# -*- coding: utf-8 -*-
"""普陀区宽表 / 趋势 / v2 标准化排名（2.3 计算）。

- 基线：区属 4 所（华二普陀/曹杨二中/晋元/宜川）——五年全勤，无断点（优于徐汇）
- 全口径：9 所（+委属 5 所：华二/上中/复附/交附/上师大）
- 逐年名次：当年全部有数据学校内、平均名次法（分高者名次小）
- v2 主口径：分位 P = 1-(rank-1)/(n-1)；Z/ZR 为辅
- 规模：区属名额与全口径名额逐年（计划表 2022–2026 五年齐）
- 趋势：rel = base4 均分 − 当年 CORE 中位；Sen 斜率；收敛回归（Δrel ~ rel_2022）；近 3 年 Sen
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
QU = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']
WEI = ['华东师范大学第二附属中学', '上海市上海中学', '复旦大学附属中学',
       '上海交通大学附属中学', '上海师范大学附属中学']
ALL9 = QU + WEI
W_LIN = {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5}
W_EXP = {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16}


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def fnum(v):
    return float(v) if v not in ('', None) else None


score = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')

S = {}
for r in score:
    S[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = fnum(r['min_score'])
P = {}
for r in plan:
    P[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = int(r['quota'])

schools = sorted({r['junior_high_school'] for r in score} | {r['junior_high_school'] for r in plan})

# ---- 逐年指标 ----
met = {}
for c in schools:
    for y in YEARS:
        q4 = sum(P.get((c, h, y), 0) for h in QU)
        qall = sum(P.get((c, h, y), 0) for h in ALL9)
        s4 = [S[(c, h, y)] for h in QU if (c, h, y) in S]
        sa = [S[(c, h, y)] for h in ALL9 if (c, h, y) in S]
        met[(c, y)] = {
            'quota4': q4, 'quota_all': qall,
            'mean_score_base4': st.fmean(s4) if s4 else None,
            'mean_score_all': st.fmean(sa) if sa else None,
            'pairs4': len(s4), 'pairs_all': len(sa),
        }

# ---- 逐年名次（平均名次法：分高者名次小）----
def rank_col(key):
    for c in schools:                     # 先置 None，避免后续 KeyError
        for y in YEARS:
            met[(c, y)]['rank_' + key] = None
    for y in YEARS:
        vals = {c: met[(c, y)][key] for c in schools if met[(c, y)][key] is not None}
        for c, v in vals.items():
            better = sum(1 for w in vals.values() if w > v)
            eq = sum(1 for w in vals.values() if w == v)
            met[(c, y)]['rank_' + key] = better + (eq + 1) / 2


rank_col('mean_score_base4')
rank_col('mean_score_all')

CORE = [c for c in schools
        if all(met[(c, y)]['mean_score_base4'] is not None for y in YEARS)]
print(f'学校总数 {len(schools)}，五年全勤（base4）{len(CORE)} 所')

# ---- 汇总与加权 ----
def wavg(c, key, w):
    num = den = 0.0
    for y in YEARS:
        v = met[(c, y)][key]
        if v is None:
            continue
        num += w[y] * v
        den += w[y]
    return num / den if den else None


wide = []
for c in schools:
    rb = [met[(c, y)]['rank_mean_score_base4'] for y in YEARS if met[(c, y)]['rank_mean_score_base4'] is not None]
    ra = [met[(c, y)]['rank_mean_score_all'] for y in YEARS if met[(c, y)]['rank_mean_score_all'] is not None]
    q4 = [met[(c, y)]['quota4'] for y in YEARS if met[(c, y)]['quota4']]
    wide.append({
        'junior_high_school': c,
        'years_included': len(rb),
        'years_list': ';'.join(str(y) for y in YEARS if met[(c, y)]['rank_mean_score_base4'] is not None),
        'quota4_avg': st.fmean(q4) if q4 else None,
        'quota_all_avg': st.fmean([met[(c, y)]['quota_all'] for y in YEARS]),
        'mean_rank_base4_avg': st.fmean(rb) if rb else None,
        'mean_rank_base4_median': st.median(rb) if rb else None,
        'mean_rank_base4_var': st.pvariance(rb) if len(rb) > 1 else None,
        'mean_rank_all_avg': st.fmean(ra) if ra else None,
        'mean_rank_base4_w_linear': wavg(c, 'rank_mean_score_base4', W_LIN),
        'mean_rank_base4_w_exp': wavg(c, 'rank_mean_score_base4', W_EXP),
    })

# ---- v2：分位 P / Z / ZR（区属基线上做，与徐汇 A8 一致）----
def iqr(v):
    s = sorted(v)
    return s[len(s) * 3 // 4] - s[len(s) // 4]


year_stat = {}
for y in YEARS:
    xs = [met[(c, y)]['mean_score_base4'] for c in schools
          if met[(c, y)]['mean_score_base4'] is not None]
    year_stat[y] = (len(xs), st.fmean(xs), st.pstdev(xs), st.median(xs), iqr(xs))

v2 = []
for c in schools:
    ps, zs, zrs, nys = [], [], [], []
    for y in YEARS:
        v = met[(c, y)]['mean_score_base4']
        k = met[(c, y)]['rank_mean_score_base4']
        if v is None:
            continue
        n, mu, sg, med, iq = year_stat[y]
        ps.append(1 - (k - 1) / (n - 1))
        zs.append((v - mu) / sg)
        zrs.append((v - med) / (iq / 1.349))
        nys.append(y)
    v2.append({
        'junior_high_school': c, 'n_years': len(ps),
        'P': st.fmean(ps) if ps else None,
        'Z': st.fmean(zs) if zs else None,
        'ZR': st.fmean(zrs) if zrs else None,
        'old_mean_rank': (st.fmean([met[(c, y)]['rank_mean_score_base4'] for y in nys])
                          if nys else None),
    })
ranked = [v for v in v2 if v['n_years'] >= 4]
for v in v2:
    v['ranked'] = int(v in ranked)
for key in ('P', 'Z', 'ZR'):
    srt = sorted(ranked, key=lambda v: -v[key])
    for i, v in enumerate(srt, 1):
        v['rank_' + key] = i
for i, v in enumerate(sorted([v for v in ranked if v['old_mean_rank'] is not None],
                             key=lambda v: v['old_mean_rank']), 1):
    v['rank_old'] = i          # 旧口径名次在入榜集合内排名（与 A8 一致）

# ---- 趋势（rel 相对 CORE 中位 + Sen + 收敛回归 + 近3年 Sen）----
def sen(vals):
    n = len(vals)
    slopes = []
    for i in range(n):
        for j in range(i + 1, n):
            slopes.append((vals[j] - vals[i]) / (j - i))
    return st.median(slopes) if slopes else None


def spearman(x, y):
    def rk(v):
        s = sorted(v)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in v]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


trend = []
rel_of = {}
for c in schools:
    navail = sum(1 for y in YEARS if met[(c, y)]['mean_score_base4'] is not None)
    if navail < 3:
        continue
    rel, yrs = [], []
    for y in YEARS:
        v = met[(c, y)]['mean_score_base4']
        if v is None:
            continue
        med = st.median([met[(cc, y)]['mean_score_base4'] for cc in CORE])
        rel.append(v - med)
        yrs.append(y)
    rel_of[c] = (yrs, rel)
    s5 = sen(rel)
    sp = spearman(yrs, rel)
    s3 = sen(rel[-3:]) if len(rel) >= 3 else None
    trend.append({
        'junior_high_school': c, 'n_years': len(rel),
        'rel_first': rel[0], 'rel_last': rel[-1], 'delta_rel': rel[-1] - rel[0],
        'sen': s5, 'spearman': sp, 'sen_recent3': s3,
    })

# 收敛回归：Δrel = a + b*rel_first（仅五年全勤）
X = [r for r in trend if r['n_years'] == 5]
xs = [r['rel_first'] for r in X]
ys = [r['delta_rel'] for r in X]
mx, my = st.fmean(xs), st.fmean(ys)
b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
a = my - b * mx
ss_tot = sum((y - my) ** 2 for y in ys)
ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
r2 = 1 - ss_res / ss_tot
resid = [y - (a + b * x) for x, y in zip(xs, ys)]
sd = st.pstdev(resid) or 1e-9
for r in X:
    pred = a + b * r['rel_first']
    r['convergence_pred'] = pred
    r['residual'] = r['delta_rel'] - pred
    r['residual_z'] = r['residual'] / sd
    r['beyond_convergence'] = abs(r['residual_z']) >= 1.0
print(f'收敛回归: b={b:.3f} 截距={a:.3f} R²={r2:.3f}（n={len(X)}）')

# ---- 落盘 ----
def w_csv(path, cols, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v)
                        for k, v in r.items()})
    print('写出', path)


w_csv(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv',
      ['junior_high_school', 'years_included', 'years_list', 'quota4_avg', 'quota_all_avg',
       'mean_rank_base4_avg', 'mean_rank_base4_median', 'mean_rank_base4_var',
       'mean_rank_all_avg', 'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp'],
      sorted(wide, key=lambda r: r['mean_rank_base4_avg'] if r['mean_rank_base4_avg'] else 99))
w_csv(f'{D_A}/rank-标准化-普陀区-2022-2026.csv',
      ['junior_high_school', 'n_years', 'P', 'Z', 'ZR', 'rank_P', 'rank_Z', 'rank_ZR',
       'old_mean_rank', 'rank_old', 'ranked'],
      sorted(v2, key=lambda v: (v.get('rank_P', 99) if v['ranked'] else 999)))
w_csv(f'{D_A}/趋势分析-普陀区-2022-2026.csv',
      ['junior_high_school', 'n_years', 'rel_first', 'rel_last', 'delta_rel',
       'sen', 'spearman', 'sen_recent3', 'convergence_pred', 'residual',
       'residual_z', 'beyond_convergence'],
      sorted(trend, key=lambda r: r['rel_first']))

print('\n== CORE 排名（按均名）==')
for i, r in enumerate(sorted([r for r in wide if r['years_included'] == 5],
                             key=lambda r: r['mean_rank_base4_avg']), 1):
    print(f"{i:>3} {r['junior_high_school']:<26} 均名{r['mean_rank_base4_avg']:.2f} "
          f"中位{r['mean_rank_base4_median']:.1f} 方差{r['mean_rank_base4_var']:.2f} "
          f"名额4={r['quota4_avg']:.1f} 名额9={r['quota_all_avg']:.1f}")
# ---- 收敛诊断（IQR / σ / 中位±5 分内占比）----
print('\n== 收敛诊断（CORE 31 所，base4 均分）==')
for y in YEARS:
    xs = sorted(met[(c, y)]['mean_score_base4'] for c in CORE)
    n = len(xs)
    med = st.median(xs)
    print(f'  {y}: n={n} IQR={xs[n*3//4]-xs[n//4]:.1f} σ={st.pstdev(xs):.2f} '
          f'±5分内={sum(1 for v in xs if abs(v-med)<=5)/n:.0%} '
          f'±10分内={sum(1 for v in xs if abs(v-med)<=10)/n:.0%}')

# ---- 规模分档（区属年均名额三分位），检验排序是否翻转 ----
qs = sorted(r['quota4_avg'] for r in wide if r['years_included'] == 5)
lo, hi = qs[len(qs)//3], qs[2*len(qs)//3]
def tier_of(q):
    return '小规模' if q <= lo else ('中规模' if q <= hi else '大规模')
print(f'\n== 规模分档（区属年均名额三分位；阈值 {lo:.1f} / {hi:.1f}）==')
flips = 0
for tname in ['大规模', '中规模', '小规模']:
    grp = sorted([r for r in wide if r['years_included'] == 5 and tier_of(r['quota4_avg']) == tname],
                 key=lambda r: r['mean_rank_base4_avg'])
    overall = {r['junior_high_school']: i for i, r in enumerate(
        sorted([r for r in wide if r['years_included'] == 5],
               key=lambda r: r['mean_rank_base4_avg']), 1)}
    print(f'  {tname}（{len(grp)} 所）:')
    for i, r in enumerate(grp, 1):
        flip = '' if overall[r['junior_high_school']] == overall[grp[0]['junior_high_school']] + i - 1 else ''
        print(f"    {i:>2} {r['junior_high_school']:<26} 均名{r['mean_rank_base4_avg']:.2f} "
              f"名额4={r['quota4_avg']:.1f}（全样本第 {overall[r['junior_high_school']]}）")

print('\n== v2 P 排名（前 3 与末 3）==')
srt = sorted([v for v in v2 if v['ranked']], key=lambda v: v['rank_P'])
for v in srt[:3] + srt[-3:]:
    print(f"  第{v['rank_P']:>2} {v['junior_high_school']:<26} P={v['P']:.3f} "
          f"Z={v['Z']:+.2f} ZR={v['ZR']:+.2f} 旧第{v.get('rank_old')}")
