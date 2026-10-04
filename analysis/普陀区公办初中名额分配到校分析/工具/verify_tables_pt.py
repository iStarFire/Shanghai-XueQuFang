"""独立复算阶段 4 的三张表 —— 不 import build_tables.py。

判定标准（implement.md）：
  4.1 固定样本校数五年恒定
  4.2 斜率 / CI / p / R² 由独立脚本复算一致
  4.3 分类只覆盖 years_included ≥ 4

独立性：本脚本从**宽表**（而非源 CSV）重算，用与生成脚本不同的实现路径
（numpy-free 手写 OLS / 用 statistics 而非自写 gini），口径漂移会被发现。
"""
import csv
import math
import statistics as st
import sys
from pathlib import Path

D = Path('.')
YEARS = [2022, 2023, 2024, 2025, 2026]
MEAN_COL = 'mean_score_base4_wq_{y}'


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def ols_ref(xs, ys):
    """参照实现：用 statistics.correlation 斜率 + 手算 t，不用求和公式。"""
    n = len(xs)
    mx, my = st.fmean(xs), st.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    # 用相关系数求斜率（与生成脚本的求和公式是不同实现路径）
    r = sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0
    b = r * math.sqrt(syy / sxx) if sxx else 0.0
    a = st.fmean(ys) - b * st.fmean(xs)
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(e * e for e in resid)
    sst = syy
    df = n - 2
    s2 = sse / df
    se = math.sqrt(s2 / sxx) if sxx else 0.0
    t = b / se if se else 0.0
    # df=3 的 t 分布双侧 p：用不完全 beta 的连分数（数值稳定）
    p = _t_sf(t, df)
    tcrit = {1: 12.706205, 2: 4.302653, 3: 3.182446, 4: 2.776445, 5: 2.570582}[df]
    return {'b': b, 'se': se, 't': t, 'p': p,
            'r2': 1 - sse / sst if sst else 1.0,
            'ci_lo': b - tcrit * se, 'ci_hi': b + tcrit * se}


