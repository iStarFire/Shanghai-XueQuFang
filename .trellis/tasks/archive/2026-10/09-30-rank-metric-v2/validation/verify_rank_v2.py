# -*- coding: utf-8 -*-
"""2.4 独立复算：不 import 2.3 脚本，不读宽表。

路径：原始分数线 CSV → base5 均分（公办过滤独立实现）→ 逐年名次 → P/Z/ZR
→ 与交付 CSV rank-标准化-徐汇区-2022-2026.csv 逐值比对 + 抽样回源。
"""
import csv
from collections import defaultdict

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{BASE}/analysis/徐汇区公办初中名额分配到校分析"
BASE5 = ["042001", "042008", "042035", "043015", "042036"]
YEARS = [2022, 2023, 2024, 2025, 2026]

lines = defaultdict(dict)          # (code, year) -> {hs: score}
for r in csv.DictReader(open(
        f"{BASE}/data/徐汇区/学校/名额到校最低分数线-徐汇区-2022-2026.csv",
        encoding="utf-8-sig")):
    if r["min_score"] and r["senior_high_school_code"] in BASE5:
        lines[(r["junior_high_school_code"], int(r["year"]))][
            r["senior_high_school_code"]] = float(r["min_score"])

alias = list(csv.DictReader(open(
    f"{BASE}/data/徐汇区/学校/初中校名别名表-徐汇区.csv", encoding="utf-8-sig")))
roster = list(csv.DictReader(open(
    f"{BASE}/data/徐汇区/学校/初中名录-公办民办-徐汇区-2026.csv", encoding="utf-8-sig")))
n2c = {}
for a in alias:
    n2c[a["canonical_name"]] = a["school_code"]
    for al in (a["alias_name"] or "").split(";"):
        if al:
            n2c[al] = a["school_code"]
minban = {n2c[r["school_name"]] for r in roster if r["ownership"] == "民办"}

mean5 = {}                          # (code, year) -> mean over available BASE5
for (c, y), d in lines.items():
    if c in minban:
        continue
    vs = [d[h] for h in BASE5 if h in d]
    if vs:
        mean5[(c, y)] = sum(vs) / len(vs)

# 数据链路核验：base5 均分 vs 4校基线（宽表）——2022 年应完全一致
wide = list(csv.DictReader(open(f"{D}/宽表-初中水平-徐汇区-2022-2026.csv",
                                encoding="utf-8-sig")))
lk_bad = lk_n = 0
for r in wide:
    for y in YEARS:
        v = r.get(f"mean_score_base4_{y}")
        mine = mean5.get((r["junior_high_school_code"], y))
        if v and mine is not None:
            # 2022 无复附线 → base5 == base4；2023+ 增加复附线，允许不同
            if y == 2022 and abs(float(v) - mine) > 5.1e-4:
                lk_bad += 1
                print(f"LINK 2022 MISMATCH {r['junior_high_school']}: {v} vs {mine}")
            if y == 2022:
                lk_n += 1
print(f"数据链路核验(2022, base5应与base4一致): {lk_n} 校, 不一致 {lk_bad}")

# 逐年名次与标准化
per = {y: {} for y in YEARS}
for (c, y), v in mean5.items():
    per[y][c] = v
stat = {}
for y in YEARS:
    xs = list(per[y].values())
    n = len(xs)
    mu = sum(xs) / n
    sg = (sum((x - mu) ** 2 for x in xs) / n) ** 0.5
    s = sorted(xs)
    med = (s[(n - 1) // 2] + s[n // 2]) / 2   # st.median 口径（与 2.3/design 一致）
    iqr = s[n * 3 // 4] - s[n // 4]
    stat[y] = (n, mu, sg, med, iqr)

P, Z, ZR = defaultdict(list), defaultdict(list), defaultdict(list)
for y in YEARS:
    vals = per[y]
    for c, v in vals.items():
        better = sum(1 for w in vals.values() if w > v)
        eq = sum(1 for w in vals.values() if w == v)
        k = better + (eq + 1) / 2
        n, mu, sg, med, iqr = stat[y]
        P[c].append(1 - (k - 1) / (n - 1))
        Z[c].append((v - mu) / sg)
        ZR[c].append((v - med) / (iqr / 1.349))

out = list(csv.DictReader(open(f"{D}/rank-标准化-徐汇区-2022-2026.csv",
                               encoding="utf-8-sig")))
bad = cmp = 0
mx = 0.0
for r in out:
    c = r["junior_high_school_code"]
    for col, series in [("P", P[c]), ("Z", Z[c]), ("ZR", ZR[c])]:
        ref = sum(series) / len(series)
        dev = abs(float(r[col]) - ref)
        mx = max(mx, dev)
        cmp += 1
        if dev > 5e-3:
            bad += 1
            print(f"MISMATCH {r['junior_high_school']} {col}: 交付 {r[col]} vs 独立 {ref:.4f}")
    ny = len(P[c])
    if int(r["n_years"]) != ny:
        bad += 1
        print(f"n_years MISMATCH {r['junior_high_school']}: {r['n_years']} vs {ny}")
print(f"逐值比对: {cmp} 项(含n_years), 超容差 {bad} 项, 最大偏差 {mx:.5f}")

# 抽样回源：2026 复附徐汇线（新基线成员）
print("\n== 抽样回源（复附徐汇线 2026，前5条）==")
doc_page = {}
for r in csv.DictReader(open(
        f"{BASE}/data/徐汇区/学校/名额到校最低分数线-徐汇区-2022-2026.csv",
        encoding="utf-8-sig")):
    if r["year"] == "2026" and r["senior_high_school_code"] == "042036":
        doc_page[r["junior_high_school"]] = (r["min_score"], r["source_doc"], r["source_page"])
for i, (nm, (s, doc, pg)) in enumerate(doc_page.items()):
    if i >= 5:
        break
    print(f"{nm}: {s} 分 来源={doc} 第{pg}页")
