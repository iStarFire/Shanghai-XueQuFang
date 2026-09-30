"""趋势分析的独立复算校验（S11 / 2.4 门禁）。

**刻意不 import `build_trend.py` 的任何函数**，从宽表与长表重新实现一遍
rel / Theil–Sen / Spearman / 去尾 / 留一法 / 收敛回归，
以「两份独立实现结果一致」作为正确性证据。
"""
import csv, statistics as st, sys, os

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{ROOT}/data/徐汇区/学校"
A = f"{ROOT}/analysis/徐汇区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
SEN_MIN = 1.0
BASE4 = ['042001', '042008', '042035', '043015']


def rd(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def sen(pairs):
    """Theil–Sen：所有点对斜率的中位数（独立实现）。"""
    slopes = []
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            dx = pairs[j][0] - pairs[i][0]
            if dx:
                slopes.append((pairs[j][1] - pairs[i][1]) / dx)
    slopes.sort()
    n = len(slopes)
    return (slopes[n // 2] if n % 2 else (slopes[n // 2 - 1] + slopes[n // 2]) / 2)


def spearman(pairs):
    """秩相关（独立实现：用「小于计数」求秩，避免依赖 quantiles）。"""
    ys = [p[1] for p in pairs]
    n = len(ys)
    rk = []
    for v in ys:
        less = sum(1 for u in ys if u < v)
        eq = sum(1 for u in ys if u == v)
        rk.append(less + (eq + 1) / 2)          # 平均秩（1 起）
    xr = list(range(1, n + 1))
    mx, my = st.mean(xr), st.mean(rk)
    num = sum((a - mx) * (b - my) for a, b in zip(xr, rk))
    den = (sum((a - mx) ** 2 for a in xr) * sum((b - my) ** 2 for b in rk)) ** 0.5
    return num / den if den else 0.0


def main():
    wide = [r for r in rd(f'{A}/宽表-初中水平-徐汇区-2022-2026.csv')
            if r['years_included'] == '5']
    trend = rd(f'{A}/趋势分析-徐汇区-2022-2026.csv')
    fails = []
    sgn = lambda v: 1 if v > 0 else -1 if v < 0 else 0

    # --- 1. 覆盖与唯一性 ---
    codes_w = {r['junior_high_school_code'] for r in wide}
    codes_t = {r['junior_high_school_code'] for r in trend}
    print(f'[1] 宽表 CORE {len(wide)} 所 / 趋势表 {len(trend)} 所；编号一致: '
          f'{codes_w == codes_t}')
    if codes_w != codes_t:
        fails.append('覆盖')

    # --- 2. 基准中位独立重算 ---
    med = {}
    for y in YEARS:
        med[y] = st.median(sorted(float(r[f'mean_score_base4_{y}']) for r in wide))
    print(f'[2] CORE 中位独立重算: {[round(med[y], 2) for y in YEARS]}')

    # --- 3. rel / sen / spearman / 去尾 / 留一 逐校复算 ---
    bad = []
    for r in trend:
        c = r['junior_high_school_code']
        w = next(x for x in wide if x['junior_high_school_code'] == c)
        pts = [(y, float(w[f'mean_score_base4_{y}']) - med[y]) for y in YEARS]
        s = sen(pts)
        sp = spearman(pts)
        d26 = sen(pts[:-1])
        loo = [sen([p for p in pts if p[0] != y]) for y in YEARS]
        c1 = sgn(s) == sgn(sp) and sgn(s) != 0 and abs(s) >= SEN_MIN
        c2 = sgn(d26) == sgn(s)
        c3 = all(sgn(v) == sgn(s) for v in loo)
        want_pass = c1 and c2 and c3
        want_dir = ('上升' if s > 0 else '下降') if want_pass else '无趋势'
        got_pass = r['passed'] == 'True'
        if got_pass != want_pass or r['direction'] != want_dir:
            bad.append((c, r['direction'], want_dir, got_pass, want_pass))
        # 比对时按产物的小数位数取整（rel/z 两位，sen/spearman/去尾 三位）
        for key, val, nd in ((f'rel_{YEARS[0]}', pts[0][1], 2), ('sen', s, 3),
                             ('spearman', sp, 3), ('sen_drop26', d26, 3)):
            if abs(float(r[key]) - round(val, nd)) > 1e-9:
                bad.append((c, key, r[key], round(val, nd)))
    print(f'[3] rel/统计量/判定 不符项: {len(bad)} {bad[:4]}')
    if bad:
        fails.append('统计量复算')

    # --- 4. 收敛回归独立重算 ---
    x = [float(r[f'rel_{YEARS[0]}']) for r in trend]
    yv = [float(r[f'rel_{YEARS[-1]}']) - float(r[f'rel_{YEARS[0]}']) for r in trend]
    n = len(x)
    cov = sum((a - st.mean(x)) * (b - st.mean(yv)) for a, b in zip(x, yv)) / n
    var = sum((a - st.mean(x)) ** 2 for a in x) / n
    b = cov / var
    a = st.mean(yv) - b * st.mean(x)
    res = [c - (a + b * xi) for xi, c in zip(x, yv)]
    r2 = 1 - sum(v ** 2 for v in res) / sum((c - st.mean(yv)) ** 2 for c in yv)
    print(f'[4] 收敛回归独立重算: b={b:.4f}  R²={r2:.4f}  残差SD={st.pstdev(res):.4f}')
    bad4 = [(r['junior_high_school_code'], r['residual_z'], round(v / st.pstdev(res), 2))
            for r, v in zip(trend, res)
            if abs(float(r['residual_z']) - round(v / st.pstdev(res), 2)) > 1e-9]
    print(f'    残差 z 不符项: {len(bad4)} {bad4[:4]}')
    if bad4:
        fails.append('收敛诊断复算')

    # --- 5. 关键结论点复核 ---
    passed = [r for r in trend if r['passed'] == 'True']
    beyond = sorted([r for r in passed if r['beyond_convergence'] == 'True'],
                    key=lambda r: -float(r['residual']))
    flip3 = [r['junior_high_school'] for r in passed
             if sgn(float(r['sen'])) != sgn(float(r['sen_recent3']))]
    uneven = [r['junior_high_school'] for r in trend
              if r['pairs_uniform'] != 'True']
    print(f'[5] 通过严格三重判定: {len(passed)} 所（报告写 11）')
    print(f'    超出收敛解释: {len(beyond)} 所 -> '
          f'{[(r["junior_high_school"], r["direction"], r["residual_z"]) for r in beyond]}')
    print(f'    近3年方向翻转: {flip3}')
    print(f'    基线对数不齐: {uneven}')
    if len(passed) != 11 or len(beyond) != 2 or len(flip3) != 1:
        fails.append('关键结论点')

    # --- 6. 换基准互校独立重算 ---
    med_all = {y: st.median(sorted(float(r[f'mean_score_base4_{y}'])
                                   for r in rd(f'{A}/宽表-初中水平-徐汇区-2022-2026.csv')
                                   if r[f'mean_score_base4_{y}']))
               for y in YEARS}
    bad6 = []
    for r in trend:
        c = r['junior_high_school_code']
        w = next(x for x in wide if x['junior_high_school_code'] == c)
        s2 = sen([(y, float(w[f'mean_score_base4_{y}']) - med_all[y]) for y in YEARS])
        if abs(s2 - float(r['sen_base_all'])) > 5e-3:
            bad6.append((c, r['sen_base_all'], round(s2, 3)))
    print(f'[6] 换基准 sen 不符项: {len(bad6)} {bad6[:4]}')
    if bad6:
        fails.append('换基准复算')

    print()
    print('门禁：', '✅ 全部通过' if not fails else f'❌ 未通过 {fails}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
