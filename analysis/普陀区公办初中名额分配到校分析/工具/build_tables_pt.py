"""阶段 4：普陀三张新表（收敛指标 / 收敛趋势检验 / 趋势分类）。

口径对齐嘉定 `build_q2q3_jd.py` 与 `build_ch5_jd.py`，但按**普陀自身口径**实现：
  · 均分列          = mean_score_base4_wq_{y}（区属 4 线名额加权均分；普陀基线是 4 线非 3 线）
  · 固定样本        = row_type='ranked' 且 years_included=5（普陀 32 所）
  · 归一化分母      = **当年公办非退出池中位**（与 rel 基准同池，见 2.3；普陀另有 exited 校）
  · 民办 / exited / 短样本 一律不进固定样本
  · 名额已按 `merged_into` 排除（1.1），西校不独立计量

检验力说明：n=5、df=3 ⇒ Mann-Kendall 最小 p≈0.028、OLS p 最小 ≈0.028，
Bonferroni 校正后（×14）阈值 0.0036 ⇒ **预期 0 所显著**。这是检验力天花板，
不是「无趋势」的证据，必须在报告中写明。

写入策略：全部在内存拼装 + 断言通过后才落盘（规范陷阱 14）。
"""
import csv
import io
import math
import statistics as st
from pathlib import Path

D_A = Path('.')
YEARS = [2022, 2023, 2024, 2025, 2026]
MIN_YEARS_FIXED = 5
N_MK_TESTS = 14          # 与嘉定一致：7 指标 + 7 方向检验
ALPHA = 0.05
MEAN_COL = 'mean_score_base4_wq_{y}'


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def num(v, nd=None):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ''
    return f'{f:.{nd}f}' if nd is not None else f


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
    """基尼系数（升序 0-based 配 1-based 系数，系数和恒 0 ⇒ 结果非负）。"""
    s = sorted(xs)
    n, tot = len(s), sum(s)
    if n == 0 or tot <= 0:
        return None
    return sum((2 * i - n + 1) * x for i, x in enumerate(s)) / (n * tot)


def ols(xs, ys):
    """一元 OLS：返回 b/se/t/p/r2/ci（x 为年份序号 0..4）。"""
    n = len(xs)
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    sse = sum(r * r for r in resid)
    df = n - 2
    s2 = sse / df
    se = math.sqrt(s2 / sxx)
    t = b / se if se else None
    r2 = 1 - sse / sum((y - my) ** 2 for y in ys) if sse else 1.0
    # 双侧 p（t 分布，df=3 时用闭式不完全 beta 的数值积分近似）
    p = 2 * (1 - student_cdf(abs(t), df)) if t is not None else None
    # t_{0.975} 精确值（df 1..5）；此前用 3.182 近似会使 CI 与统计量差 1e-4
    tcrit = {1: 12.706205, 2: 4.302653, 3: 3.182446, 4: 2.776445, 5: 2.570582}.get(df, 1.959964)
    return {'b': b, 'se': se, 't': t, 'p': p, 'r2': r2, 'n_obs': n, 'df': df,
            'ci_lo': b - tcrit * se, 'ci_hi': b + tcrit * se}


def _norm_cdf(x):
    """标准正态 CDF，精度约 1e-7（A&S 7.1.26 误差函数近似）。"""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804014327 * math.exp(-x * x / 2.0)
    p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
                                    + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - p if x > 0 else p


def student_cdf(x, df):
    """学生 t 分布 CDF（数值积分，精度足够 n=5 的报告用途）。"""
    if x is None:
        return None
    x = abs(x)
    if x == 0:
        return 0.5
    # ∫0..x (1+t²/df)^(-(df+1)/2) dt 归一化
    k = (df + 1) / 2
    a = math.gamma(k)
    b = math.gamma(df / 2) * math.sqrt(df * math.pi)
    f = lambda t: (1 + t * t / df) ** (-k)
    n = 4000
    h = x / n
    s = f(0) + f(x)
    for i in range(1, n):
        s += (4 if i % 2 else 2) * f(i * h)
    s *= h / 3
    return 0.5 + s * a / b


