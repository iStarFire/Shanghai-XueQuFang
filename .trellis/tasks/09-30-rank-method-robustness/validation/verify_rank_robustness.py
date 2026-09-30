# -*- coding: utf-8 -*-
"""2.4 独立复算：不 import 2.3 的 rank_robustness.py，不读宽表。

路径：原始分数线 CSV → 直接算 mean_score_base4 → 逐年标准化 → Z/ZR/P
→ 与交付 CSV rank-稳健性-徐汇区-2022-2026.csv 逐值比对。
同时抽样回源：打印 3 所学校 × 5 年的 source_doc/source_page。
"""
import csv
from collections import defaultdict

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{BASE}/analysis/徐汇区公办初中名额分配到校分析"
BASE4 = {"042001", "042008", "042035", "043015"}
YEARS = [2022, 2023, 2024, 2025, 2026]

# ---- 从原始分数线重建 mean_score_base4（与 2.3 不同的数据路径）----
# 口径：仅公办（名录+别名表判定，与宽表构建口径一致）；base4 = 4 所区属市重点
rows = list(csv.DictReader(open(
    f"{BASE}/data/徐汇区/学校/名额到校最低分数线-徐汇区-2022-2026.csv",
    encoding="utf-8-sig")))
alias = list(csv.DictReader(open(
    f"{BASE}/data/徐汇区/学校/初中校名别名表-徐汇区.csv", encoding="utf-8-sig")))
roster = list(csv.DictReader(open(
    f"{BASE}/data/徐汇区/学校/初中名录-公办民办-徐汇区-2026.csv",
    encoding="utf-8-sig")))
name2code = {}
for a in alias:
    name2code[a["canonical_name"]] = a["school_code"]
    for al in (a["alias_name"] or "").split(";"):
        if al:
            name2code[al] = a["school_code"]
minban = {name2code[r["school_name"]] for r in roster
          if r["ownership"] == "民办"}

by_cy = defaultdict(list)      # (code, year) -> [(score, doc, page)]
for r in rows:
    if (r["senior_high_school_code"] in BASE4 and r["min_score"]
            and r["junior_high_school_code"] not in minban):
        by_cy[(r["junior_high_school_code"], int(r["year"]))].append(
            (float(r["min_score"]), r["source_doc"], r["source_page"]))

score = {k: sum(v[0] for v in g) / len(g) for k, g in by_cy.items()}

# ---- 数据链路核验：独立重建的 mean_score_base4 vs 宽表（全量）----
wide = list(csv.DictReader(open(
    f"{D}/宽表-初中水平-徐汇区-2022-2026.csv", encoding="utf-8-sig")))
link_bad = link_n = 0
for r in wide:
    for y in YEARS:
        v = r.get(f"mean_score_base4_{y}")
        mine = score.get((r["junior_high_school_code"], y))
        if v and mine is not None:
            link_n += 1
            # 宽表存 3 位小数（build_wide num(x, nd=3)），容差取舍入半格
            if abs(float(v) - mine) > 5.1e-4:
                link_bad += 1
                print(f"LINK MISMATCH {r['junior_high_school']} {y}: "
                      f"宽表 {v} vs 原始重建 {mine}")
        elif bool(v) != (mine is not None):
            link_bad += 1
            print(f"LINK 存在性不一致 {r['junior_high_school']} {y}")
print(f"数据链路核验: {link_n} 个校年均值逐值比对(容差5.1e-4), 不一致 {link_bad}")

# ---- 独立实现：pandas 风格的分组聚合（与 2.3 的逐行循环不同序）----
schools = sorted({c for (c, y) in by_cy})
per_year = {y: {c: score[(c, y)] for c in schools if (c, y) in score}
            for y in YEARS}
print("逐年样本量:", {y: len(per_year[y]) for y in YEARS})
stat = {}
for y in YEARS:
    xs = sorted(per_year[y].values())
    n = len(xs)
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / n          # 总体方差
    q1, q3 = xs[n // 4], xs[n * 3 // 4]
    stat[y] = (n, mu, var ** 0.5, xs[n // 2], q3 - q1)

def avg_rank(vals):                                    # 平均名次法（分高=名次好）
    out = {}
    for v in vals:
        better = sum(1 for t in vals if t > v)
        eq = sum(1 for t in vals if t == v)
        out[v] = better + (eq + 1) / 2
    return out

ranks = {y: avg_rank(list(per_year[y].values())) for y in YEARS}

def agg(c, f):
    vs = [f(c, y) for y in YEARS if (c, y) in score]
    return sum(vs) / len(vs) if vs else None

Z = {c: agg(c, lambda c, y: (score[(c, y)] - stat[y][1]) / stat[y][2])
     for c in schools}
ZR = {c: agg(c, lambda c, y: (score[(c, y)] - stat[y][3])
             / (stat[y][4] / 1.349)) for c in schools}
P = {c: agg(c, lambda c, y: 1 - (ranks[y][score[(c, y)]] - 1)
            / (stat[y][0] - 1)) for c in schools}

# ---- 与交付 CSV 比对 ----
out = list(csv.DictReader(open(f"{D}/rank-稳健性-徐汇区-2022-2026.csv",
                               encoding="utf-8-sig")))
bad = 0
compared = 0
max_dev = 0.0
for r in out:
    c = r["junior_high_school_code"]
    for col, ref in [("Z", Z[c]), ("ZR", ZR[c]), ("P", P[c])]:
        compared += 1
        dev = abs(float(r[col]) - ref)
        max_dev = max(max_dev, dev)
        # 交付值链路含宽表 3 位小数舍入 + 本表 4 位小数舍入，容差 5e-3
        if dev > 5e-3:
            bad += 1
            print(f"MISMATCH {r['junior_high_school']} {col}: "
                  f"交付 {r[col]} vs 独立 {ref:.6f}")
print(f"逐值比对: {compared} 项, 超容差不一致 {bad} 项, 最大偏差 {max_dev:.5f}")
print(f"逐值比对: {compared} 项, 不一致 {bad} 项")
# n_years 与每年参数抽核
for r in out[:3]:
    c = r["junior_high_school_code"]
    ny = sum(1 for y in YEARS if (c, y) in score)
    if int(r["n_years"]) != ny:
        bad += 1
        print(f"n_years MISMATCH {r['junior_high_school']}: "
              f"{r['n_years']} vs {ny}")
print(f"含 n_years 复核后不一致合计: {bad} 项")

# ---- 抽样回源（3 所 × 5 年，打印来源定位）----
print("\n== 抽样回源 ==")
core3 = [r["junior_high_school_code"] for r in out[:1]] + \
        [r["junior_high_school_code"] for r in out[len(out)//2:len(out)//2+1]] + \
        [r["junior_high_school_code"] for r in out[-1:]]
for c in core3:
    name = next(r["junior_high_school"] for r in out
                if r["junior_high_school_code"] == c)
    for y in YEARS:
        g = by_cy.get((c, y))
        if g:
            sc, doc, page = g[0]
            print(f"{name} {y}: base4={len(g)}项 均值={score[(c,y)]:.2f} "
                  f"来源={doc} 第{page}页")
        else:
            print(f"{name} {y}: 无 base4 数据")
