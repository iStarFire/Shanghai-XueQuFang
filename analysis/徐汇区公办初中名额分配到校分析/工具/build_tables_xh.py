#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""徐汇区名额到校分析 —— 阶段 4：三张新表

产出：收敛指标 / 收敛趋势检验 / 趋势分类（三张 CSV）。

⛔ 三处**不得**照搬普陀的错误（普陀本轮已犯，见其脚本注释）：
1. **Bonferroni 项数 = `len(FIXED)`**（参与 MK 的学校数），⛔ 不得写死 14 ——
   普陀曾照搬嘉定**注释**的「7 指标 + 7 方向检验」，而嘉定代码
   `build_q2q3_jd.py:265` 实为 `m = len(RANKED)`。徐汇 MK 是**每校一次**。
2. **检验力天花板用精确推导**：`n=5 ⇒ |S| ≤ 10、Var(S)=16.667 ⇒ |z| ≤ 2.205`，
   Bonferroni 后需 `|z| > z_{1-α/(2m)}`；若前者 < 后者则 0 所显著是**数学必然**。
3. `t(0.975, df=3)` 用**精确值 3.182446**（普陀曾用 3.182 近似使 CI 差 1.15e-4）。

固定样本 = **五年全勤**。徐汇 24 所入榜校里有 1 所四年制（徐汇南校），
故 FIXED = 23 所，逐年恒定。
"""
import csv
import math
import statistics as st
import sys
from collections import Counter
from pathlib import Path

D_A = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xh_common import midrank  # noqa: E402  共用平均秩（implement 6.1）

YEARS = ['2022', '2023', '2024', '2025', '2026']
MIN_YEARS_FIXED = 5
SEN_THRESH = 1.0
ALPHA = 0.05
T975_DF3 = 3.182446
METRICS = ('cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm')


def load(p):
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def num(v, nd=6):
    return '' if v is None else (f'{v:.{nd}f}' if nd is not None else str(v))


def pctl(xs, p):
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def gini(xs):
    s = sorted(xs)
    n = len(s)
    tot = sum(s)
    if not tot or not n:
        return None
    cum = sum((i + 1) * v for i, v in enumerate(s))
    return (2 * cum - (n + 1) * tot) / (n * tot)


def _betai(a, b, x, tol=1e-15, maxit=500):
    """正则化不完全 beta I_x(a,b) = x^a/(a·B(a,b)) · ₂F₁(a, 1-b; a+1; x)

    ⛔ **不含 (1-x)^b 因子** —— 加上它会让 a=b=1 时得到 x(1-x) 而非 x。
    ⚠️ 曾用「Lentz 连分数」实现，两处出错（`bt` 与 `betacf` 的配合），
       致 p 值系统性偏小约 18%（t=3.182446 给 0.0413 而正确值 0.05），
       且**不报错、不为空、不影响 CI**（CI 走的是 T975_DF3 常量）⇒ 属静默错误。
       改用超几何级数后与 df=3 的解析解
       `I_x(1.5,0.5) = (2/π)(arcsin√x − √(x(1−x)))` 吻合到 3.6e-10。

    级数项递推：t_0 = 1，t_{n+1} = t_n · (a+n)(1-b+n)/((a+1+n)(n+1)) · x
    """
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(a * math.log(x) - math.lgamma(a) - math.lgamma(b)
                     + math.lgamma(a + b)) / a
    term, s = 1.0, 1.0
    for n in range(maxit):
        term *= (a + n) * (1.0 - b + n) / ((a + 1.0 + n) * (n + 1)) * x
        s += term
        if abs(term) < tol * abs(s):
            break
    return front * s



def t_sf_2tail(t, df):
    """双尾 p = I_{df/(df+t²)}(df/2, 1/2)。"""
    if t <= 0:
        return 1.0
    return max(0.0, min(1.0, _betai(df / 2, 0.5, df / (df + t * t))))


# ---- 实现自检（⛔ 缺了这段，上面的 bug 不会暴露）----
# 曾用「Lentz 连分数」实现不完全 beta，两处出错（`bt` 取 B 而非 1/B 的配合、
# 递推首项写成 1.0），致 p 值系统性偏小约 18%：t=3.182446 得 0.0413 而正确值 0.05。
# 该错误**不抛异常、不产出空值**，且 CI 走 T975_DF3 常量不受影响 ⇒ 属静默错误。
# 下列断言把它钉死：I_x(1,1)=x（可解析）、df=3 三点合 t 表值、反解回 T975_DF3。
assert abs(_betai(1, 1, 0.3) - 0.3) < 1e-12, 'I_x(1,1) 应 = x'
assert abs(_betai(1, 1, 0.7) - 0.7) < 1e-12, 'I_x(1,1) 应 = x'
for _t, _p in ((2.353363, 0.10), (3.182446, 0.05), (4.540703, 0.02)):
    _x = 3 / (3 + _t * _t)
    _th = math.asin(math.sqrt(_x))
    _exact = (2 / math.pi) * (_th - math.sqrt(_x * (1 - _x)))   # df=3 解析解
    _got = t_sf_2tail(_t, 3)
    assert abs(_got - _p) < 1e-6, f't_sf_2tail({_t},3)={_got:.6f} 应≈{_p}'
    assert abs(_got - _exact) < 1e-9, f'与 df=3 解析解不符：{_got} vs {_exact}'
_lo, _hi = 0.0, 80.0
for _ in range(200):
    _mid = (_lo + _hi) / 2
    if t_sf_2tail(_mid, 3) > 0.05:
        _lo = _mid
    else:
        _hi = _mid
assert abs((_lo + _hi) / 2 - T975_DF3) < 1e-5, \
    f'反解 t(0.975,3)={(_lo+_hi)/2:.6f} 与 T975_DF3={T975_DF3} 不符'
print(f'   t 分布自检通过（I_x(1,1)=x；df=3 三点合表值；反解 t={(_lo+_hi)/2:.6f}）')


def ols(xs, ys):
    n = len(xs)
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sd = math.sqrt(sum(r * r for r in resid) / (n - 2)) if n > 2 else 0.0
    se = sd / math.sqrt(sxx) if sxx > 0 else None
    t = b / se if se else None
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy ** 2) / (sxx * syy) if sxx > 0 and syy > 0 else None
    p = t_sf_2tail(abs(t), n - 2) if t is not None else None
    return {'b': b, 'se': se, 't': t, 'p': p, 'r2': r2, 'n': n}


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_sdf(p):
    """标准正态分位（反 CDF），Acklam 有理近似，|误差| < 1.15e-9。"""
    if p <= 0 or p >= 1:
        raise ValueError('p 必须落在 (0,1)，实为 %r' % p)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    else:
        # 中央区：Acklam 原式用 r = q²（⛔ 不是 0.25 —— 写错会让 sdf(0.975)
        # 从 1.959964 偏到 2.459103，进而算错 z_need 并使天花板断言失效）
        q = p - 0.5
        r = q * q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
            (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    # 一次 Halley 修正
    e = _norm_cdf(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def mk_test(ys):
    n = len(ys)
    S = sum((ys[j] > ys[i]) - (ys[j] < ys[i])
            for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18
    z = (S - 1) / math.sqrt(var) if S > 0 else ((S + 1) / math.sqrt(var) if S < 0 else 0.0)
    return S, z, (2 * (1 - _norm_cdf(abs(z))) if z else 1.0)


# ================= 载入宽表 =================
W = load(D_A / '宽表-初中水平-徐汇区-2022-2026.csv')
RANKED = [r for r in W if r['row_type'] == 'ranked']
FIXED = [r for r in RANKED if int(r['years_included']) == MIN_YEARS_FIXED]
FIXED_NAMES = {r['junior_high_school'] for r in FIXED}
#: 收敛指标固定样本逐年值（只用 FIXED，避免新增校进池造成构成效应）
XS = {y: [float(r['mean_score_base_%s' % y]) for r in FIXED
          if r['mean_score_base_%s' % y] not in ('', None)] for y in YEARS}
#: 当年公办入榜池（用于量化构成效应：池外学校的分位均值）
POOL = {y: [r for r in RANKED if r['mean_score_base_%s' % y] not in ('', None)]
        for y in YEARS}
print('入榜 %d 所｜固定样本（五年全勤）%d 所' % (len(RANKED), len(FIXED)))

# ================= 4.1 收敛指标 =================
rows2 = []
for y in YEARS:
    xs = XS[y]
    med = st.median(xs)
    met = {'sigma': st.pstdev(xs), 'cv': st.pstdev(xs) / med,
           'iqr_norm': (pctl(xs, 75) - pctl(xs, 25)) / med, 'gini': gini(xs),
           'r90_10_norm': (pctl(xs, 90) - pctl(xs, 10)) / med,
           'range_norm': (max(xs) - min(xs)) / med,
           'mad_norm': st.fmean([abs(v - med) for v in xs]) / med}
    pool = POOL[y]
    rk = midrank([(r['junior_high_school'], float(r['mean_score_base_%s' % y]))
                  for r in pool])
    out = [1 - (rk[r['junior_high_school']] - 1) / (len(pool) - 1)
           for r in pool if r['junior_high_school'] not in FIXED_NAMES]
    rows2.append({'year': y, 'n_fixed': len(xs), 'pool_n': len(pool),
                  'pool_median': num(st.median([float(r['mean_score_base_%s' % y])
                                                for r in pool]), 3),
                  'outside_n': len(out),
                  'outside_pct_mean': num(st.fmean(out), 4) if out else '',
                  **{k: num(met[k], 6) for k in ('sigma',) + METRICS}})
_nf = {r['n_fixed'] for r in rows2}
assert _nf == {len(FIXED)}, '固定样本逐年不一致：%s（应恒为 %d）' % (_nf, len(FIXED))
print('4.1 固定样本 %d 所，五年恒定 ✓｜池外校数：%s'
      % (len(FIXED), [r['outside_n'] for r in rows2]))

# ================= 4.2 收敛趋势检验 =================
rows3 = []
xs_t = list(range(len(YEARS)))
for k in ('sigma',) + METRICS:
    o = ols(xs_t, [float(r[k]) for r in rows2])
    ci_lo = num(o['b'] - T975_DF3 * o['se'], 8)
    ci_hi = num(o['b'] + T975_DF3 * o['se'], 8)
    rows3.append({'metric': k, 'slope_b': num(o['b'], 7), 'se': num(o['se'], 7),
                  't': num(o['t'], 4), 'p': num(o['p'], 6), 'r2': num(o['r2'], 6),
                  'n_obs': o['n'], 'df': o['n'] - 2, 'ci_lo': ci_lo, 'ci_hi': ci_hi,
                  'v2022': rows2[0][k], 'v2026': rows2[-1][k]})
    assert all(rows3[-1][c] != '' for c in
               ('slope_b', 'se', 't', 'p', 'r2', 'ci_lo', 'ci_hi')), \
        '%s 的回归输出有整列空值（普陀曾致 slope_b 整列静默为空）' % k
    cross = float(ci_lo) * float(ci_hi) < 0
    print('  %-12s 2022=%.5f 2026=%.5f b=%+.5f p=%.4f CI=[%+.5f,%+.5f] %s'
          % (k, float(rows2[0][k]), float(rows2[-1][k]), o['b'], o['p'],
             float(ci_lo), float(ci_hi), '跨0⇒无法判定' if cross else ''))

# ================= 4.3 趋势分类 =================
# Bonferroni 校正项数 = **参与 MK 检验的学校数**，⛔ 不是固定 14。
MK_M = len(FIXED)
assert MK_M == len(FIXED) == 23, 'MK_M 必须等于 FIXED 数'
rows4 = []
for r in FIXED:
    rels = [(y, float(r['rel_%s' % y])) for y in YEARS
            if r['rel_%s' % y] not in ('', None)]
    sen = ((rels[-1][1] - rels[0][1]) / (int(rels[-1][0]) - int(rels[0][0]))) \
        if len(rels) >= 2 else None
    p3 = [(y, v) for y, v in rels if y >= '2024']
    sen3 = ((p3[-1][1] - p3[0][1]) / (int(p3[-1][0]) - int(p3[0][0]))) \
        if len(p3) >= 2 else None
    ys = [v for _, v in rels]
    S, z, p = mk_test(ys)
    pb = min(1.0, p * MK_M)
    cls = ('数据不足' if sen is None else
           '明显上升' if sen >= SEN_THRESH else
           '明显下降' if sen <= -SEN_THRESH else '基本持平')
    rows4.append({'junior_high_school': r['junior_high_school'],
                  'junior_high_school_code': r['junior_high_school_code'],
                  'row_type': r['row_type'], 'n_years': r['years_included'],
                  'trend_class': cls, 'sen': num(sen, 4), 'sen_recent3': num(sen3, 4),
                  'rel_first': num(rels[0][1], 4) if rels else '',
                  'rel_last': num(rels[-1][1], 4) if rels else '',
                  'delta_rel': num(rels[-1][1] - rels[0][1], 4) if len(rels) >= 2 else '',
                  'mk_S': S, 'mk_z': num(z, 4), 'mk_p': num(p, 4),
                  'mk_p_bonferroni': num(pb, 4),
                  'sig_uncorrected': '是' if p < ALPHA else '否',
                  'sig_bonferroni': '是' if pb < ALPHA else '否'})
print('4.3 分类（|SEN|≥%s，MK 校正 ×%d）：%s'
      % (SEN_THRESH, MK_M, dict(Counter(r['trend_class'] for r in rows4))))

# ---- 判定：分类只覆盖 FIXED（五年全勤），且全部 ranked ----
assert all(int(r['n_years']) == MIN_YEARS_FIXED for r in rows4), '分类覆盖了非五年全勤学校'
assert all(r['row_type'] == 'ranked' for r in rows4), '分类混入了非 ranked 行'
for c in ('sen', 'rel_first', 'rel_last', 'delta_rel', 'mk_S', 'mk_z', 'mk_p',
          'mk_p_bonferroni'):
    assert all(r[c] != '' for r in rows4), '%s 整列为空' % c

# ---- 检验力天花板的**精确推导** + 三条断言 ----
n_mk = int(rows4[0]['n_years'])
S_max = n_mk * (n_mk - 1) / 2
var_s = n_mk * (n_mk - 1) * (2 * n_mk + 5) / 18
z_max = (S_max - 1) / math.sqrt(var_s)
p_floor = 2 * (1 - _norm_cdf(z_max))
alpha_b = ALPHA / MK_M
z_need = _norm_sdf(1 - alpha_b / 2)
assert z_max < z_need, (
    '天花板断言失效：|z|max=%.3f ≥ 所需 %.3f，本可显著，「0 所显著」结论需重审'
    % (z_max, z_need))
assert all(r['sig_bonferroni'] == '否' for r in rows4), \
    '有学校通过 Bonferroni 校正，与天花板结论矛盾'
_pmin = min(float(r['mk_p']) for r in rows4)
assert _pmin >= p_floor - 1e-9, \
    '实测最小 mk_p=%.4f < 理论下界 %.4f，MK 计算或 n 取值有误' % (_pmin, p_floor)
print('   天花板：n=%d 时 |S|≤%d、Var(S)=%.3f ⇒ |z|≤%.3f ⇒ p≥%.4f；'
      'Bonferroni α=%.6f（%d 项）需 |z|>%.3f ⇒ 0 所显著是数学必然'
      % (n_mk, S_max, var_s, z_max, p_floor, alpha_b, MK_M, z_need))
print('   实测最小 mk_p=%.4f ≥ 理论下界 %.4f ✓' % (_pmin, p_floor))
print('   未经校正显著：%d 所｜校正后：%d 所'
      % (sum(1 for r in rows4 if r['sig_uncorrected'] == '是'),
         sum(1 for r in rows4 if r['sig_bonferroni'] == '是')))
_flip = [r for r in rows4 if r['sen_recent3'] and r['sen']
         and float(r['sen']) * float(r['sen_recent3']) < 0]
print('   五年与近三年方向相反：%d 所 → %s'
      % (len(_flip), '、'.join(r['junior_high_school'].replace('上海市', '')
                              for r in _flip)))


# ================= 落盘（全部断言通过后）====================
def dump(name, rows, cols):
    p = D_A / name
    with open(p, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('  写出 %s（%d 行 × %d 列）' % (name, len(rows), len(cols)))


print('落盘：')
dump('收敛指标-徐汇区-2022-2026.csv', rows2,
     ['year', 'n_fixed', 'pool_n', 'pool_median', 'outside_n', 'outside_pct_mean']
     + ['sigma'] + list(METRICS))
dump('收敛趋势检验-徐汇区-2022-2026.csv', rows3,
     ['metric', 'slope_b', 'se', 't', 'p', 'r2', 'n_obs', 'df', 'ci_lo', 'ci_hi',
      'v2022', 'v2026'])
dump('趋势分类-徐汇区-2022-2026.csv', rows4,
     ['junior_high_school', 'junior_high_school_code', 'row_type', 'n_years',
      'trend_class', 'sen', 'sen_recent3', 'rel_first', 'rel_last', 'delta_rel',
      'mk_S', 'mk_z', 'mk_p', 'mk_p_bonferroni', 'sig_uncorrected', 'sig_bonferroni'])
print('阶段 4 三表完成')