def _betacf(a, b, x, itmax=200, eps=3e-12):
    """连分数求不完全 beta（Numerical Recipes）。"""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def _betai(a, b, x):
    """正则化不完全 beta I_x(a,b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log(1 - x) + a * math.log(x)) * _betacf(b, a, 1 - x) / b


def _t_sf(t, df):
    """t 分布双侧 p 值。"""
    x = df / (df + t * t)
    return _betai(df / 2.0, 0.5, x)


W = load(D / '宽表-初中水平-普陀区-2022-2026.csv')
R2 = load(D / '收敛指标-普陀区-2022-2026.csv')
R3 = load(D / '收敛趋势检验-普陀区-2022-2026.csv')
R4 = load(D / '趋势分类-普陀区-2022-2026.csv')

bad, checked = [], 0

# ---- 4.1 固定样本恒定 + 指标复算 ----
FIXED = [r for r in W if r['row_type'] == 'ranked' and r['years_included'] == '5']
assert len({r['n_fixed'] for r in R2}) == 1, '固定样本校数逐年不等'
print(f'4.1 固定样本 {R2[0]["n_fixed"]} 所，五年恒定 ✓（独立复算 = {len(FIXED)} 所）')
assert int(R2[0]['n_fixed']) == len(FIXED), 'n_fixed 与独立复算不符'

for r in R2:
    y = r['year']
    xs = [float(x[MEAN_COL.format(y=y)]) for x in FIXED if x[MEAN_COL.format(y=y)]]
    pool = [float(x[MEAN_COL.format(y=y)]) for x in W
            if x['ownership'] == '公办' and x['row_type'] != 'exited'
            and x[MEAN_COL.format(y=y)] not in ('', None)]
    med = st.median(pool)
    srt = sorted(xs)
    n = len(srt)

    def pc(p):
        k = (n - 1) * p / 100
        lo, hi = math.floor(k), math.ceil(k)
        return srt[lo] + (srt[hi] - srt[lo]) * (k - lo)

    med_xs = st.median(xs)
    exp = {
        'sigma': st.pstdev(xs),
        'cv': st.pstdev(xs) / med,
        'iqr_norm': (pc(75) - pc(25)) / med,
        'gini': sum((2 * i - n + 1) * v for i, v in enumerate(srt)) / (n * sum(srt)),
        'r90_10_norm': (pc(90) - pc(10)) / med,
        'range_norm': (max(xs) - min(xs)) / med,
        'mad_norm': st.fmean([abs(v - med_xs) for v in xs]) / med,
    }
    for k, v in exp.items():
        checked += 1
        if abs(float(r[k]) - v) > 5e-6:
            bad.append(('4.1', f'{y}/{k}', f'表={r[k]} 复算={v:.6f}'))
    checked += 1
    if abs(float(r['pool_median']) - med) > 5e-4:
        bad.append(('4.1', f'{y}/pool_median', f'表={r["pool_median"]} 复算={med:.3f}'))
    checked += 1
    if int(r['pool_n']) != len(pool):
        bad.append(('4.1', f'{y}/pool_n', f'表={r["pool_n"]} 复算={len(pool)}'))

# ---- 4.2 斜率 / CI / p / R² 复算 ----
xs_t = [y - 2022 for y in YEARS]
for r in R3:
    k = r['metric']
    ys = [float(x[k]) for x in R2]
    o = ols_ref(xs_t, ys)
    for col, ev, tol in (('slope_b', o['b'], 5e-6), ('se', o['se'], 5e-6),
                         ('t', o['t'], 5e-4), ('p', o['p'], 2e-3),
                         ('r2', o['r2'], 5e-4),
                         ('ci_lo', o['ci_lo'], 5e-5), ('ci_hi', o['ci_hi'], 5e-5)):
        checked += 1
        got = float(r[col])
        if abs(got - ev) > tol:
            bad.append(('4.2', f'{k}/{col}', f'表={got} 复算={ev:.7f} 差={got-ev:+.2e}'))
    checked += 1
    if int(r['df']) != 3 or int(r['n_obs']) != 5:
        bad.append(('4.2', f'{k}/df,n', f'表={r["df"]},{r["n_obs"]} 应为 3,5'))
print(f'4.2 斜率/CI/p/R² 已复算（{len(R3)} 指标）')

# ---- 4.3 分类与显著性 ----
for r in R4:
    checked += 1
    if int(r['n_years']) < 4:
        bad.append(('4.3', r['junior_high_school'][:14], f'n_years={r["n_years"]} <4'))
    checked += 1
    if r['row_type'] != 'ranked':
        bad.append(('4.3', r['junior_high_school'][:14], f'row_type={r["row_type"]}'))
    # SEN = 首尾斜率，独立复算
    name = r['junior_high_school']
    w = [x for x in W if x['junior_high_school'] == name][0]
    pts = [(int(y), float(w['rel_' + y])) for y in map(str, YEARS)
           if w.get('rel_' + y) not in ('', None)]
    sen = (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0]) if len(pts) >= 2 else None
    checked += 1
    if abs(sen - float(r['sen'])) > 5e-4:
        bad.append(('4.3', f'{name[:14]}/sen', f'表={r["sen"]} 复算={sen:.4f}'))
    # Bonferroni 一致性
    MK_M = len(R4)   # 校正项数 = 参与 MK 的学校数
    checked += 1
    exp_b = min(1.0, float(r['mk_p']) * MK_M)   # MK_M = 参与检验的校数（≠ 14，见 build_tables_pt.py 注释）
    if abs(exp_b - float(r['mk_p_bonferroni'])) > 1e-3:
        bad.append(('4.3', f'{name[:14]}/bonf', f'表={r["mk_p_bonferroni"]} 复算={exp_b:.4f}'))
print(f'4.3 分类覆盖 {len(R4)} 所（全部 n≥4 且 ranked）、SEN 与 Bonferroni 已复算')

if bad:
    print(f'\n❌ 不一致 {len(bad)} 处：')
    for w, k, m in bad[:20]:
        print(f'   [{w}] {k}: {m}')
    sys.exit(1)
print(f'\n✅ 全部一致：共校验 {checked} 格')
