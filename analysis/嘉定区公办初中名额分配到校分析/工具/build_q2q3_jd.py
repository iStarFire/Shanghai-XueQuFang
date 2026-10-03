# -*- coding: utf-8 -*-
"""2.3 嘉定区 Q2 收敛分析 + Q3 趋势分类（任务 10-03-jiading-new-schools-recent3）。

读入宽表（唯一事实源），产出两张新表：
  收敛指标-嘉定区-2022-2026.csv   Q2：固定样本逐年差距指标 + 趋势检验 + Q-Q 收敛
  趋势分类-嘉定区-2022-2026.csv   Q3：入榜学校上升/下降分类 + Mann-Kendall 检验

方法（预注册在 design.md 5-6，**事后不得调整**）
--------------------------------
Q2 核心问题：**池子构成混杂**。逐年全池 27→39 所，新校若集中在中间水平，
仅因「新校加入」就会压低 σ。因此主口径用**固定样本**：

  固定样本 = 归并后五年全勤的 27 所公办（含德富、嘉二实验），五年恒定。

量的选择：`mean_score_base3_wq_y`（区属 3 线名额加权均分）。**所有离散度指标必须
归一化到当年全区全池中位**才能跨年比较——σ/IQR/极差虽是平移不变的，但**尺度随
当年卷面难度变化**，不归一化就比较的是难度而非差距（design 5.3）。

Q3 判定规则（design 6.3）：阈值 |sen| = 1.10 分/年，来自实测 |sen| 排序的**自然间隙**
（0.86 与 1.10 之间断层），非主观设定。优先级：方向不一 > 明显上升/下降 > 温和升/降。

⚠ 检验力限制（design 6.4，报告必须如实写明）：n=5 时 Mann-Kendall 完全单调的
最小 p ≈ 0.028；而 28 所学校 Bonferroni 校正后 α ≈ 0.0036 —— **校正后不可能有
任何学校达到显著**。故本表分类是**方向性描述**，不是「统计显著的结论」。
"""
import csv
import math
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = ['2022', '2023', '2024', '2025', '2026']
SENS_THRESH = 1.10          # design 6.2：来自 |sen| 自然间隙
ALPHA = 0.10


# ------------------------------------------------------------------ 工具
def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def pctl(xs, p):
    """线性插值分位（与 numpy 默认一致，避免依赖差异）。"""
    s = sorted(xs)
    n = len(s)
    if n == 1:
        return s[0]
    k = (n - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def gini(xs):
    """基尼系数（升序排列，0-based 索引）。

    标准形式 G = sum((2i-n+1)*x_i) / (n*sum x)；
    系数之和恒为 0，故结果必为非负。
    ⚠ 索引基准与系数形式必须匹配——用 0-based 索引配 1-based 系数
    （2i-n-1）会使系数和为 -2n，产出**负的**基尼系数（曾发生）。
    """
    s = sorted(xs)
    n, tot = len(s), sum(s)
    if n == 0 or tot <= 0:
        return None
    assert abs(sum(2 * i - n + 1 for i in range(n))) < 1e-9, 'Gini 系数和不为 0'
    return sum((2 * i - n + 1) * x for i, x in enumerate(s)) / (n * tot)


def ols(xs, ys):
    """返回 b, intercept, r2, se_b, t, p(双侧, df=n-2)。"""
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    sst = sum((y - my) ** 2 for y in ys)
    r2 = 1 - sse / sst if sst else None
    df = n - 2
    se_b = math.sqrt((sse / df) / sxx) if df > 0 and sxx > 0 else None
    t = b / se_b if se_b else None
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2)))) if t is not None else None
    # 95% 置信区间（正态近似；df 小的时候偏窄，故只作参考）
    lo = b - 1.96 * se_b if se_b else None
    hi = b + 1.96 * se_b if se_b else None
    return {'b': b, 'a': a, 'r2': r2, 'se': se_b, 't': t, 'p': p,
            'ci_lo': lo, 'ci_hi': hi, 'n': n, 'df': df}


def sen_slope(xs, ys):
    """Theil–Sen：中位数斜率。"""
    sl = [(ys[j] - ys[i]) / (xs[j] - xs[i])
          for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j] != xs[i]]
    return st.median(sl) if sl else None