def mk_test(ys):
    """Mann-Kendall：返回 S / z / p（无并列修正的方差）。"""
    n = len(ys)
    def _sgn(x):
        return (x > 0) - (x < 0)

    S = sum(_sgn(ys[j] - ys[i]) for i in range(n) for j in range(i + 1, n))
    var = n * (n - 1) * (2 * n + 5) / 18
    z = (S - 1) / math.sqrt(var) if S > 0 else ((S + 1) / math.sqrt(var) if S < 0 else 0.0)
    p = 2 * (1 - _norm_cdf(abs(z))) if z else 1.0
    return S, z, p


# ================= 载入宽表 =================
W = load(D_A / '宽表-初中水平-普陀区-2022-2026.csv')
RANKED = [r for r in W if r['row_type'] == 'ranked']
FIXED = [r for r in RANKED if int(r['years_included']) == MIN_YEARS_FIXED]

# 池中位：当年**公办非退出**池（与 2.3 的 rel 基准同池）
POOL_MED, POOL_N = {}, {}
for y in YEARS:
    vals = [float(r[MEAN_COL.format(y=y)]) for r in W
            if r['ownership'] == '公办' and r['row_type'] != 'exited'
            and r[MEAN_COL.format(y=y)] not in ('', None)]
    POOL_MED[y] = st.median(vals)
    POOL_N[y] = len(vals)
print(f'固定样本 {len(FIXED)} 所｜逐年公办非退出池中位：'
      + '｜'.join(f'{y}:{POOL_MED[y]:.2f}(n={POOL_N[y]})' for y in YEARS))
assert FIXED, '固定样本为空'

# ================= 4.1 收敛指标 =================
METRICS = ('cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm')
rows2 = []
for y in YEARS:
    col = MEAN_COL.format(y=y)
    xs = [float(r[col]) for r in FIXED if r[col] not in ('', None)]
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
    # 构成效应：固定样本之外、当年有数据的公办非退出校
    outside = [r for r in W
               if r['ownership'] == '公办' and r['row_type'] != 'exited'
               and r['junior_high_school'] not in {x['junior_high_school'] for x in FIXED}
               and r[col] not in ('', None)]
    opcts = []
    for r in outside:
        pool = sorted(float(x[col]) for x in W
                      if x['ownership'] == '公办' and x['row_type'] != 'exited'
                      and x[col] not in ('', None))
        below = sum(1 for v in pool if v < float(r[col]))
        opcts.append(below / (len(pool) - 1) if len(pool) > 1 else 0.0)
    rows2.append({'year': y, 'n_fixed': len(xs), 'pool_n': POOL_N[y],
                  'pool_median': num(med, 3),
                  'fixed_mean': num(st.fmean(xs), 3),
                  'fixed_max': num(max(xs), 3), 'fixed_min': num(min(xs), 3),
                  **{k: num(m.get(k), 6) for k in ('sigma',) + METRICS},
                  'outside_n': len(outside),
                  'outside_pct_mean': num(st.fmean(opcts), 4) if opcts else ''})

# 判定：固定样本校数五年恒定
_ns = {r['n_fixed'] for r in rows2}
assert len(_ns) == 1, f'固定样本校数逐年不等：{_ns}'
print(f'4.1 固定样本 {rows2[0]["n_fixed"]} 所，五年恒定 ✓｜'
      f'池外校数：{[r["outside_n"] for r in rows2]}')

# ================= 4.2 收敛趋势检验 =================
xs_t = [y - 2022 for y in YEARS]
rows3 = []
for k in ('sigma',) + METRICS:
    o = ols(xs_t, [float(r[k]) for r in rows2])
    # 显式映射到表头列名：ols() 返回的键是 b/se/t/p/r2/n_obs/df/ci_lo/ci_hi，
    # 若直接 **o 展开会与表头 `slope_b` 不匹配 ⇒ 该列静默变空（曾发生）。
    rows3.append({'metric': k,
                  'slope_b': num(o['b'], 7), 'se': num(o['se'], 7),
                  't': num(o['t'], 4), 'p': num(o['p'], 6), 'r2': num(o['r2'], 6),
                  'n_obs': o['n_obs'], 'df': o['df'],
                  'ci_lo': num(o['ci_lo'], 8), 'ci_hi': num(o['ci_hi'], 8),
                  'v2022': rows2[0][k], 'v2026': rows2[-1][k]})
    assert all(rows3[-1][c] != '' for c in ('slope_b', 'se', 't', 'p', 'r2',
                                            'ci_lo', 'ci_hi')), \
        f'{k} 的检验列有空值，检查列名映射'
    print(f'  {k:<12} 2022={float(rows2[0][k]):.5f} 2026={float(rows2[-1][k]):.5f} '
          f'b={o["b"]:+.6f}/年 p={o["p"]:.3f} '
          f'CI[{o["ci_lo"]:+.5f},{o["ci_hi"]:+.5f}]')

