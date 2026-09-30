# -*- coding: utf-8 -*-
"""A6 排名方法稳健性检验（2.3 计算）。

主口径（既有，不改动）：mean_rank_base4_avg = 5 年期内名次等权均值（交集基线）。
本脚本产出两个辅口径做对照（design.md）：
  Z_i  年内 z-score 聚合：z_it = (x_it - μ_t) / σ_t，x = mean_score_base4
       μ_t/σ_t 用当年全部有数据学校；σ_t = 总体标准差（与宽表 var 口径一致）
  ZR_i 稳健版：z = (x - median_t) / (IQR_t / 1.349)，IQR 用有序样本取位法
       Q1=s[⌊n/4⌋]、Q3=s[⌊3n/4⌋]（n 为当年样本数，s 升序）
  P_i  年内分位聚合：pct_it = 1 - (rank_it - 1) / (n_t - 1)，rank 用宽表现有
       mean_rank_base4_{t}（平均名次法，含并列）
仅读宽表，不改动任何既有文件。输出 CSV 与对照统计。
"""
import csv
import statistics as st

D = "/Users/ivan/workspace/github/Shanghai-XueQuFang/analysis/徐汇区公办初中名额分配到校分析"
OUT = f"{D}/rank-稳健性-徐汇区-2022-2026.csv"
YEARS = [2022, 2023, 2024, 2025, 2026]


