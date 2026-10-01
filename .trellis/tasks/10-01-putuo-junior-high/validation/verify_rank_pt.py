# -*- coding: utf-8 -*-
"""2.4 独立复算（普陀）：不 import build_wide_pt.py，从长表 CSV 走另一条实现。

路径：分数线长表 → base4 均分（按 (校,年) 分组平均，与 2.3 的索引式循环不同）
     → 逐年名次（逐值比较法）→ P/Z/ZR → 与交付 CSV 逐值比对 + 抽样回源 PDF。
"""
import csv, statistics as st, os, random

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
QU = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']
YEARS = [2022, 2023, 2024, 2025, 2026]


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


rows = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')

# ---- 分组聚合（不同实现：先 collect 再平均）----
bucket = {}
for r in rows:
    if r['senior_high_school'] in QU:
        bucket.setdefault((r['junior_high_school'], int(r['year'])), []).append(float(r['min_score']))
mean4 = {k: sum(v) / len(v) for k, v in bucket.items()}

# ---- 逐年统计与名次（逐值比较）----
P, Z, ZR = {}, {}, {}
for y in YEARS:
    vals = {c: v for (c, yy), v in mean4.items() if yy == y}
    xs = list(vals.values())
    n = len(xs)
    mu = sum(xs) / n
    sg = (sum((x - mu) ** 2 for x in xs) / n) ** 0.5
    s = sorted(xs)
    med = (s[(n - 1) // 2] + s[n // 2]) / 2
    iqr = s[n * 3 // 4] - s[n // 4]
    for c, v in vals.items():
        better = sum(1 for w in xs if w > v)
        eq = sum(1 for w in xs if w == v)
        k = better + (eq + 1) / 2
        P.setdefault(c, []).append(1 - (k - 1) / (n - 1))
        Z.setdefault(c, []).append((v - mu) / sg)
        ZR.setdefault(c, []).append((v - med) / (iqr / 1.349))

# ---- 比对交付 CSV ----
out = load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')
bad = cmp = 0
mx = 0.0
for r in out:
    c = r['junior_high_school']
    if r['n_years'] == '0':
        continue
    for col, series in [('P', P[c]), ('Z', Z[c]), ('ZR', ZR[c])]:
        ref = sum(series) / len(series)
        dev = abs(float(r[col]) - ref)
        mx = max(mx, dev)
        cmp += 1
        if dev > 5e-3:
            bad += 1
            print(f'MISMATCH {c} {col}: 交付 {r[col]} vs 独立 {ref:.4f}')
    if int(r['n_years']) != len(P[c]):
        bad += 1
        print(f'n_years MISMATCH {c}: {r["n_years"]} vs {len(P[c])}')
print(f'逐值比对: {cmp} 项, 超容差 {bad} 项, 最大偏差 {mx:.5f}')

# ---- 宽表核对（均名/中位/方差）----
wide = load(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv')
bad2 = 0
for r in wide:
    c = r['junior_high_school']
    vals = [v for (cc, y), v in mean4.items() if cc == c]
    if not vals:
        continue
    n = len(vals)
    # 用逐年名次复算均名
    per_rank = []
    for y in YEARS:
        if (c, y) not in mean4:
            continue
        same = {cc: v for (cc, yy), v in mean4.items() if yy == y}
        v = mean4[(c, y)]
        better = sum(1 for w in same.values() if w > v)
        eq = sum(1 for w in same.values() if w == v)
        per_rank.append(better + (eq + 1) / 2)
    if r['mean_rank_base4_avg']:
        dev = abs(float(r['mean_rank_base4_avg']) - st.fmean(per_rank))
        if dev > 5e-3:
            bad2 += 1
            print(f'宽表 MISMATCH {c}: 交付 {r["mean_rank_base4_avg"]} vs 独立 {st.fmean(per_rank):.4f}')
    if r['mean_rank_base4_var'] and len(per_rank) > 1:
        if abs(float(r['mean_rank_base4_var']) - st.pvariance(per_rank)) > 5e-3:
            bad2 += 1
            print(f'宽表方差 MISMATCH {c}')
print(f'宽表均名/方差比对: 不一致 {bad2} 项')

# ---- 抽样回源 ----
random.seed(11)
print('\n== 抽样回源 ==')
for r in random.sample(rows, 3):
    import fitz
    doc = fitz.open(f'{D_S}/{r["source_doc"]}')
    txt = ''.join(doc[int(r['source_page']) - 1].get_text('text').split())
    ok = r['junior_high_school'] in txt and r['min_score'].rstrip('0').rstrip('.') in txt.replace('.0', '')
    print(f'  {r["junior_high_school"]}/{r["senior_high_school"]} {r["min_score"]} '
          f'页{r["source_page"]}: {"命中" if ok else "未命中"}')