# ================= 4.3 趋势分类 =================
# 阈值**预注册**（分析前固定，见 design.md 3.3）：|SEN| ≥ 1.0 视为明显上升/下降
SEN_THRESH = 1.0
rows4 = []
for r in RANKED:
    name = r['junior_high_school']
    rels = [(y, float(r[f'rel_{y}'])) for y in YEARS if r.get(f'rel_{y}') not in ('', None)]
    pts3 = [p for p in rels if p[0] >= 2024]
    sen = (rels[-1][1] - rels[0][1]) / (rels[-1][0] - rels[0][0]) if len(rels) >= 2 else None
    sen3 = (pts3[-1][1] - pts3[0][1]) / (pts3[-1][0] - pts3[0][0]) if len(pts3) >= 2 else None
    ys = [v for _, v in rels]
    mkS, mkz, mkp = mk_test(ys)
    mkp_b = min(1.0, mkp * N_MK_TESTS)
    d = rels[-1][1] - rels[0][1]
    cls = ('数据不足' if sen is None else
           '明显上升' if sen >= SEN_THRESH else
           '明显下降' if sen <= -SEN_THRESH else '基本持平')
    rows4.append({
        'junior_high_school': name, 'row_type': r['row_type'],
        'n_years': r['years_included'], 'trend_class': cls,
        'sen': num(sen, 4), 'sen_recent3': num(sen3, 4),
        'rel_first': num(rels[0][1], 3), 'rel_last': num(rels[-1][1], 3),
        'delta_rel': num(d, 3),
        'mk_S': mkS, 'mk_z': num(mkz, 4), 'mk_p': num(mkp, 4),
        'mk_p_bonferroni': num(mkp_b, 4),
        'sig_uncorrected': '是' if mkp < ALPHA else '否',
        'sig_bonferroni': '是' if mkp_b < ALPHA else '否',
    })

_cls = {}
for r in rows4:
    _cls[r['trend_class']] = _cls.get(r['trend_class'], 0) + 1
from collections import Counter
print(f'4.3 分类（阈值预注册 |SEN|≥{SEN_THRESH}，'
      f'MK 校正 ×{N_MK_TESTS}）：{dict(Counter(r["trend_class"] for r in rows4))}')
print(f'   校正后显著：{sum(1 for r in rows4 if r["sig_bonferroni"] == "是")} 所'
      f'（n={len(rows4)}, df=3 ⇒ 检验力天花板，预期 0）')
# 判定：分类只覆盖 years_included ≥ 4
assert all(int(r['n_years']) >= 4 for r in rows4), '分类覆盖了 n<4 的学校'
assert all(r['row_type'] == 'ranked' for r in rows4), '分类混入了非 ranked 行'

# ================= 落盘（全部断言通过后）====================
def dump(path, rows, cols):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\r\n', extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
    out = buf.getvalue().encode('utf-8-sig')
    assert out.count(b'\n') == len(rows) + 1, f'{path} 行数异常'
    assert len(out) > 500, f'{path} 输出过小'
    Path(path).write_bytes(out)
    print(f'  写出 {path}（{len(rows)} 行 × {len(cols)} 列）')


dump('收敛指标-普陀区-2022-2026.csv', rows2,
     ['year', 'n_fixed', 'pool_n', 'pool_median', 'fixed_mean', 'fixed_max', 'fixed_min',
      'sigma', 'cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm',
      'outside_n', 'outside_pct_mean'])
dump('收敛趋势检验-普陀区-2022-2026.csv', rows3,
     ['metric', 'slope_b', 'se', 't', 'p', 'r2', 'n_obs', 'df', 'ci_lo', 'ci_hi',
      'v2022', 'v2026'])
dump('趋势分类-普陀区-2022-2026.csv', rows4,
     ['junior_high_school', 'row_type', 'n_years', 'trend_class', 'sen', 'sen_recent3',
      'rel_first', 'rel_last', 'delta_rel',
      'mk_S', 'mk_z', 'mk_p', 'mk_p_bonferroni', 'sig_uncorrected', 'sig_bonferroni'])
print('阶段 4 三表完成')