def load(name):
    with open(f"{D}/{name}", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fnum(x):
    return float(x) if x else None


def iqr_pos(vals):
    """有序样本取位法四分位差（与设计文档一致）。"""
    s = sorted(vals)
    return s[len(s) * 3 // 4] - s[len(s) // 4]


def build():
    R = load("宽表-初中水平-徐汇区-2022-2026.csv")
    # 每年全部有数据学校的 mean_score_base4 / mean_rank_base4（标准化分母样本）
    pool_score = {y: [] for y in YEARS}
    pool_rank = {y: [] for y in YEARS}
    for r in R:
        for y in YEARS:
            s = fnum(r.get(f"mean_score_base4_{y}"))
            k = fnum(r.get(f"mean_rank_base4_{y}"))
            if s is not None:
                pool_score[y].append(s)
            if k is not None:
                pool_rank[y].append(k)

    stat = {}
    for y in YEARS:
        xs = pool_score[y]
        n = len(xs)
        stat[y] = {
            "n": n,
            "mu": st.fmean(xs),
            "sigma": st.pstdev(xs),
            "med": st.median(xs),
            "iqr": iqr_pos(xs),
        }

    rows = []
    for r in R:
        if r["years_included"] != "5":
            continue
        zs, zrs, ps = [], [], []
        for y in YEARS:
            x = fnum(r.get(f"mean_score_base4_{y}"))
            k = fnum(r.get(f"mean_rank_base4_{y}"))
            s = stat[y]
            if x is not None:
                zs.append((x - s["mu"]) / s["sigma"])
                zrs.append((x - s["med"]) / (s["iqr"] / 1.349))
            if k is not None:
                ps.append(1 - (k - 1) / (s["n"] - 1))
        rows.append({
            "junior_high_school": r["junior_high_school"],
            "junior_high_school_code": r["junior_high_school_code"],
            "n_years": len(zs),
            "mean_rank_base4_avg": fnum(r["mean_rank_base4_avg"]),
            "Z": st.fmean(zs),
            "ZR": st.fmean(zrs),
            "P": st.fmean(ps),
        })

    def rk(vals, key):
        """平均名次法；reverse=True 时值大=名次小（越好）。"""
        order = sorted(vals, key=key, reverse=True)
        out = {}
        for i, v in enumerate(order, 1):
            out[v["junior_high_school_code"]] = float(i)
        # 并列取平均名次
        for code in out:
            same = [i for i, v in enumerate(order, 1)
                    if key(v) == key(next(w for w in order
                                          if w["junior_high_school_code"] == code))]
            out[code] = st.fmean(same)
        return out

    rB = rk(rows, lambda v: -v["mean_rank_base4_avg"])   # 均名小=好
    rZ = rk(rows, lambda v: v["Z"])
    rZR = rk(rows, lambda v: v["ZR"])
    rP = rk(rows, lambda v: v["P"])

    for v in rows:
        c = v["junior_high_school_code"]
        v["rank_b4"], v["rank_Z"], v["rank_ZR"], v["rank_P"] = (
            rB[c], rZ[c], rZR[c], rP[c])
        v["shift_Z"] = rB[c] - rZ[c]
        v["shift_ZR"] = rB[c] - rZR[c]
        v["shift_P"] = rB[c] - rP[c]

    cols = ["junior_high_school", "junior_high_school_code", "n_years",
            "mean_rank_base4_avg", "Z", "ZR", "P",
            "rank_b4", "rank_Z", "rank_ZR", "rank_P",
            "shift_Z", "shift_ZR", "shift_P"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for v in sorted(rows, key=lambda v: v["rank_b4"]):
            w.writerow({c: (f"{v[c]:.4f}" if isinstance(v[c], float) else v[c])
                        for c in cols})

    # ---- 对照统计 ----
    def spearman(a, b):
        ra = {v["junior_high_school_code"]: a[v["junior_high_school_code"]] for v in rows}
        rb = {v["junior_high_school_code"]: b[v["junior_high_school_code"]] for v in rows}
        xs = [ra[c] for c in ra]
        ys = [rb[c] for c in ra]
        mx, my = st.fmean(xs), st.fmean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        return num / den

    def top3(rr):
        return sorted(rr, key=rr.get)[:3]

    print("== 逐年标准化参数 ==")
    for y in YEARS:
        s = stat[y]
        print(f"{y}: n={s['n']} mu={s['mu']:.2f} sigma={s['sigma']:.2f} "
              f"med={s['med']:.1f} iqr={s['iqr']:.1f}")
    print("\n== 前3成员（按 rank_b4 / rank_Z / rank_ZR / rank_P）==")
    nm = {v["junior_high_school_code"]: v["junior_high_school"] for v in rows}
    for label, rr in [("均名", rB), ("Z", rZ), ("ZR", rZR), ("P", rP)]:
        print(f"{label}: {[nm[c] for c in top3(rr)]}")
    print(f"\nSpearman(均名, Z)={spearman(rB, rZ):.4f}  "
          f"Spearman(均名, ZR)={spearman(rB, rZR):.4f}  "
          f"Spearman(均名, P)={spearman(rB, rP):.4f}")
    print("\n== |偏移|>=3 名次（Z 口径）==")
    for v in sorted(rows, key=lambda v: abs(v["shift_Z"]), reverse=True):
        if abs(v["shift_Z"]) >= 3:
            print(f"{v['junior_high_school']}: 均名第{v['rank_b4']:.0f} "
                  f"→ Z第{v['rank_Z']:.0f}（偏移{v['shift_Z']:+.0f}）")
    print("\n== |偏移|>=3 名次（P 口径）==")
    for v in sorted(rows, key=lambda v: abs(v["shift_P"]), reverse=True):
        if abs(v["shift_P"]) >= 3:
            print(f"{v['junior_high_school']}: 均名第{v['rank_b4']:.0f} "
                  f"→ P第{v['rank_P']:.0f}（偏移{v['shift_P']:+.0f}）")
    print("\n== ZR 与 Z 排序差异 ==")
    print(f"Spearman(Z, ZR)={spearman(rZ, rZR):.4f}")
    for v in sorted(rows, key=lambda v: abs(v["shift_ZR"]), reverse=True)[:5]:
        print(f"{v['junior_high_school']}: Z第{v['rank_Z']:.0f} "
              f"→ ZR第{v['rank_ZR']:.0f}（偏移{v['shift_ZR']:+.0f}）")
    print(f"\n写出 {OUT}")


if __name__ == "__main__":
    build()
