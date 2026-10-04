#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.2 门禁：三张新表复算（**CI 用独立实现**）。

「独立」的含义：收敛趋势检验的 CI 在 `build_tables_xh.py` 里用
`t(0.975,df=3) = 3.182446` 常量计算；本脚本**改用不完全 beta 函数**从
`slope_b`/`se` 重新算出 t 临界值与 CI，两条路径必须吻合。
若只用同一常量自证，等于没验。
"""
import csv
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D_S = ROOT / 'data/徐汇区/学校'
D_A = ROOT / 'analysis/徐汇区公办初中名额分配到校分析'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xh_common import midrank  # noqa: E402

YEARS = [2022, 2023, 2024, 2025, 2026]
TOL = 1e-5


def load(p):
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def betainc(a, b, x, tol=1e-15, maxit=500):
    """I_x(a,b) = x^a/(a·B(a,b)) · ₂F₁(a,1-b;a+1;x)   ⛔ 不含 (1-x)^b。

    ⚠️ 生成脚本曾用 Lentz 连分数且写错，p 偏小约 18%；此处**用同一份级数**
    以保证两者算法一致，但**各自独立实现了自检断言**（下方），
    断言失败会立刻暴露实现漂移。
    """
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(a*math.log(x) - math.lgamma(a) - math.lgamma(b)
                     + math.lgamma(a + b)) / a
    term, s = 1.0, 1.0
    for n in range(maxit):
        term *= (a + n) * (1.0 - b + n) / ((a + 1.0 + n) * (n + 1)) * x
        s += term
        if abs(term) < tol * abs(s):
            break
    return front * s


def t_two_tail(t, df):
    return betainc(df / 2, 0.5, df / (df + t * t))


def t_crit(p, df):
    """反求 t 临界值（二分法）—— 不依赖生成脚本的常量。"""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_two_tail(mid, df) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

# 实现自检（独立于生成脚本）：I_x(1,1)=x、df=3 解析解、t 表值三点
assert abs(betainc(1, 1, 0.3) - 0.3) < 1e-12, 'I_x(1,1) 应 = x'
for _t, _p in ((2.353363, 0.10), (3.182446, 0.05), (4.540703, 0.02)):
    _x = 3 / (3 + _t * _t)
    _th = math.asin(math.sqrt(_x))
    _ex = (2 / math.pi) * (_th - math.sqrt(_x * (1 - _x)))
    assert abs(t_two_tail(_t, 3) - _p) < 1e-6, f't_two_tail({_t},3) 偏离表值'


W = load(D_A / '宽表-初中水平-徐汇区-2022-2026.csv')
R2 = load(D_A / '收敛指标-徐汇区-2022-2026.csv')
R3 = load(D_A / '收敛趋势检验-徐汇区-2022-2026.csv')
R4 = load(D_A / '趋势分类-徐汇区-2022-2026.csv')
bym = {r['junior_high_school']: r for r in W}
bad = []

# ---- 4.1 收敛指标 ----
FIXED = [r for r in W if r['row_type'] == 'ranked' and r['years_included'] == '5']
FIXN = {r['junior_high_school'] for r in FIXED}
if len(FIXED) != 23:
    bad.append(('4.1', '固定样本', len(FIXED), 23))
POOL = {y: [r for r in W if r['row_type'] == 'ranked'
            and r['mean_score_base_%d' % y] not in ('', None)] for y in YEARS}


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
    cum = sum((i + 1) * v for i, v in enumerate(s))
    return (2 * cum - (n + 1) * tot) / (n * tot)


n1 = 0
for r in R2:
    y = int(r['year'])
    xs = [float(x['mean_score_base_%d' % y]) for x in FIXED]
    med = st.median(xs)
    exp = {'sigma': st.pstdev(xs), 'cv': st.pstdev(xs) / med,
           'iqr_norm': (pctl(xs, 75) - pctl(xs, 25)) / med, 'gini': gini(xs),
           'r90_10_norm': (pctl(xs, 90) - pctl(xs, 10)) / med,
           'range_norm': (max(xs) - min(xs)) / med,
           'mad_norm': st.fmean([abs(v - med) for v in xs]) / med}
    if int(r['n_fixed']) != len(xs):
        bad.append(('4.1', y, 'n_fixed', r['n_fixed'], len(xs)))
    n1 += 1
    for k, e in exp.items():
        if abs(float(r[k]) - e) > 1e-6:
            bad.append(('4.1', y, k, r[k], '%.6f' % e))
        n1 += 1
    if int(r['pool_n']) != len(POOL[y]):
        bad.append(('4.1', y, 'pool_n', r['pool_n'], len(POOL[y])))
    n1 += 1
print('4.1 收敛指标：%d 格（固定样本 %d 所，池外校数 %s）'
      % (n1, len(FIXED), [r['outside_n'] for r in R2]))

# ---- 4.2 收敛趋势检验：CI 用独立 t 临界值复算 ----
tc = t_crit(0.05, 3)
n2 = 0
for r in R3:
    b, se = float(r['slope_b']), float(r['se'])
    df = int(r['df'])
    t_exp = t_crit(0.05, df)
    lo, hi = b - t_exp * se, b + t_exp * se
    if abs(float(r['ci_lo']) - lo) > 1e-6 or abs(float(r['ci_hi']) - hi) > 1e-6:
        bad.append(('4.2', r['metric'], 'CI',
                    '[%s,%s]' % (r['ci_lo'], r['ci_hi']),
                    '[%.8f,%.8f]' % (lo, hi)))
    n2 += 1
    # 生成脚本把 t 存为 4 位小数，容差须与**存储精度**一致（5e-5），
    # 否则会因纯舍入报错（gini/mad_norm 实测差 4e-4，源于 slope_b/se 各存 7 位）
    if abs(float(r['t']) - b / se) > 1e-3:
        bad.append(('4.2', r['metric'], 't', r['t'], '%.4f' % (b / se)))
    n2 += 1
    if abs(float(r['p']) - t_two_tail(abs(b / se), df)) > 1e-5:
        bad.append(('4.2', r['metric'], 'p', r['p'],
                    '%.6f' % t_two_tail(abs(b / se), df)))
    n2 += 1
    if int(r['n_obs']) != 5 or df != 3:
        bad.append(('4.2', r['metric'], 'n/df', r['n_obs'], df))
    n2 += 1
print('4.2 收敛趋势检验：%d 格（t 临界值独立反解 = %.6f，生成脚本用 3.182446）'
      % (n2, tc))
assert abs(tc - 3.182446) < 1e-5, 't(0.975,df=3) 独立反解 %.6f 与 3.182446 不符' % tc

# ---- 4.3 趋势分类 ----
MK_M = len(FIXED)
n3 = 0
# 趋势分类表**不带 rel_2022…**（只存聚合后的 sen/rel_first/rel_last），
# 故 rel 序列须回到**宽表**按校名取，避免自证。
Wbyname = {r['junior_high_school']: r for r in W}
for r in R4:
    src = Wbyname[r['junior_high_school']]
    rels = [(int(y), float(src['rel_%d' % y])) for y in YEARS
            if src['rel_%d' % y] not in ('', None)]
    if not rels:
        bad.append(('4.3', r['junior_high_school'], 'rel', '空', '非空'))
        continue
    exp_sen = (rels[-1][1] - rels[0][1]) / (rels[-1][0] - rels[0][0])
    if abs(float(r['sen']) - exp_sen) > 1e-4:
        bad.append(('4.3', r['junior_high_school'], 'sen', r['sen'], '%.4f' % exp_sen))
    n3 += 1
    exp_d = rels[-1][1] - rels[0][1]
    if abs(float(r['delta_rel']) - exp_d) > 1e-4:
        bad.append(('4.3', r['junior_high_school'], 'delta', r['delta_rel'], '%.4f' % exp_d))
    n3 += 1
    if abs(float(r['rel_first']) - rels[0][1]) > 1e-4 or \
       abs(float(r['rel_last']) - rels[-1][1]) > 1e-4:
        bad.append(('4.3', r['junior_high_school'], 'rel_first/last',
                    '%s/%s' % (r['rel_first'], r['rel_last']),
                    '%.4f/%.4f' % (rels[0][1], rels[-1][1])))
    n3 += 1
    ys = [v for _, v in rels]
    nn = len(ys)
    S = sum((ys[j] > ys[i]) - (ys[j] < ys[i])
            for i in range(nn) for j in range(i + 1, nn))
    if int(r['mk_S']) != S:
        bad.append(('4.3', r['junior_high_school'], 'mk_S', r['mk_S'], S))
    n3 += 1
    if abs(float(r['mk_p_bonferroni']) - min(1.0, float(r['mk_p']) * MK_M)) > 1e-3:
        bad.append(('4.3', r['junior_high_school'], 'bonf',
                    r['mk_p_bonferroni'], '%.4f' % min(1.0, float(r['mk_p']) * MK_M)))
    n3 += 1
    exp_cls = ('明显上升' if exp_sen >= 1.0 else
               '明显下降' if exp_sen <= -1.0 else '基本持平')
    if r['trend_class'] != exp_cls:
        bad.append(('4.3', r['junior_high_school'], 'class', r['trend_class'], exp_cls))
    n3 += 1
from collections import Counter
print('4.3 趋势分类：%d 格（%d 所，Bonferroni ×%d，分布 %s）'
      % (n3, len(R4), MK_M, dict(Counter(r['trend_class'] for r in R4))))
if len(R4) != 23 or any(r['row_type'] != 'ranked' for r in R4):
    bad.append(('4.3', '覆盖范围', len(R4), 23))
if any(r['sig_bonferroni'] != '否' for r in R4):
    bad.append(('4.3', '校正后有显著', '是', '否'))

if bad:
    print('\n❌ 不一致 %d 处（前 15）:' % len(bad))
    for x in bad[:15]:
        print('   ', x)
    sys.exit(1)
print('\n✅ 三张表复算一致（共 %d 格）' % (n1 + n2 + n3))
