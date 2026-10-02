# -*- coding: utf-8 -*-
"""普陀区计算管线 v3：名额加权主口径 + 宽表扩容（单一事实源）。

口径变更（v3）：
- **主口径**：当年到校均分 = 计划名额加权平均  `Σ(score×quota)/Σ(quota)`（只取当年该校有分数的线）
- **对照口径**：等权算术平均（v2 口径），全部保留为 `_eq` 列
- 其余步骤（逐年名次 → 分位 P / Z / ZR → 三组结构口径 → 综合口径 → 时间权重）两链完全一致

输出（覆盖式重写）：
  宽表-初中水平-普陀区-2022-2026.csv        （≈170 列：逐年逐线原始分数/名额 + 全部派生）
  趋势分析-普陀区-2022-2026.csv             （基于加权主口径）
  rank-标准化-普陀区-2022-2026.csv          （P_wq 主 / P_eq 对照 / Z,ZR 两链）
  rank-多口径总表-普陀区-2022-2026.csv       （三组 × (eq,wq) + 综合 + 时间权重）
  rank-加权敏感性-普陀区-2022-2026.csv       （加权主口径下的时间权重敏感性）
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
# 简称 → 全名（宽表原始列用简称命名）；tier 决定是否区属基线
HS = [('华二普陀', '华东师范大学第二附属中学（普陀校区）', '区属'),
      ('二中', '上海市曹杨第二中学', '区属'),
      ('晋元', '上海市晋元高级中学', '区属'),
      ('宜川', '上海市宜川中学', '区属'),
      ('华二', '华东师范大学第二附属中学', '委属'),
      ('上中', '上海市上海中学', '委属'),
      ('复附', '复旦大学附属中学', '委属'),
      ('交附', '上海交通大学附属中学', '委属'),
      ('上师大', '上海师范大学附属中学', '委属')]
SHORT2FULL = {s: f for s, f, _ in HS}
FULL2SHORT = {f: s for s, f, _ in HS}
QU4 = [f for s, f, t in HS if t == '区属']
HEAD2 = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学']
TAIL2 = ['上海市晋元高级中学', '上海市宜川中学']
GROUPS = {'all': QU4, 'head': HEAD2, 'tail': TAIL2}
ALL9 = [f for _, f, _ in HS]
W_TIME = {'lin': {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
          'exp': {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
          'recent3': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1}}


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


def num(v, nd=4):
    return '' if v is None else round(v, nd)


score_rows = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan_rows = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')
roster = {r['school_name']: r for r in load(f'{D_S}/初中名录-公办民办-普陀区-2026.csv')}

S = {}   # (校, 高中, 年) -> 分数
for r in score_rows:
    v = F(r['min_score'])
    if v is not None:
        S[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = v
Q = {}   # (校, 高中, 年) -> 名额
for r in plan_rows:
    Q[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = int(r['quota'])
CODE = {}
for r in plan_rows:
    CODE.setdefault(r['junior_high_school'], r['junior_high_school_code'])
schools = sorted({k[0] for k in S} | {k[0] for k in Q})


def group_mean(c, y, lines, chain):
    """链式均分：eq = 算术平均；wq = 计划名额加权（仅取有分数的线）。"""
    pairs = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in lines if (c, h, y) in S]
    if not pairs:
        return None
    if chain == 'eq':
        return st.fmean([v for v, _ in pairs])
    tw = sum(q for _, q in pairs)
    if tw <= 0:                       # 有分数但无名额（不该出现）→ 退化为等权
        return st.fmean([v for v, _ in pairs])
    return sum(v * q for v, q in pairs) / tw


def year_stats(mean_map, y):
    """当年池（该链有数据的全部初中）的 μ/σ/中位/IQR，并返回 {校: (P, Z, ZR)}。"""
    vals = {c: mean_map[(c, y)] for c in schools if (c, y) in mean_map}
    xs = sorted(vals.values())
    n = len(xs)
    if n < 2:
        return vals, n, {}
    mu, sg = st.fmean(xs), st.pstdev(xs)
    med = st.median(xs)
    iqr = xs[n * 3 // 4] - xs[n // 4]
    rs = iqr / 1.349 if iqr else None
    out = {}
    for c, v in vals.items():
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        r = b + (e + 1) / 2
        out[c] = (1 - (r - 1) / (n - 1), (v - mu) / sg if sg else None,
                  (v - med) / rs if rs else None)
    return vals, n, out


# ---------- 逐年链：三组 × 两链 ----------
YEAR_MEAN = {}    # (group, chain) -> {(c,y): mean}
YEAR_PZR = {}     # (group, chain) -> {(c,y): (P, Z, ZR)}
YEAR_RANK = {}    # (group, chain) -> {(c,y): rank}
YEAR_N = {}       # (group, chain, y) -> pool n
for g, lines in GROUPS.items():
    for chain in ('eq', 'wq'):
        mm = {}
        for c in schools:
            for y in YEARS:
                v = group_mean(c, y, lines, chain)
                if v is not None:
                    mm[(c, y)] = v
        YEAR_MEAN[(g, chain)] = mm
        for y in YEARS:
            vals, n, pzr = year_stats(mm, y)
            YEAR_N[(g, chain, y)] = n
        # 名次
        rk = {}
        for y in YEARS:
            vals = {c: mm[(c, y)] for c in schools if (c, y) in mm}
            xs = list(vals.values())
            for c, v in vals.items():
                b = sum(1 for w in xs if w > v)
                e = sum(1 for w in xs if w == v)
                rk[(c, y)] = b + (e + 1) / 2
        YEAR_RANK[(g, chain)] = rk

# 逐年 P / Z / ZR（两链 × 三组）
YEAR_PZR = {}
for g, lines in GROUPS.items():
    for chain in ('eq', 'wq'):
        mm = YEAR_MEAN[(g, chain)]
        d = {}
        for y in YEARS:
            vals, n, pzr = year_stats(mm, y)
            for c, t in pzr.items():
                d[(c, y)] = t
        YEAR_PZR[(g, chain)] = d


def agg(d, c):
    v = [d[(c, y)] for y in YEARS if (c, y) in d]
    return st.fmean(v) if v else None


def agg_tuple(d, c, i):
    v = [d[(c, y)][i] for y in YEARS if (c, y) in d]
    return st.fmean(v) if v else None


COV = lambda c: len([y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]])
RANKED = [c for c in schools if COV(c) == 5]        # 五年全勤（加权链）
FOUR_YEAR = [c for c in schools if COV(c) == 4]     # 恰好 4 年（与 v2 一致，仅曹杨二中附属实验中学）
TABLE = RANKED + FOUR_YEAR
assert COV  # 保留引用

# ---------- 趋势链（加权主口径） ----------
rel = {}
for c in RANKED:
    for y in YEARS:
        vals = sorted(YEAR_MEAN[('all', 'wq')][(x, y)] for x in RANKED if (x, y) in YEAR_MEAN[('all', 'wq')])
        rel[(c, y)] = YEAR_MEAN[('all', 'wq')][(c, y)] - st.median(vals)


def sen_slope(pts):
    xs = sorted(pts)
    sl = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
          for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j][0] != xs[i][0]]
    return st.median(sl) if sl else None


def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    den = (sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5
    return sum((p - mx) * (q - my) for p, q in zip(rx, ry)) / den if den else None


trend = {}
for c in RANKED:
    pts = [(y, rel[(c, y)]) for y in YEARS if (c, y) in rel]
    pts3 = [p for p in pts if p[0] >= 2024]
    trend[c] = {'rel_first': pts[0][1], 'rel_last': pts[-1][1],
                'delta_rel': pts[-1][1] - pts[0][1],
                'sen': sen_slope(pts), 'spearman': spearman([p[0] for p in pts], [p[1] for p in pts]),
                'sen_recent3': sen_slope(pts3) if len(pts3) >= 2 else None}
# 收敛回归
xs = [trend[c]['rel_first'] for c in RANKED]
ys = [trend[c]['delta_rel'] for c in RANKED]
mx, my = st.fmean(xs), st.fmean(ys)
b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
a = my - b * mx
pred = [a + b * x for x in xs]
resid = [y - p for y, p in zip(ys, pred)]
sd = st.pstdev(resid)
r2 = 1 - sum(r * r for r in resid) / sum((y - my) ** 2 for y in ys)
for c, pr, rs in zip(RANKED, pred, resid):
    trend[c]['convergence_pred'] = pr
    trend[c]['residual'] = rs
    trend[c]['residual_z'] = rs / sd if sd else None
    trend[c]['beyond_convergence'] = int(abs(rs / sd) >= 1) if sd else 0

# ---------- 输出 1：宽表（扩容） ----------
wide_cols = ['junior_high_school', 'junior_high_school_code', 'ownership',
             'years_included', 'years_list', 'ranked']
for s, full, _ in HS:
    for y in YEARS:
        wide_cols.append(f'score_{s}_{y}')
for s, full, _ in HS:
    for y in YEARS:
        wide_cols.append(f'quota_{s}_{y}')
for y in YEARS:
    wide_cols += [f'mean_score_base4_eq_{y}', f'mean_score_base4_wq_{y}',
                  f'rank_base4_eq_{y}', f'rank_base4_wq_{y}',
                  f'valid_pairs_{y}', f'quota4_{y}',
                  f'P_eq_{y}', f'P_wq_{y}', f'Z_eq_{y}', f'Z_wq_{y}', f'ZR_eq_{y}', f'ZR_wq_{y}']
wide_cols += [
    'quota4_avg', 'quota_all_avg',
    'mean_rank_base4_wq_avg', 'mean_rank_base4_wq_median', 'mean_rank_base4_wq_var',
    'mean_rank_base4_eq_avg', 'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
    'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
    'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq',
    'P_wq_all', 'rank_P_wq_all', 'P_wq_head', 'rank_P_wq_head',
    'P_wq_tail', 'rank_P_wq_tail', 'P_wq_comb', 'rank_P_wq_comb',
    'P_eq_all', 'rank_P_eq_all', 'P_eq_head', 'rank_P_eq_head',
    'P_eq_tail', 'rank_P_eq_tail', 'P_eq_comb', 'rank_P_eq_comb',
    'Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb',
    'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp', 'P_recent3', 'rank_P_recent3',
]

WIDE_SCHOOLS = [c for c in schools if COV(c) >= 1]
rows_out = []
for c in WIDE_SCHOOLS:
    cov = [y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]]
    q4 = [sum(Q.get((c, h, y), 0) for h in QU4) for y in cov]
    qa = [sum(Q.get((c, h, y), 0) for h in ALL9) for y in cov]
    d = {'junior_high_school': c, 'junior_high_school_code': CODE.get(c, ''),
         'ownership': roster.get(c, {}).get('ownership', ''),
         'years_included': len(cov), 'years_list': ';'.join(str(y) for y in cov),
         'ranked': 1 if c in TABLE else 0}
    for s, full, _ in HS:
        for y in YEARS:
            d[f'score_{s}_{y}'] = S.get((c, full, y), '')
    for s, full, _ in HS:
        for y in YEARS:
            d[f'quota_{s}_{y}'] = Q.get((c, full, y), '')
    for y in YEARS:
        d[f'mean_score_base4_eq_{y}'] = num(YEAR_MEAN[('all', 'eq')].get((c, y)), 3)
        d[f'mean_score_base4_wq_{y}'] = num(YEAR_MEAN[('all', 'wq')].get((c, y)), 3)
        d[f'rank_base4_eq_{y}'] = num(YEAR_RANK[('all', 'eq')].get((c, y)), 2)
        d[f'rank_base4_wq_{y}'] = num(YEAR_RANK[('all', 'wq')].get((c, y)), 2)
        d[f'valid_pairs_{y}'] = sum(1 for h in QU4 if (c, h, y) in S)
        d[f'quota4_{y}'] = sum(Q.get((c, h, y), 0) for h in QU4)
        for chain, tag in (('eq', 'eq'), ('wq', 'wq')):
            t = YEAR_PZR[('all', chain)].get((c, y))
            d[f'P_{tag}_{y}'] = num(t[0], 6) if t else ''
            d[f'Z_{tag}_{y}'] = num(t[1], 4) if t else ''
            d[f'ZR_{tag}_{y}'] = num(t[2], 4) if t else ''
    d['quota4_avg'] = num(st.fmean(q4), 4)
    d['quota_all_avg'] = num(st.fmean(qa), 4)
    mr = [YEAR_RANK[('all', 'wq')][(c, y)] for y in cov]
    d['mean_rank_base4_wq_avg'] = num(st.fmean(mr), 4)
    d['mean_rank_base4_wq_median'] = num(st.median(mr), 4)
    d['mean_rank_base4_wq_var'] = num(st.pvariance(mr), 4) if len(mr) > 1 else ''
    d['mean_rank_base4_eq_avg'] = num(agg(YEAR_RANK[('all', 'eq')], c), 4)
    d['mean_rank_base4_w_linear'] = num(
        sum(W_TIME['lin'][y] * YEAR_RANK[('all', 'wq')][(c, y)] for y in cov)
        / sum(W_TIME['lin'][y] for y in cov), 4)
    d['mean_rank_base4_w_exp'] = num(
        sum(W_TIME['exp'][y] * YEAR_RANK[('all', 'wq')][(c, y)] for y in cov)
        / sum(W_TIME['exp'][y] for y in cov), 4)
    rows_out.append(d)

# 聚合 P/Z/ZR（三组 × 两链 + 综合）与名次
P_agg, Z_agg, ZR_agg = {}, {}, {}
for g in GROUPS:
    for chain in ('eq', 'wq'):
        for c in WIDE_SCHOOLS:
            P_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 0)
            Z_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 1)
            ZR_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 2)
MISSING = []
for c in WIDE_SCHOOLS:
    for chain in ('eq', 'wq'):
        for tag, dic in (('P', P_agg), ('Z', Z_agg), ('ZR', ZR_agg)):
            vals = [dic[(g, chain, c)] for g in GROUPS if dic[(g, chain, c)] is not None]
            if len(vals) < len(GROUPS):
                MISSING.append((c, chain, tag, len(vals)))
            dic[('comb', chain, c)] = st.fmean(vals) if vals else None
if MISSING:
    print('缺少部分分组数据的 (校, 链, 指标, 可用组数)：', MISSING[:8], '共', len(MISSING))


def ranks_of(dic):
    ok = [(c, dic[c]) for c in TABLE if dic[c] is not None]
    o = sorted(ok, key=lambda t: -t[1])
    return {c: i for i, (c, _) in enumerate(o, 1)}


RK = {}
for g in list(GROUPS) + ['comb']:
    for chain in ('eq', 'wq'):
        RK[(g, chain)] = ranks_of({c: P_agg[(g, chain, c)] for c in TABLE})
for chain in ('eq', 'wq'):
    for tag, dic in (('Z', Z_agg), ('ZR', ZR_agg)):
        RK[(tag + '_' + chain,)] = ranks_of({c: dic[('comb', chain, c)] for c in TABLE})
# 时间权重（加权主口径）
for c in WIDE_SCHOOLS:
    cov = [y for y in YEARS if (c, y) in YEAR_PZR[('all', 'wq')]]
    for k, w in W_TIME.items():
        num_ = sum(w[y] * YEAR_PZR[('all', 'wq')][(c, y)][0] for y in cov if w[y] > 0)
        den = sum(w[y] for y in cov if w[y] > 0)
        P_agg[(k, 'wq', c)] = num_ / den if den else None
for k in W_TIME:
    RK[(k, 'wq')] = ranks_of({c: P_agg[(k, 'wq', c)] for c in TABLE})
print('入榜样本:', len(TABLE), '｜4 年校:', [c for c in FOUR_YEAR])

# 写回宽表聚合列
by_name = {d['junior_high_school']: d for d in rows_out}
for c in WIDE_SCHOOLS:
    d = by_name[c]
    R = lambda key: RK[key].get(c, '')
    d['P_wq'] = num(P_agg[('all', 'wq', c)], 6)
    d['rank_P_wq'] = R(('all', 'wq'))
    d['P_eq'] = num(P_agg[('all', 'eq', c)], 6)
    d['rank_P_eq'] = R(('all', 'eq'))
    d['shift_wq_eq'] = (RK[('all', 'eq')][c] - RK[('all', 'wq')][c]) if c in TABLE else ''
    d['Z_wq'] = num(Z_agg[('all', 'wq', c)], 4)
    d['rank_Z_wq'] = R(('Z_wq',))
    d['ZR_wq'] = num(ZR_agg[('all', 'wq', c)], 4)
    d['rank_ZR_wq'] = R(('ZR_wq',))
    for g, tag in [('all', 'all'), ('head', 'head'), ('tail', 'tail'), ('comb', 'comb')]:
        d[f'P_wq_{tag}'] = num(P_agg[(g, 'wq', c)], 6)
        d[f'rank_P_wq_{tag}'] = R((g, 'wq'))
        d[f'P_eq_{tag}'] = num(P_agg[(g, 'eq', c)], 6)
        d[f'rank_P_eq_{tag}'] = R((g, 'eq'))
    d['Z_wq_comb'] = num(Z_agg[('comb', 'wq', c)], 4)
    d['rank_Z_wq_comb'] = R(('Z_wq',))
    d['ZR_wq_comb'] = num(ZR_agg[('comb', 'wq', c)], 4)
    d['rank_ZR_wq_comb'] = R(('ZR_wq',))
    for k in W_TIME:
        d[f'P_{k}'] = num(P_agg.get((k, 'wq', c)), 6)
        d[f'rank_P_{k}'] = R((k, 'wq'))

with open(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=wide_cols)
    w.writeheader()
    for d in sorted(rows_out, key=lambda d: (d['rank_P_wq'] if d['rank_P_wq'] != '' else 999)):
        w.writerow({k: d.get(k, '') for k in wide_cols})

# ---------- 输出 2：趋势分析（加权主口径） ----------
tcols = ['junior_high_school', 'n_years', 'rel_first', 'rel_last', 'delta_rel', 'sen', 'spearman',
         'sen_recent3', 'convergence_pred', 'residual', 'residual_z', 'beyond_convergence']
with open(f'{D_A}/趋势分析-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=tcols)
    w.writeheader()
    for c in sorted(RANKED, key=lambda c: RK[('all', 'wq')][c]):
        t = trend[c]
        w.writerow({'junior_high_school': c, 'n_years': 5,
                    'rel_first': num(t['rel_first'], 3), 'rel_last': num(t['rel_last'], 3),
                    'delta_rel': num(t['delta_rel'], 3), 'sen': num(t['sen'], 4),
                    'spearman': num(t['spearman'], 4), 'sen_recent3': num(t['sen_recent3'], 4),
                    'convergence_pred': num(t['convergence_pred'], 3),
                    'residual': num(t['residual'], 3), 'residual_z': num(t['residual_z'], 3),
                    'beyond_convergence': t['beyond_convergence']})

# ---------- 输出 3：rank-标准化 ----------
rcols = ['junior_high_school', 'junior_high_school_code', 'n_years', 'ranked',
         'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
         'Z_wq', 'ZR_wq', 'rank_Z_wq', 'rank_ZR_wq', 'Z_eq', 'ZR_eq',
         'mean_rank_wq_avg', 'mean_rank_eq_avg']
with open(f'{D_A}/rank-标准化-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=rcols)
    w.writeheader()
    for c in WIDE_SCHOOLS:
        d = by_name[c]
        w.writerow({'junior_high_school': c, 'junior_high_school_code': d['junior_high_school_code'],
                    'n_years': d['years_included'], 'ranked': d['ranked'],
                    'P_wq': d['P_wq'], 'rank_P_wq': d['rank_P_wq'],
                    'P_eq': d['P_eq'], 'rank_P_eq': d['rank_P_eq'], 'shift_wq_eq': d['shift_wq_eq'],
                    'Z_wq': d['Z_wq'], 'ZR_wq': d['ZR_wq'],
                    'rank_Z_wq': d['rank_Z_wq'], 'rank_ZR_wq': d['rank_ZR_wq'],
                    'Z_eq': num(Z_agg[('all', 'eq', c)], 4), 'ZR_eq': num(ZR_agg[('all', 'eq', c)], 4),
                    'mean_rank_wq_avg': d['mean_rank_base4_wq_avg'],
                    'mean_rank_eq_avg': d['mean_rank_base4_eq_avg']})

# ---------- 输出 4：rank-多口径总表 ----------
mcols = ['junior_high_school', 'n_years',
         'P_wq_comb', 'rank_P_wq_comb', 'P_wq_all', 'rank_P_wq_all',
         'P_wq_head', 'rank_P_wq_head', 'P_wq_tail', 'rank_P_wq_tail',
         'P_eq_comb', 'rank_P_eq_comb', 'P_eq_all', 'rank_P_eq_all',
         'P_eq_head', 'rank_P_eq_head', 'P_eq_tail', 'rank_P_eq_tail',
         'shift_comb_wq_eq', 'Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb',
         'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp', 'P_recent3', 'rank_P_recent3',
         'mean_rank_wq_avg', 'quota4_avg', 'quota_all_avg']
with open(f'{D_A}/rank-多口径总表-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=mcols)
    w.writeheader()
    for d in sorted([r for r in rows_out if r['junior_high_school'] in TABLE],
                    key=lambda d: d['rank_P_wq_comb']):
        d['shift_comb_wq_eq'] = RK[('comb', 'eq')][d['junior_high_school']] - d['rank_P_wq_comb']
        d['n_years'] = d['years_included']
        w.writerow({k: d.get(k, '') for k in mcols})

# ---------- 输出 5：rank-加权敏感性（加权主口径） ----------
scols = ['junior_high_school', 'n_years', 'P_eq', 'P_lin', 'P_exp', 'P_recent3',
         'rank_eq', 'rank_lin', 'rank_exp', 'rank_recent3',
         'shift_lin', 'shift_exp', 'shift_recent3']
with open(f'{D_A}/rank-加权敏感性-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=scols)
    w.writeheader()
    for c in sorted(TABLE, key=lambda c: RK[(('all', 'wq'))][c]):
        d = by_name[c]
        r = {k: RK[(k, 'wq')][c] for k in W_TIME}
        w.writerow({'junior_high_school': c, 'n_years': d['years_included'],
                    'P_eq': d['P_wq'], 'P_lin': d['P_lin'], 'P_exp': d['P_exp'],
                    'P_recent3': d['P_recent3'],
                    'rank_eq': d['rank_P_wq'], 'rank_lin': r['lin'], 'rank_exp': r['exp'],
                    'rank_recent3': r['recent3'],
                    'shift_lin': r['lin'] - d['rank_P_wq'],
                    'shift_exp': r['exp'] - d['rank_P_wq'],
                    'shift_recent3': r['recent3'] - d['rank_P_wq']})

# ---------- 控制台 ----------
print(f'宽表列数 {len(wide_cols)}，行数 {len(rows_out)}')
print(f'入榜 {len(TABLE)} 所（五年全勤 {len(RANKED)} + 4 年 {len(FOUR_YEAR)}）')
print(f'\n=== 加权主口径 综合排名（前 10）与等权对照 ===')
for c in sorted(TABLE, key=lambda c: RK[('comb', 'wq')][c])[:10]:
    d = by_name[c]
    print(f"  {d['rank_P_wq_comb']:>2} {c.replace('上海市',''):<24} 加权综合={d['P_wq_comb']} "
          f"等权综合第{d['rank_P_eq_comb']:>2}（位次差 {d['shift_comb_wq_eq']:+d}） "
          f"全身{ d['rank_P_wq_all'] }/头{ d['rank_P_wq_head'] }/尾{ d['rank_P_wq_tail'] }")
print(f'\n收敛回归：b={b:.3f}  R²={r2:.3f}  残差σ={sd:.2f}')
print(f'规模相关性：ρ(名额, 加权名次)={spearman([F(by_name[c]["quota4_avg"]) for c in TABLE], [RK[("all","wq")][c] for c in TABLE]):+.3f}')
print('年限池量：', {k: YEAR_N[k] for k in sorted(YEAR_N)})
