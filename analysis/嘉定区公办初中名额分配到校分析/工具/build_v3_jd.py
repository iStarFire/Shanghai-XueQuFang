# -*- coding: utf-8 -*-
"""嘉定区计算管线 v3：宽表扩容 + 全部原始数据（单一事实源）。

对齐普陀 `build_v3.py` 模板，差异：
- 线集合为 8 条（3 区属 + 5 委属），委属线**原始数据进宽表但不进排名口径**
- 区属线 2022–2024 为 2 条、2025–2026 为 3 条（142004 上师嘉新 2025 年首现）
- 头/尾分组固定定义：head = 难度较高 2 条，tail = 难度最低 1 条 ⇒ 仅 2025–2026 可用
- 额外保留 `SEN` 列（报告主表使用）

口径：
- 主口径 wq：当年到校均分 = Σ(score×quota)/Σ(quota)（仅取当年该校有分数的线）
- 对照口径 eq：同年有分数的线算术平均
- 排名：逐年名次（平均名次法）→ 分位 P = 1-(rank-1)/(n-1)；Z / ZR 为辅
- 三组结构口径 all/head/tail → 综合 comb = 三组可用值的均值

输出（覆盖式重写 6 个 CSV）：
  宽表-初中水平-嘉定区-2022-2026.csv
  趋势分析-嘉定区-2022-2026.csv
  rank-标准化-嘉定区-2022-2026.csv
  rank-多口径总表-嘉定区-2022-2026.csv
  rank-加权敏感性-嘉定区-2022-2026.csv
  单线视角-嘉定区-2022-2026.csv
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_S = f'{ROOT}/data/嘉定区/学校'
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = [2022, 2023, 2024, 2025, 2026]

# (宽表简称, 代码, 全名, tier) —— 排序：区属在前（按难度降序），委属在后
HS = [('交大嘉定', '142002', '上海交通大学附属中学嘉定分校', '区属'),
      ('上师嘉新', '142004', '上海师范大学附属中学嘉定新城分校', '区属'),
      ('嘉定一中', '142001', '上海市嘉定区第一中学', '区属'),
      ('上海中学', '042032', '上海市上海中学', '委属'),
      ('交大本部', '102056', '上海交通大学附属中学', '委属'),
      ('复旦附中', '102057', '复旦大学附属中学', '委属'),
      ('华师大二附', '152003', '华东师范大学第二附属中学', '委属'),
      ('上师大附中', '152006', '上海师范大学附属中学', '委属')]
SHORT2CODE = {s: c for s, c, _, _ in HS}
QU3 = [c for _, c, _, t in HS if t == '区属']          # 排名基线：3 条区属线
HEAD2 = ['142002', '142004']                            # 难度较高 2 条
TAIL1 = ['142001']                                     # 难度最低 1 条
GROUPS = {'all': QU3, 'head': HEAD2, 'tail': TAIL1}
ALL8 = [c for _, c, _, _ in HS]
W_TIME = {'lin': {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
          'exp': {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
          'recent3': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1},
          # 近 2 年（2025–2026 等权）：用户 2026-10-03 要求，最短的近期窗口
          'recent2': {2022: 0, 2023: 0, 2024: 0, 2025: 1, 2026: 1}}


def load(p):
    with open(f'{D_S}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


def num(v, nd=4):
    return '' if v is None else round(v, nd)


score_rows = load('名额到校最低分数线-嘉定区-2022-2026.csv')
plan_rows = (load('名额到校计划-嘉定区-2023-2026.csv')
             + load('名额到校计划-嘉定区-2022-图片转录.csv'))
roster = {r['junior_high_school']: r for r in load('初中名录-公办民办-嘉定区-2026.csv')}

# ---- 同校改名归并（旧名 -> 规范名），在**读取阶段**映射 ----
# 依据 .trellis/spec/quality/data-validation.md 陷阱 7：同一实体跨年只占一行，
# 显示名取最新年份写法，历年写法另记 former_names 列。
# 三组归并的证据链与「无编号可核」的限制见 design.md 2.1-2.3；
# 名录侧的同步归并由 build_roster_jd.py 完成（缺它会导致 ownership 静默变空）。
ALIAS = {
    '上海市嘉定区德富路中学': '交大附中附属嘉定德富中学',
    '上海市嘉定区杨柳初级中学': '上海市嘉定区嘉二实验学校',
    '上海嘉定区世界外国语学校': '上海嘉定区世外学校',
}
# 陷阱 8 高风险对：名称相似但确为两所不同学校，禁止合并
MUST_KEEP_SEPARATE = ('上海外国语大学嘉定外国语学校', '上海嘉定区世外学校')


def CANON(n):
    return ALIAS.get(n, n)


S, Q, CODE = {}, {}, {}
for r in score_rows:
    c = CANON(r['junior_high_school'])
    v = F(r['min_score'])
    if v is not None:
        S[(c, r['senior_high_school_code'], int(r['year']))] = v
    CODE.setdefault(c, r['junior_high_school_code'])
for r in plan_rows:
    c = CANON(r['junior_high_school'])
    Q[(c, r['senior_high_school_code'], int(r['year']))] = int(r['quota'])
    CODE.setdefault(c, r.get('junior_high_school_code', ''))
schools = sorted({k[0] for k in S} | {k[0] for k in Q})
# ---- 排名池：**只用当年有数据的公办初中**，民办不参与排名与分位 ----
# 用户 2026-10-03 明确要求「排名不要考虑民办，只考虑当年全部公办学校」。
# 改动前池子含民办（2024 起每年 7 所），且民办多为强校（2026 民办远东 P=1.000
# 即全区第 1），会机械地压低所有公办校的分位与名次。
PUB = {c for c in schools if roster.get(c, {}).get('ownership') == '公办'}
print(f'排名池（公办）{len(PUB)} 所｜民办 {len(schools) - len(PUB)} 所不参与排名')



print(f'学校 {len(schools)} 所｜分数线 {len(S)} 格｜名额 {len(Q)} 格')

# 归并自检：旧名不得残留、规范名必须在、陷阱 8 高风险校不得被合并掉
assert not (set(schools) & set(ALIAS)), f'旧名残留：{set(schools) & set(ALIAS)}'
for _n in MUST_KEEP_SEPARATE:
    assert _n in schools, f'陷阱 8：{_n} 缺失'
_missing = [c for c in schools if c not in roster]
assert not _missing, f'名录缺 {len(_missing)} 所（名录未同步归并？）：{_missing[:5]}'


def group_mean(c, y, codes, chain):
    """链式均分：eq = 算术平均；wq = 计划名额加权（仅取当年该校有分数的线）。"""
    pairs = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in codes if (c, h, y) in S]
    if not pairs:
        return None
    if chain == 'eq':
        return st.fmean([v for v, _ in pairs])
    tw = sum(q for _, q in pairs)
    if tw <= 0:
        return st.fmean([v for v, _ in pairs])
    return sum(v * q for v, q in pairs) / tw


def year_stats(mm, y):
    # 排名池只含公办（民办保留 mean 供披露，但无分位/位次）
    vals = {c: mm[(c, y)] for c in PUB if (c, y) in mm}
    xs = sorted(vals.values())
    n = len(xs)
    if n < 2:
        return n, {}
    mu, sg, med = st.fmean(xs), st.pstdev(xs), st.median(xs)
    iqr = xs[n * 3 // 4] - xs[n // 4]
    rs = iqr / 1.349 if iqr else None
    out = {}
    for c, v in vals.items():
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        r = b + (e + 1) / 2
        out[c] = (1 - (r - 1) / (n - 1), (v - mu) / sg if sg else None,
                  (v - med) / rs if rs else None)
    return n, out


# ---------- 逐年链：三组 × 两链 ----------
YEAR_MEAN, YEAR_PZR, YEAR_RANK, YEAR_N = {}, {}, {}, {}
for g, codes in GROUPS.items():
    for chain in ('eq', 'wq'):
        mm = {}
        for c in schools:
            for y in YEARS:
                v = group_mean(c, y, codes, chain)
                if v is not None:
                    mm[(c, y)] = v
        YEAR_MEAN[(g, chain)] = mm
        rk = {}
        for y in YEARS:
            vals = {c: mm[(c, y)] for c in PUB if (c, y) in mm}
            xs = list(vals.values())
            YEAR_N[(g, chain, y)] = len(xs)
            for c, v in vals.items():
                b = sum(1 for w in xs if w > v)
                e = sum(1 for w in xs if w == v)
                rk[(c, y)] = b + (e + 1) / 2
        YEAR_RANK[(g, chain)] = rk
        d = {}
        for y in YEARS:
            _, pzr = year_stats(mm, y)
            for c, t in pzr.items():
                d[(c, y)] = t
        YEAR_PZR[(g, chain)] = d


def agg_tuple(d, c, i):
    v = [d[(c, y)][i] for y in YEARS if (c, y) in d]
    return st.fmean(v) if v else None


COV = lambda c: len([y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]])
RANKED = [c for c in schools if COV(c) == 5]
FOUR_YEAR = [c for c in schools if COV(c) == 4]
TABLE = RANKED + FOUR_YEAR

# ---- row_type：区分「入榜排序 / 新开办缺历史数据 / 民办排除」三类 ----
# 顺序按 design 3.2：民办优先（民办校多为老校首次获得名额资格，并非新办，
# 见 build_roster_jd.py 核实记录），故不能靠年份判定民办。
def row_type(c):
    if roster.get(c, {}).get('ownership') == '民办':
        return 'excluded_private'
    return 'ranked' if c in TABLE else 'new_school'


ROW_TYPE = {c: row_type(c) for c in schools}
NEW = [c for c in schools if ROW_TYPE[c] == 'new_school']
PRIV = [c for c in schools if ROW_TYPE[c] == 'excluded_private']

# 自检：new_school 必须是「有历史数据缺口且延续至今」的公办校
for c in NEW:
    sy = roster.get(c, {}).get('score_years', '').split(';')
    assert '2026' in sy, f'{c} 不延续至今，不能归为新开办'
    assert roster.get(c, {}).get('ownership') == '公办', f'{c} 办学性质异常'
assert len(PRIV) == 8, f'民办应为 8 所，实际 {len(PRIV)}'
assert len(schools) == 40, f'归并后全区应 40 所，实际 {len(schools)}'
print(f'五年全勤 {len(RANKED)}｜恰好 4 年 {len(FOUR_YEAR)} {FOUR_YEAR}｜入榜 {len(TABLE)}')
print(f'row_type｜ranked {len(TABLE)}｜new_school {len(NEW)} {NEW}｜excluded_private {len(PRIV)}')

# ---------- 趋势链（加权主口径） ----------
# rel 基准 = 当年「有数据全池」中位（嘉定既有口径；换用五年全勤池会使 rel 均名与 SEN 改变）
rel = {}
for y in YEARS:
    vals = sorted(YEAR_MEAN[('all', 'wq')][(x, y)] for x in PUB if (x, y) in YEAR_MEAN[('all', 'wq')])
    med_y = st.median(vals)
    for x in schools:
        if (x, y) in YEAR_MEAN[('all', 'wq')]:
            rel[(x, y)] = YEAR_MEAN[('all', 'wq')][(x, y)] - med_y
REL_POOL = {y: len([x for x in PUB if (x, y) in YEAR_MEAN[('all', 'wq')]]) for y in YEARS}
REL_MED = {y: st.median(sorted(YEAR_MEAN[('all', 'wq')][(x, y)]
                               for x in schools if (x, y) in YEAR_MEAN[('all', 'wq')]))
           for y in YEARS}


def sen_slope(pts):
    xs = sorted(pts)
    sl = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
          for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j][0] != xs[i][0]]
    return st.median(sl) if sl else None


def sen_ols(pts):
    """嘉定原口径：rel 对年份序号（0..n-1）的 OLS 斜率。"""
    n = len(pts)
    if n < 3:
        return None
    xs = list(range(n))
    ys = [p[1] for p in pts]
    mx, my = st.fmean(xs), st.fmean(ys)
    den = sum((i - mx) ** 2 for i in xs)
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / den if den else None


def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    den = (sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / den if den else None


trend = {}
for c in [x for x in schools if COV(x) >= 3]:
    pts = [(y, rel[(c, y)]) for y in YEARS if (c, y) in rel]
    pts3 = [p for p in pts if p[0] >= 2024]
    trend[c] = {'rel_first': pts[0][1], 'rel_last': pts[-1][1],
                'delta_rel': pts[-1][1] - pts[0][1],
                'sen': sen_slope(pts), 'sen_ols': sen_ols(pts),
                'spearman': spearman([p[0] for p in pts], [p[1] for p in pts]),
                'sen_recent3': sen_slope(pts3) if len(pts3) >= 2 else None}
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
print(f'收敛回归A（总变化）Δrel~rel_2022：b={b:.3f} R²={r2:.3f} 残差σ={sd:.2f}')

# 收敛回归B（逐年水平，报告 4.2/4.3 口径）：rel_y = a + b*rel_2022 + e
CONV_B = {}
for y in YEARS[1:]:
    xs_b = [trend[c]['rel_first'] for c in RANKED]
    ys_b = [rel[(c, y)] for c in RANKED]
    mx_b, my_b = st.fmean(xs_b), st.fmean(ys_b)
    bb = (sum((x - mx_b) * (v - my_b) for x, v in zip(xs_b, ys_b))
          / sum((x - mx_b) ** 2 for x in xs_b))
    aa = my_b - bb * mx_b
    rs_b = [v - (aa + bb * x) for x, v in zip(xs_b, ys_b)]
    sd_b = st.pstdev(rs_b) or 1e-9
    sst = sum((v - my_b) ** 2 for v in ys_b)
    r2b = 1 - sum(r * r for r in rs_b) / sst if sst else None
    for c, r_ in zip(RANKED, rs_b):
        CONV_B[(c, y)] = {'b': bb, 'r2': r2b, 'z': r_ / sd_b}
    print(f'收敛回归B {y}~2022：b={bb:+.3f} R²={r2b:.3f} '
          f'|z|≥1 的学校 {sum(1 for r_ in rs_b if abs(r_) >= sd_b)} 所')

# ---------- 聚合 P/Z/ZR（三组 × 两链 + 综合） ----------
AGG = {t: {} for t in ('P', 'Z', 'ZR')}
for g in GROUPS:
    for chain in ('eq', 'wq'):
        for c in schools:
            for i, t in enumerate(('P', 'Z', 'ZR')):
                AGG[t][(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, i)
for c in schools:
    for chain in ('eq', 'wq'):
        for t in ('P', 'Z', 'ZR'):
            vals = [AGG[t][(g, chain, c)] for g in GROUPS if AGG[t][(g, chain, c)] is not None]
            AGG[t][('comb', chain, c)] = st.fmean(vals) if vals else None
for c in schools:
    for k, w in W_TIME.items():
        cov = [y for y in YEARS if (c, y) in YEAR_PZR[('all', 'wq')]]
        num_ = sum(w[y] * YEAR_PZR[('all', 'wq')][(c, y)][0] for y in cov if w[y] > 0)
        den = sum(w[y] for y in cov if w[y] > 0)
        AGG['P'][(k, 'wq', c)] = num_ / den if den else None


def ranks_of(getter):
    ok = [(c, getter(c)) for c in TABLE if getter(c) is not None]
    return {c: i for i, (c, _) in enumerate(sorted(ok, key=lambda t: -t[1]), 1)}


RK = {}
for g in list(GROUPS) + ['comb']:
    for chain in ('eq', 'wq'):
        RK[(g, chain)] = ranks_of(lambda c, g=g, ch=chain: AGG['P'][(g, ch, c)])
# Z / ZR：`_wq` 系列排 all 组值，`_comb` 系列排三组均值——两者必须分别成列，
# 不能像普陀模板那样让 rank_Z_wq 实际排的是 comb 值（值与名次口径不符）。
for chain in ('eq', 'wq'):
    for t in ('Z', 'ZR'):
        RK[(t, chain)] = ranks_of(lambda c, t=t, ch=chain: AGG[t][('all', ch, c)])
        RK[(t + '_comb', chain)] = ranks_of(lambda c, t=t, ch=chain: AGG[t][('comb', ch, c)])
for k in W_TIME:
    RK[(k, 'wq')] = ranks_of(lambda c, k=k: AGG['P'][(k, 'wq', c)])

# ---------- 输出 1：宽表 ----------
wide_cols = ['junior_high_school', 'junior_high_school_former_names',
             'junior_high_school_code', 'ownership', 'row_type',
             'years_included', 'years_list', 'ranked']
for s, c, _, _ in HS:
    for y in YEARS:
        wide_cols.append(f'score_{s}_{y}')
for s, c, _, _ in HS:
    for y in YEARS:
        wide_cols.append(f'quota_{s}_{y}')
for y in YEARS:
    wide_cols += [f'mean_score_base3_eq_{y}', f'mean_score_base3_wq_{y}',
                  f'rank_base3_eq_{y}', f'rank_base3_wq_{y}',
                  f'valid_pairs_{y}', f'quota3_{y}', f'rel_{y}',
                  f'P_eq_{y}', f'P_wq_{y}', f'Z_eq_{y}', f'Z_wq_{y}',
                  f'ZR_eq_{y}', f'ZR_wq_{y}']
wide_cols += ['quota3_avg', 'quota_all_avg',
              'mean_rank_base3_wq_avg', 'mean_rank_base3_wq_median',
              'mean_rank_base3_wq_var', 'mean_rank_base3_eq_avg',
              'mean_rank_base3_w_linear', 'mean_rank_base3_w_exp',
              'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
              'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq',
              'rel_avg', 'SEN']
for g in ('all', 'head', 'tail', 'comb'):
    wide_cols += [f'P_wq_{g}', f'rank_P_wq_{g}', f'P_eq_{g}', f'rank_P_eq_{g}']
wide_cols += ['Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb']
for k in W_TIME:
    wide_cols += [f'P_{k}', f'rank_P_{k}']

rows_out = []
for c in schools:
    cov = [y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]]
    d = {'junior_high_school': c,
         'junior_high_school_former_names': roster.get(c, {}).get(
             'junior_high_school_former_names', ''),
         'junior_high_school_code': CODE.get(c, ''),
         'ownership': roster.get(c, {}).get('ownership', ''),
         'row_type': ROW_TYPE[c],
         'years_included': len(cov), 'years_list': ';'.join(str(y) for y in cov),
         'ranked': 1 if c in TABLE else 0}
    for s, code, _, _ in HS:
        for y in YEARS:
            d[f'score_{s}_{y}'] = S.get((c, code, y), '')
            d[f'quota_{s}_{y}'] = Q.get((c, code, y), '')
    for y in YEARS:
        d[f'mean_score_base3_eq_{y}'] = num(YEAR_MEAN[('all', 'eq')].get((c, y)), 3)
        d[f'mean_score_base3_wq_{y}'] = num(YEAR_MEAN[('all', 'wq')].get((c, y)), 3)
        d[f'rank_base3_eq_{y}'] = num(YEAR_RANK[('all', 'eq')].get((c, y)), 2)
        d[f'rank_base3_wq_{y}'] = num(YEAR_RANK[('all', 'wq')].get((c, y)), 2)
        d[f'valid_pairs_{y}'] = sum(1 for h in QU3 if (c, h, y) in S)
        d[f'quota3_{y}'] = sum(Q.get((c, h, y), 0) for h in QU3)
        d[f'rel_{y}'] = num(rel.get((c, y)), 4)
        for chain in ('eq', 'wq'):
            t = YEAR_PZR[('all', chain)].get((c, y))
            d[f'P_{chain}_{y}'] = num(t[0], 6) if t else ''
            d[f'Z_{chain}_{y}'] = num(t[1], 4) if t else ''
            d[f'ZR_{chain}_{y}'] = num(t[2], 4) if t else ''
    q3 = [sum(Q.get((c, h, y), 0) for h in QU3) for y in cov]
    qa = [sum(Q.get((c, h, y), 0) for h in ALL8) for y in cov]
    d['quota3_avg'] = num(st.fmean(q3), 4) if q3 else ''
    d['quota_all_avg'] = num(st.fmean(qa), 4)
    # 民办不在排名池（YEAR_RANK 只含公办），逐年位次可能缺失 -> 跳过而非报错
    mr = [YEAR_RANK[('all', 'wq')][(c, y)] for y in cov
          if (c, y) in YEAR_RANK[('all', 'wq')]]
    d['mean_rank_base3_wq_avg'] = num(st.fmean(mr), 4) if mr else ''
    d['mean_rank_base3_wq_median'] = num(st.median(mr), 4) if mr else ''
    d['mean_rank_base3_wq_var'] = num(st.pvariance(mr), 4) if len(mr) > 1 else ''
    _eq = [YEAR_RANK[('all', 'eq')][(c, y)] for y in cov
           if (c, y) in YEAR_RANK[('all', 'eq')]]
    d['mean_rank_base3_eq_avg'] = num(st.fmean(_eq), 4) if _eq else ''
    _lin = [(W_TIME['lin'][y], YEAR_RANK[('all', 'wq')][(c, y)]) for y in cov
            if (c, y) in YEAR_RANK[('all', 'wq')]]
    d['mean_rank_base3_w_linear'] = num(
        sum(w * r for w, r in _lin) / sum(w for w, _ in _lin), 4) if _lin else ''
    _exp = [(W_TIME['exp'][y], YEAR_RANK[('all', 'wq')][(c, y)]) for y in cov
            if (c, y) in YEAR_RANK[('all', 'wq')]]
    d['mean_rank_base3_w_exp'] = num(
        sum(w * r for w, r in _exp) / sum(w for w, _ in _exp), 4) if _exp else ''
    d['P_wq'] = num(AGG['P'][('all', 'wq', c)], 6)
    d['rank_P_wq'] = RK[('all', 'wq')].get(c, '')
    d['P_eq'] = num(AGG['P'][('all', 'eq', c)], 6)
    d['rank_P_eq'] = RK[('all', 'eq')].get(c, '')
    d['shift_wq_eq'] = (RK[('all', 'eq')][c] - RK[('all', 'wq')][c]) if c in TABLE else ''
    d['Z_wq'] = num(AGG['Z'][('all', 'wq', c)], 4)
    d['rank_Z_wq'] = RK[('Z', 'wq')].get(c, '')
    d['ZR_wq'] = num(AGG['ZR'][('all', 'wq', c)], 4)
    d['rank_ZR_wq'] = RK[('ZR', 'wq')].get(c, '')
    rl = [rel[(c, y)] for y in cov if (c, y) in rel]
    d['rel_avg'] = num(st.fmean(rl), 4) if rl else ''
    d['SEN'] = num(trend[c]['sen_ols'], 4) if c in trend else ''
    for g in ('all', 'head', 'tail', 'comb'):
        d[f'P_wq_{g}'] = num(AGG['P'][(g, 'wq', c)], 6)
        d[f'rank_P_wq_{g}'] = RK[(g, 'wq')].get(c, '')
        d[f'P_eq_{g}'] = num(AGG['P'][(g, 'eq', c)], 6)
        d[f'rank_P_eq_{g}'] = RK[(g, 'eq')].get(c, '')
    d['Z_wq_comb'] = num(AGG['Z'][('comb', 'wq', c)], 4)
    d['rank_Z_wq_comb'] = RK[('Z_comb', 'wq')].get(c, '')
    d['ZR_wq_comb'] = num(AGG['ZR'][('comb', 'wq', c)], 4)
    d['rank_ZR_wq_comb'] = RK[('ZR_comb', 'wq')].get(c, '')
    for k in W_TIME:
        d[f'P_{k}'] = num(AGG['P'].get((k, 'wq', c)), 6)
        d[f'rank_P_{k}'] = RK[(k, 'wq')].get(c, '')
    rows_out.append(d)

# ---- 空值语义：未参与主排序的学校，其「多年聚合」列一律留空 ----
# 依据 design 3.5 与 spec/data/field-conventions.md「缺失值不得用 0 代替」。
# 逐年诊断列（score_/quota_/mean_score_base3_/rank_base3_/quota3_/P_/Z_/ZR_ 逐年）
# **必须保留**——新开办学校的单年位次与均分正是 R3 要披露的内容。
AGG_COLS = ['quota3_avg', 'quota_all_avg', 'rel_avg', 'SEN', 'shift_wq_eq',
            'mean_rank_base3_wq_avg', 'mean_rank_base3_wq_median',
            'mean_rank_base3_wq_var', 'mean_rank_base3_eq_avg',
            'mean_rank_base3_w_linear', 'mean_rank_base3_w_exp',
            'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq',
            'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq']
for _p in ('P_wq', 'P_eq'):
    AGG_COLS += [f'{_p}_{g}' for g in ('all', 'head', 'tail', 'comb')]
AGG_COLS += ['Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb']
AGG_COLS += [x for k in W_TIME for x in (f'P_{k}', f'rank_P_{k}')]

_n_blank = 0
for _d in rows_out:
    if _d['row_type'] == 'ranked':
        continue
    for _col in AGG_COLS:
        if _d.get(_col) not in ('', None):
            _d[_col] = ''
            _n_blank += 1
print(f'空值语义：{len(schools) - len(TABLE)} 所非入榜学校共清空 {_n_blank} 个多年聚合格'
      f'（逐年诊断列保留）')

with open(f'{D_A}/宽表-初中水平-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=wide_cols)
    w.writeheader()
    for d in sorted(rows_out, key=lambda d: (d['rank_P_wq'] if d['rank_P_wq'] != '' else 999)):
        w.writerow({k: d.get(k, '') for k in wide_cols})
print(f'宽表 {len(wide_cols)} 列 × {len(rows_out)} 行')

# ---------- 输出 2：趋势分析 ----------
tcols = (['junior_high_school', 'n_years', 'rel_first', 'rel_last', 'delta_rel',
          'sen', 'sen_ols', 'spearman', 'sen_recent3']
          + [f'convB_b_{y}' for y in YEARS[1:]] + [f'convB_r2_{y}' for y in YEARS[1:]]
          + [f'convB_resid_z_{y}' for y in YEARS[1:]]
          + ['convB_zmax', 'convB_beyond_n',
             'convA_pred', 'convA_resid', 'convA_resid_z', 'convA_beyond'])
with open(f'{D_A}/趋势分析-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=tcols)
    w.writeheader()
    for c in sorted(TABLE, key=lambda c: RK[('all', 'wq')][c]):
        t = trend[c]
        zs = [CONV_B[(c, y)]['z'] for y in YEARS[1:] if (c, y) in CONV_B]
        # convA/convB 只在 RANKED（五年全勤样本）上回归，4 年校这些列留空
        row = {'junior_high_school': c, 'n_years': COV(c),
               'rel_first': num(t['rel_first'], 3), 'rel_last': num(t['rel_last'], 3),
               'delta_rel': num(t['delta_rel'], 3), 'sen': num(t['sen'], 4),
               'sen_ols': num(t['sen_ols'], 4), 'spearman': num(t['spearman'], 4),
               'sen_recent3': num(t['sen_recent3'], 4),
               'convB_zmax': num(max(zs, key=abs), 3) if zs else '',
               'convB_beyond_n': sum(1 for z in zs if abs(z) >= 1),
               'convA_pred': num(t.get('convergence_pred'), 3),
               'convA_resid': num(t.get('residual'), 3),
               'convA_resid_z': num(t.get('residual_z'), 3),
               'convA_beyond': t.get('beyond_convergence', '')}
        for y in YEARS[1:]:
            cb = CONV_B.get((c, y))
            row[f'convB_b_{y}'] = num(cb['b'], 4) if cb else ''
            row[f'convB_r2_{y}'] = num(cb['r2'], 4) if cb else ''
            row[f'convB_resid_z_{y}'] = num(cb['z'], 3) if cb else ''
        w.writerow(row)

# ---------- 输出 3：rank-标准化 ----------
by_name = {d['junior_high_school']: d for d in rows_out}
rcols = ['junior_high_school', 'junior_high_school_former_names',
         'junior_high_school_code', 'ownership', 'row_type', 'n_years', 'ranked',
         'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
         'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq', 'Z_eq', 'ZR_eq',
         'mean_rank_wq_avg', 'mean_rank_eq_avg', 'rel_avg', 'SEN']
with open(f'{D_A}/rank-标准化-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=rcols)
    w.writeheader()
    for c in schools:
        d = by_name[c]
        w.writerow({'junior_high_school': c,
                    'junior_high_school_former_names': d['junior_high_school_former_names'],
                    'junior_high_school_code': d['junior_high_school_code'],
                    'ownership': d['ownership'], 'row_type': d['row_type'],
                    'n_years': d['years_included'],
                    'ranked': d['ranked'], 'P_wq': d['P_wq'], 'rank_P_wq': d['rank_P_wq'],
                    'P_eq': d['P_eq'], 'rank_P_eq': d['rank_P_eq'],
                    'shift_wq_eq': d['shift_wq_eq'], 'Z_wq': d['Z_wq'], 'ZR_wq': d['ZR_wq'],
                    'rank_Z_wq': d['rank_Z_wq'], 'rank_ZR_wq': d['rank_ZR_wq'],
                    'Z_eq': '' if d['row_type'] != 'ranked' else num(AGG['Z'][('all', 'eq', c)], 4),
                    'ZR_eq': '' if d['row_type'] != 'ranked' else num(AGG['ZR'][('all', 'eq', c)], 4),
                    'mean_rank_wq_avg': d['mean_rank_base3_wq_avg'],
                    'mean_rank_eq_avg': d['mean_rank_base3_eq_avg'],
                    'rel_avg': d['rel_avg'], 'SEN': d['SEN']})

# ---------- 输出 4：rank-多口径总表（入榜 28 所 + 新开办 4 所 = 32 行） ----------
mcols = ['junior_high_school', 'junior_high_school_former_names', 'row_type', 'n_years',
         'P_wq_comb', 'rank_P_wq_comb', 'P_wq_all', 'rank_P_wq_all',
         'P_wq_head', 'rank_P_wq_head', 'P_wq_tail', 'rank_P_wq_tail',
         'P_eq_comb', 'rank_P_eq_comb', 'P_eq_all', 'rank_P_eq_all',
         'P_eq_head', 'rank_P_eq_head', 'P_eq_tail', 'rank_P_eq_tail',
         'shift_comb_wq_eq', 'Z_wq_comb', 'rank_Z_wq_comb',
         'ZR_wq_comb', 'rank_ZR_wq_comb',
         'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp',
         'P_recent3', 'rank_P_recent3', 'P_recent2', 'rank_P_recent2',
         'mean_rank_wq_avg', 'quota3_avg', 'quota_all_avg', 'SEN']


def _mkey(d):
    """入榜学校按 rank_P_wq_comb 升序在前，新开办学校统一排在后面。"""
    r = d.get('rank_P_wq_comb')
    return (0 if d['row_type'] == 'ranked' else 1,
            r if r not in ('', None) else 999)


with open(f'{D_A}/rank-多口径总表-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=mcols)
    w.writeheader()
    for d in sorted([r for r in rows_out
                     if r['row_type'] in ('ranked', 'new_school')], key=_mkey):
        if d['row_type'] == 'ranked':
            d['shift_comb_wq_eq'] = (RK[('comb', 'eq')][d['junior_high_school']]
                                     - d['rank_P_wq_comb'])
        d['n_years'] = d['years_included']
        w.writerow({k: d.get(k, '') for k in mcols})
print(f'总表 {len(TABLE) + len(NEW)} 行（入榜 {len(TABLE)} + 新开办 {len(NEW)}）')

# ---------- 输出 5：rank-加权敏感性 ----------
scols = ['junior_high_school', 'n_years', 'P_wq', 'P_lin', 'P_exp', 'P_recent3',
         'rank_eq', 'rank_lin', 'rank_exp', 'rank_recent3',
         'shift_lin', 'shift_exp', 'shift_recent3']
with open(f'{D_A}/rank-加权敏感性-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=scols)
    w.writeheader()
    for c in sorted(TABLE, key=lambda c: RK[('all', 'wq')][c]):
        d = by_name[c]
        r = {k: RK[(k, 'wq')][c] for k in W_TIME}
        w.writerow({'junior_high_school': c, 'n_years': d['years_included'],
                    'P_wq': d['P_wq'], 'P_lin': d['P_lin'], 'P_exp': d['P_exp'],
                    'P_recent3': d['P_recent3'], 'rank_eq': d['rank_P_wq'],
                    'rank_lin': r['lin'], 'rank_exp': r['exp'], 'rank_recent3': r['recent3'],
                    'shift_lin': r['lin'] - d['rank_P_wq'],
                    'shift_exp': r['exp'] - d['rank_P_wq'],
                    'shift_recent3': r['recent3'] - d['rank_P_wq']})

# ---------- 输出 6：单线视角（全部 8 条线，含委属线） ----------
NAME = {c: f for _, c, f, _ in HS}
lrows = []
for s in schools:
    for _, code, _, tier in HS:
        pairs = [(y, S[(s, code, y)]) for y in YEARS if (s, code, y) in S]
        if not pairs:
            continue
        rk, qtot = [], 0
        for y, v in pairs:
            vals = {x: S[(x, code, y)] for x in schools if (x, code, y) in S}
            b = sum(1 for w in vals.values() if w > v)
            e = sum(1 for w in vals.values() if w == v)
            rk.append(b + (e + 1) / 2)
            qtot += Q.get((s, code, y), 0)
        lrows.append({'junior_high_school': s, 'senior_high_school': NAME[code],
                      'senior_high_school_code': code, 'tier': tier, 'n_years': len(pairs),
                      'avg_rank_line': num(st.fmean(rk), 2),
                      'avg_score_line': num(st.fmean([v for _, v in pairs]), 2),
                      'quota_line_total': qtot, 'quota_line_avg': num(qtot / len(pairs), 2)})
lrows.sort(key=lambda r: (r['tier'], r['senior_high_school_code'], r['avg_rank_line']))
with open(f'{D_A}/单线视角-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(lrows[0].keys()))
    w.writeheader()
    w.writerows(lrows)
print(f'单线视角 {len(lrows)} 行（覆盖 8 条线）')

# ---------- 控制台 ----------
print(f'\n=== 主口径（all 加权）排名 前 10｜入榜 {len(TABLE)} 所 ===')
print(f"{'名':>3} {'初中':<26}{'P_wq':>8}{'rel':>7}{'名额':>7}{'SEN':>8}{'等权':>5}{'Z':>4}")
for c in sorted(TABLE, key=lambda c: RK[('all', 'wq')][c])[:10]:
    d = by_name[c]
    f4 = lambda v: (f'{v:.4f}' if isinstance(v, (int, float)) else str(v))
    f2 = lambda v: (f'{v:.2f}' if isinstance(v, (int, float)) else str(v))
    print(f"  {d['rank_P_wq']:>2} {c:<26}{f4(d['P_wq']):>8}{f2(d['rel_avg']):>7}"
          f"{f2(d['quota3_avg']):>7}{f2(d['SEN']):>8}{d['rank_P_eq']:>5}{d['rank_Z_wq']:>4}")
print('\n=== 逐年池量与 rel 基准（all, wq）===')
for y in YEARS:
    print(f'  {y}: n={YEAR_N[("all", "wq", y)]}  rel 中位基准={REL_MED[y]:.2f}  '
          f'区属线数={len([c for c in QU3 if any((s, c, y) in S for s in schools)])}')
print(f'\n头尾分组可用年：head={[y for y in YEARS if YEAR_N[("head", "wq", y)]]} '
      f'tail={[y for y in YEARS if YEAR_N[("tail", "wq", y)]]}')
print(f'收敛回归 b={b:+.3f} R²={r2:.3f}｜'
      f'ρ(名额, P_wq)={spearman([F(by_name[c]["quota3_avg"]) for c in TABLE], [AGG["P"][("all", "wq", c)] for c in TABLE]):+.3f}')