def mann_kendall(ys):
    """趋势检验：S 统计量、z、双侧 p。n 小时检验力低，务必与效应量同看。"""
    n = len(ys)
    S = sum((ys[j] > ys[i]) - (ys[j] < ys[i])
            for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18
    z = 0.0 if S == 0 else (S - 1) / math.sqrt(var) if S > 0 else (S + 1) / math.sqrt(var)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return S, z, p


def num(v, nd=4):
    return '' if v is None else round(v, nd)


# ------------------------------------------------------------------ 载入
W = load(f'{D_A}/宽表-初中水平-嘉定区-2022-2026.csv')
RANKED = [r for r in W if r['row_type'] == 'ranked']
FIXED = [r for r in RANKED if r['years_included'] == '5']   # Q2 固定样本 27 所

# 当年**公办池**中位（与主口径一致：排名不含民办）
POOL_MED, POOL_N = {}, {}
for y in YEARS:
    vals = [float(r[f'mean_score_base3_wq_{y}']) for r in W
            if r['ownership'] == '公办'
            and r[f'valid_pairs_{y}'] not in ('', '0') and r[f'mean_score_base3_wq_{y}']]
    POOL_MED[y] = st.median(vals)
    POOL_N[y] = len(vals)
print(f'固定样本 {len(FIXED)} 所｜逐年全池中位：'
      + '｜'.join(f'{y}:{POOL_MED[y]:.2f}(n={POOL_N[y]})' for y in YEARS))

METRICS = ('cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm')
rows2 = []
for y in YEARS:
    xs = [float(r[f'mean_score_base3_wq_{y}']) for r in FIXED]
    med = POOL_MED[y]
    med_xs = st.median(xs)
    m = {
        'sigma': st.pstdev(xs),
        'cv': st.pstdev(xs) / med,
        'iqr_norm': (pctl(xs, 75) - pctl(xs, 25)) / med,
        'gini': gini(xs),
        'r90_10_norm': (pctl(xs, 90) - pctl(xs, 10)) / med,
        'range_norm': (max(xs) - min(xs)) / med,
        'mad_norm': st.fmean([abs(v - med_xs) for v in xs]) / med,
    }
    rows2.append({'year': y, 'n_fixed': len(xs), 'pool_n': POOL_N[y],
                  'pool_median': num(med, 3),
                  'fixed_mean': num(st.fmean(xs), 3),
                  'fixed_max': num(max(xs), 3), 'fixed_min': num(min(xs), 3),
                  **{k: num(m.get(k), 6) for k in ('sigma',) + METRICS}})

# ---- 趋势检验：指标 ~ 年份序号（n=5，df=3，检验力低，仅作参考）
trends = {}
xs_t = [int(y) - 2022 for y in YEARS]
for k in ('sigma',) + METRICS:
    o = ols(xs_t, [float(r[k]) for r in rows2])
    trends[k] = o
    print(f'  {k:<12} 2022={rows2[0][k]:.5f} 2026={rows2[-1][k]:.5f} '
          f'b={o["b"]:+.6f}/年 p={o["p"]:.3f} '
          f'CI[{o["ci_lo"]:+.5f},{o["ci_hi"]:+.5f}]')

# ---- Q-Q 收敛：同一批学校在 2022 与 2026 的**名次分位**配对回归，斜率 < 1 表示收敛
# 注意：此处必须是**排名分位**，不是分数——分数跨年不可比（难度不同），
# 排名分位才是「位置」量纲，比较的是格局是否收拢。
def rank_pct(pairs):
    srt = sorted(pairs, key=lambda t: t[1])
    m_ = len(srt)
    return {name: i / (m_ - 1) for i, (name, _) in enumerate(srt)}


p22 = rank_pct([(r['junior_high_school'], float(r['mean_score_base3_wq_2022'])) for r in FIXED])
p26 = rank_pct([(r['junior_high_school'], float(r['mean_score_base3_wq_2026'])) for r in FIXED])
qq = ols([p22[r['junior_high_school']] for r in FIXED],
         [p26[r['junior_high_school']] for r in FIXED])
qq_slope = qq['b']
# 检验目标是「b=1（名次格局不变）」而不是「b=0（完全洗牌）」——
# 收敛的定义就是分位向中心收缩，故 H0: b=1。p 值检验 b=0 是问错问题。
qq_se = qq['se']
qq_t1 = (qq_slope - 1) / qq_se if qq_se else None
qq_p1 = (2 * (1 - 0.5 * (1 + math.erf(abs(qq_t1) / math.sqrt(2))))
         if qq_t1 is not None else None)
print(f'  Q-Q 名次分位收敛斜率 = {qq_slope:.4f}（<1 表示向中心收缩）'
      f'｜95%CI [{qq["ci_lo"]:.3f}, {qq["ci_hi"]:.3f}]'
      f'｜R²={qq["r2"]:.4f}｜n={qq["n"]}')
print(f'    检验 H0: b=1 → t={qq_t1:.3f} p={qq_p1:.2e}'
      f'｜H0 不被拒绝？{"否，即格局显著收缩" if qq_p1 < 0.05 else "是，方向不可定"}')
print(f'    注：R²={qq["r2"]:.4f} 极低 → 2022 分位几乎不预测 2026 分位（个体排名大幅重排），'
      f'与「系统性向中心收缩」可同时成立，二者都要说')

# ---- 混淆量化：固定样本外学校（民办 + 新校）在当年全池分位上的均值
# 注：2022 年固定样本恰为当年全体 27 所，样本外为空，属正常情形
FIXED_NAMES = {r['junior_high_school'] for r in FIXED}
for y in YEARS:
    allv = sorted(float(r[f'mean_score_base3_wq_{y}']) for r in W
                  if r['ownership'] == '公办'
                  and r[f'valid_pairs_{y}'] not in ('', '0')
                  and r[f'mean_score_base3_wq_{y}'])
    out = [float(r[f'mean_score_base3_wq_{y}']) for r in W
           if r['ownership'] == '公办'
           and r['junior_high_school'] not in FIXED_NAMES
           and r[f'valid_pairs_{y}'] not in ('', '0') and r[f'mean_score_base3_wq_{y}']]
    pct = [sum(1 for v in allv if v <= o) / len(allv) for o in out]
    row = rows2[int(y) - 2022]
    row['outside_n'] = len(out)
    row['outside_pct_mean'] = num(st.fmean(pct), 4) if pct else ''
    print(f'  {y} 固定样本外 {len(out):>2} 所'
          + (f'，平均分位 {st.fmean(pct):.3f}（0.5 附近=居中，会压低全池离散度）'
             if pct else '（样本外为空：固定样本即当年全体）'))

cols2 = (['year', 'n_fixed', 'pool_n', 'pool_median', 'fixed_mean',
          'fixed_max', 'fixed_min', 'sigma'] + list(METRICS)
         + ['outside_n', 'outside_pct_mean'])
with open(f'{D_A}/收敛指标-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols2)
    w.writeheader()
    w.writerows(rows2)

# 指标趋势另存一张长表，便于报告直接引用
trows = [{'metric': k, 'slope_b': num(o['b'], 8), 'se': num(o['se'], 8),
          't': num(o['t'], 4), 'p': num(o['p'], 4), 'r2': num(o['r2'], 4),
          'n_obs': o['n'], 'df': o['df'], 'ci_lo': num(o['ci_lo'], 8),
          'ci_hi': num(o['ci_hi'], 8),
          'v2022': rows2[0][k], 'v2026': rows2[-1][k]} for k, o in trends.items()]
trows.append({'metric': 'qq_slope', 'slope_b': num(qq_slope, 4), 'se': num(qq_se, 4),
              't': num(qq_t1, 4), 'p': num(qq_p1, 6), 'r2': num(qq['r2'], 4),
              'n_obs': qq['n'], 'df': qq['df'],
              'ci_lo': num(qq['ci_lo'], 4), 'ci_hi': num(qq['ci_hi'], 4),
              'v2022': '', 'v2026': ''})

# ---- 结论三分判定（design 5.7，优先级唯一，命中即止）
_core = [k for k in trends if k != 'sigma']
_pos = [k for k in _core if trends[k]['b'] > 0]
_neg = [k for k in _core if trends[k]['b'] < 0]
_sig_pos = [k for k in _pos if trends[k]['ci_lo'] > 0]
_sig_neg = [k for k in _neg if trends[k]['ci_hi'] < 0]
qq_clear = not (qq['ci_lo'] <= 1 <= qq['ci_hi'])   # CI 不含 1 → 方向可定
if qq_clear and qq_slope < 1 and len(_sig_neg) >= 1 and len(_sig_neg) >= len(_core) / 2:
    VERDICT = '持续收敛'
elif qq_clear and qq_slope > 1 and len(_sig_pos) >= 1 and len(_sig_pos) >= len(_core) / 2:
    VERDICT = '持续发散（离散度扩大）'
elif len(_sig_pos) >= len(_core) / 2:
    VERDICT = '未收敛（方向可定：离散度在扩大）'
else:
    VERDICT = '统计上无法判定'
n_sig = len([k for k in trends if trends[k]['p'] < 0.1])
print(f'\n  Q2 判定（design 5.7 优先级）：**{VERDICT}**')
print(f'    6 指标方向：{len(_pos)} 正 / {len(_neg)} 负；'
      f'CI 不含 0 的：正 {len(_sig_pos)} 个 / 负 {len(_sig_neg)} 个；p<0.1 的 {n_sig} 个')
print(f'    Q-Q 方向可定？{"是" if qq_clear else "否"}（CI 不含 1）'
      f'｜β={qq_slope:.3f} p(H0:b=1)={qq_p1:.4f}')
print('    ⚠ 多数指标 CI 跨 0 → 不显著 ≠ 无趋势，报告不得写成「没有差距变化」')
with open(f'{D_A}/收敛趋势检验-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['metric', 'slope_b', 'se', 't', 'p', 'r2',
                                      'n_obs', 'df', 'ci_lo', 'ci_hi', 'v2022', 'v2026'])
    w.writeheader()
    w.writerows(trows)
print(f'写出 收敛指标 / 收敛趋势检验 两表')

# ==================================================================== Q3
m = len(RANKED)
bonf = ALPHA / m
rows3 = []
for r in RANKED:
    name = r['junior_high_school']
    ys_all = [int(y) for y in YEARS if r[f'rel_{y}']]
    rels = [float(r[f'rel_{y}']) for y in YEARS if r[f'rel_{y}']]
    k = len(rels)
    sen = sen_slope(ys_all, rels)
    reg = ols([0] + list(range(1, k)), rels)          # x 用 0..k-1，保持与既有 sen_ols 同口径
    sen_ols = reg['b'] if reg else None
    S, z, p = mann_kendall(rels)
    if sen is not None and sen_ols is not None and sen * sen_ols < 0:
        cls = '方向不一'
    elif sen is not None and sen_ols is not None and sen >= SENS_THRESH and sen_ols > 0:
        cls = '明显上升'
    elif sen is not None and sen_ols is not None and sen <= -SENS_THRESH and sen_ols < 0:
        cls = '明显下降'
    elif sen is not None and sen_ols is not None and sen > 0 and sen_ols > 0:
        cls = '温和上升'
    elif sen is not None and sen_ols is not None and sen < 0 and sen_ols < 0:
        cls = '温和下降'
    else:
        cls = '无法判定'
    # 近三年（2024-2026）方向：n=3，MK 最小 p≈0.29，只能描述不可判显著
    r3 = [float(r[f'rel_{y}']) for y in ['2024', '2025', '2026'] if r[f'rel_{y}']]
    s3 = sen_slope([0, 1, 2], r3) if len(r3) == 3 else None
    rows3.append({
        'junior_high_school': name, 'row_type': r['row_type'], 'n_years': k,
        'trend_class': cls, 'sen': num(sen, 4), 'sen_ols': num(sen_ols, 4),
        'rel_first': num(rels[0], 3), 'rel_last': num(rels[-1], 3),
        'delta_rel': num(rels[-1] - rels[0], 3),
        'sen_recent3': num(s3, 4),
        'mk_S': S, 'mk_z': num(z, 4), 'mk_p': num(p, 4),
        'mk_p_bonferroni': num(min(1.0, p * m), 4),
        'sig_uncorrected': '是' if p < ALPHA else '否',
        'sig_bonferroni': '是' if min(1.0, p * m) < ALPHA else '否',
    })

order = {'明显上升': 0, '温和上升': 1, '方向不一': 2, '无法判定': 3,
         '温和下降': 4, '明显下降': 5}
rows3.sort(key=lambda d: (order.get(d['trend_class'], 9),
                          -(d['sen'] if d['sen'] != '' else 0)))
cols3 = ['junior_high_school', 'row_type', 'n_years', 'trend_class', 'sen', 'sen_ols',
         'rel_first', 'rel_last', 'delta_rel', 'sen_recent3',
         'mk_S', 'mk_z', 'mk_p', 'mk_p_bonferroni', 'sig_uncorrected', 'sig_bonferroni']
with open(f'{D_A}/趋势分类-嘉定区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols3)
    w.writeheader()
    w.writerows(rows3)

from collections import Counter
c = Counter(d['trend_class'] for d in rows3)
print(f'\nQ3 分类（阈值 |sen|={SENS_THRESH}，m={m}，Bonferroni α={bonf:.5f}）：')
for kk in order:
    if c.get(kk):
        print(f'  {kk} {c[kk]} 所：' + '、'.join(
            d['junior_high_school'] for d in rows3 if d['trend_class'] == kk))
print(f"  未校正 p<0.05：{sum(1 for d in rows3 if d['mk_p'] != '' and d['mk_p'] < 0.05)} 所"
      f"｜校正后显著：{sum(1 for d in rows3 if d['sig_bonferroni'] == '是')} 所")
opp = [d for d in rows3 if d['sen'] and d['sen_recent3']
       and (float(d['sen']) > 0) != (float(d['sen_recent3']) > 0)]
print(f'  五年方向与近三年方向相反：{len(opp)} 所：'
      + '、'.join(f"{d['junior_high_school']}(sen={d['sen']},s3={d['sen_recent3']})"
                  for d in opp))
print('写出 趋势分类表')
