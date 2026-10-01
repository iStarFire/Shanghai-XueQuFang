# -*- coding: utf-8 -*-
"""主口径 v2（2.3 计算）：年内标准化聚合排名。

design.md 口径：
- 基线 5 校：042001 二中 / 042008 南模 / 042035 位育 / 043015 南洋 / 042036 复附徐汇
  （复附徐汇 2023 年起才有线；2022 自动退化为 4 校 —— 口径断点，已在 design/报告标注）
- mean_score_base5(c,y) = 当年基线可得线的均值；逐年名次 = 当年全部有数据公办内平均名次法
- P_i = mean(1-(rank-1)/(n-1))（主口径）；Z_i / ZR_i 同 A6（辅口径）
- 排名样本：覆盖 >=4 年；<4 年保留明细不排名（ranked=0）
只读宽表既有列，不改动任何既有文件。
"""
import csv
import statistics as st

D = "/Users/ivan/workspace/github/Shanghai-XueQuFang/analysis/徐汇区公办初中名额分配到校分析"
OUT = f"{D}/rank-标准化-徐汇区-2022-2026.csv"
YEARS = [2022, 2023, 2024, 2025, 2026]
BASE5 = ["042001", "042008", "042035", "043015", "042036"]


def load(name):
    with open(f"{D}/{name}", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v else None


def build():
    R = load("宽表-初中水平-徐汇区-2022-2026.csv")
    # ---- base5 均分与逐年名次 ----
    score5, rank5 = {}, {y: {} for y in YEARS}   # 名次按年分字典：不同年份同分不可互串
    pool = {y: [] for y in YEARS}
    for r in R:
        c = r["junior_high_school_code"]
        for y in YEARS:
            vs = [F(r.get(f"score_{h}_{y}")) for h in BASE5]
            vs = [v for v in vs if v is not None]
            if vs:
                score5[(c, y)] = st.fmean(vs)
                pool[y].append(score5[(c, y)])
    for y in YEARS:
        for v in pool[y]:
            better = sum(1 for w in pool[y] if w > v)
            eq = sum(1 for w in pool[y] if w == v)
            rank5[y][v] = better + (eq + 1) / 2
    # ---- 标准化参数 ----
    n = {y: len(pool[y]) for y in YEARS}
    mu = {y: st.fmean(pool[y]) for y in YEARS}
    sg = {y: st.pstdev(pool[y]) for y in YEARS}
    med = {y: st.median(pool[y]) for y in YEARS}
    def iqr(v):
        s = sorted(v)
        return s[len(s) * 3 // 4] - s[len(s) // 4]
    iq = {y: iqr(pool[y]) for y in YEARS}
    # score5 -> rank 映射（当年，查当年名次表）
    rmap = {}
    for (c, y), v in score5.items():
        rmap[(c, y)] = rank5[y][v]
    # ---- 聚合 ----
    out = []
    for r in R:
        c = r["junior_high_school_code"]
        ps, zs, zrs, yks = [], [], [], []
        for y in YEARS:
            if (c, y) not in score5:
                continue
            x, k = score5[(c, y)], rmap[(c, y)]
            ps.append(1 - (k - 1) / (n[y] - 1))
            zs.append((x - mu[y]) / sg[y])
            zrs.append((x - med[y]) / (iq[y] / 1.349))
            yks.append(y)
        if not ps:
            continue
        old = F(r.get("mean_rank_base4_avg"))
        out.append({
            "junior_high_school": r["junior_high_school"],
            "junior_high_school_code": c,
            "years_covered": ";".join(str(y) for y in yks),
            "n_years": len(ps),
            "P": st.fmean(ps), "Z": st.fmean(zs), "ZR": st.fmean(zrs),
            "old_mean_rank_base4_avg": old,
        })
    ranked = [o for o in out if o["n_years"] >= 4]
    for o in out:
        o["ranked"] = int(o in ranked)

    def rk(vals, key, rev):
        s = sorted(vals, key=key, reverse=rev)
        pos = {}
        for i, v in enumerate(s, 1):
            same = [j for j, w in enumerate(s, 1) if key(w) == key(v)]
            pos[id(v)] = st.fmean(same)
        return {v["junior_high_school_code"]: pos[id(v)] for v in s}

    rP = rk(ranked, lambda v: v["P"], True)
    rZ = rk(ranked, lambda v: v["Z"], True)
    rZR = rk(ranked, lambda v: v["ZR"], True)
    old23 = [o for o in ranked if o["old_mean_rank_base4_avg"] is not None]
    rOld = rk(old23, lambda v: v["old_mean_rank_base4_avg"], False)
    for o in out:
        c = o["junior_high_school_code"]
        o["rank_P"] = rP.get(c, "")
        o["rank_Z"] = rZ.get(c, "")
        o["rank_ZR"] = rZR.get(c, "")
        o["rank_old"] = rOld.get(c, "")
        o["shift"] = (rOld[c] - rP[c]) if c in rOld and c in rP else ""

    cols = ["junior_high_school", "junior_high_school_code", "years_covered",
            "n_years", "ranked", "P", "Z", "ZR",
            "rank_P", "rank_Z", "rank_ZR",
            "old_mean_rank_base4_avg", "rank_old", "shift"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for o in sorted(out, key=lambda o: (-(o["ranked"]), o["rank_P"] if o["ranked"] else 99)):
            w.writerow({c: (f"{o[c]:.4f}" if isinstance(o[c], float) else o[c])
                        for c in cols})

    # ---- 对照统计 ----
    print("== 逐年参数（base5）==")
    for y in YEARS:
        print(f"{y}: n={n[y]} mu={mu[y]:.2f} sigma={sg[y]:.2f} med={med[y]:.1f} iqr={iq[y]:.1f}")
    print(f"\n排名样本 {len(ranked)} 所（覆盖>=4年），明细 {len(out)-len(ranked)} 所不排名")
    print("\n== 新口径排名（按 P）==")
    for o in sorted(ranked, key=lambda o: o["rank_P"]):
        print(f"{o['rank_P']:>5.1f} {o['junior_high_school'].replace('上海市',''):<26}"
              f"P={o['P']:.3f} Z={o['Z']:+.2f} ZR={o['ZR']:+.2f} "
              f"旧均名={o['old_mean_rank_base4_avg'] or '—'} 旧名次={o['rank_old'] or '—'} "
              f"偏移={o['shift']}")
    shifts = [abs(float(o["shift"])) for o in ranked if o["shift"] != ""]
    print(f"\n23 所新旧偏移: 最大 {max(shifts):.0f}, 非零 {sum(1 for s in shifts if s > 0)} 所")
    t3 = sorted(ranked, key=lambda o: o["rank_P"])[:3]
    t3o = sorted(old23, key=lambda o: o["rank_old"])[:3]
    print("新前3:", [o["junior_high_school"] for o in t3])
    print("旧前3:", [o["junior_high_school"] for o in t3o])
    print(f"写出 {OUT}")


if __name__ == "__main__":
    build()
