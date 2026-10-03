#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦公办初中名额到校分析 —— 公共计算层。

关键约束（不可更改）：
- 排名池按**当年在办学校**（用户明确要求），分位 P 在当年池内计算
- 民办全部排除；黄浦学校 2024 并入大同 → 逐年出现、五年主表不出现、不做趋势
- SEN 用标准 OLS 斜率（分母 Σ(y-ȳ)²，**不得多乘 n**；嘉定曾错，低估 4-5 倍）
- 离散度双口径（当年池 / 固定池），同向才给方向结论
"""
import csv
import os
import statistics as st
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/黄浦区/学校'
A = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析'
SC = f'{D}/名额到校最低分数线-黄浦区-2022-2026.csv'
PL = f'{D}/名额到校计划-黄浦区-2022-2026.csv'
YEARS = ['2022', '2023', '2024', '2025', '2026']
PRIV = lambda n: any(k in n for k in ('民办', '双语', '震旦'))
HISTORIC = {'上海市黄浦学校'}
BREAK_2024 = {'上海市大同初级中学'}
WT = {'wq': [1, 1, 1, 1, 1], 'lin': [1, 2, 3, 4, 5],
      'exp': [1, 2, 4, 8, 16], 'r3': [0, 0, 1, 1, 1]}


def num(v, nd=4):
    return '' if v is None or v == '' else round(v, nd)


def load():
    with open(SC, encoding='utf-8-sig') as f:
        S = {(r['year'], r['junior_high_school'], r['senior_high_school']):
             float(r['min_score']) for r in csv.DictReader(f)}
    with open(PL, encoding='utf-8-sig') as f:
        Q = {(r['year'], r['junior_high_school'], r['senior_high_school']):
             int(r['quota']) for r in csv.DictReader(f)}
    return S, Q


def build_pairs(S, Q):
    """(年,初中,招生学校) -> (分数, 名额)，仅保留有分数的组合。"""
    out, unpaired = {}, defaultdict(list)
    for k, q in Q.items():
        if q > 0:
            if k in S:
                out[k] = (S[k], q)
            else:
                unpaired[k[0]].append(k)
    return out, unpaired


def wmean(pairs, y, c, weighted=True):
    num_ = den = 0.0
    n = 0
    hi = lo = None
    for (yy, j, s), (sc, q) in pairs.items():
        if yy != y or j != c:
            continue
        num_ += (q if weighted else 1) * sc
        den += q if weighted else 1
        n += 1
        hi = sc if hi is None else max(hi, sc)
        lo = sc if lo is None else min(lo, sc)
    return (num_ / den, int(den), n, hi, lo) if den else (None, 0, 0, None, None)


def ols_slope(xs, ys):
    """标准 OLS 斜率。分母 Σ(x-x̄)²，不乘 n。"""
    if len(xs) < 2:
        return None
    mx, my = st.fmean(xs), st.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else None


def spearman(x, y):
    def rk(v):
        s = sorted(v)
        return [sum(1 for t in s if t < a) + (sum(1 for t in s if t == a) + 1) / 2
                for a in v]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    d = (sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5
    return sum((p - mx) * (q - my) for p, q in zip(rx, ry)) / d if d else None


def pct_rank(val, vals):
    """升序分位：0=最弱，并列取平均秩。"""
    n = len(vals)
    if n < 2:
        return 0.0
    return (sum(1 for v in vals if v < val)
            + (sum(1 for v in vals if v == val) - 1) / 2) / (n - 1)


def dispersion(vals):
    v = sorted(vals)
    n = len(v)
    q = st.quantiles(v, n=4) if n >= 4 else [v[0], v[0], v[0]]
    k = max(1, round(n * 0.2))
    sd = st.pstdev(v)
    return {'n': n, 'iqr': q[2] - q[0], 'sd': sd, 'cv': sd / st.fmean(v),
            'range': v[-1] - v[0], 'top_bottom': st.fmean(v[-k:]) - st.fmean(v[:k])}


def rkmap(d, pool):
    return {c: i for i, c in enumerate(sorted(pool, key=lambda c: -d[c]), 1)}


def write(name, cols, rows):
    with open(f'{A}/{name}', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f'  写出 {name}（{len(rows)} 行 × {len(cols)} 列）')


def compute():
    """算全部中间量，返回 dict 供产出脚本与门禁复用。"""
    S, Q = load()
    pairs, unpaired = build_pairs(S, Q)
    gov = sorted({k[1] for k in pairs if not PRIV(k[1])})

    POOL_Y, WQ, EQ, QUOTA, NPAIR, HI, LO, UNP = {}, {}, {}, {}, {}, {}, {}, {}
    for y in YEARS:
        m = {}
        for c in gov:
            w, q, n, hi, lo = wmean(pairs, y, c, True)
            if w is None:
                continue
            m[c] = w
            WQ[(c, y)], QUOTA[(c, y)], NPAIR[(c, y)] = w, q, n
            HI[(c, y)], LO[(c, y)] = hi, lo
            EQ[(c, y)] = wmean(pairs, y, c, False)[0]
        POOL_Y[y] = sorted(m)
        UNP[y] = len(unpaired.get(y, []))

    P5 = sorted(c for c in gov if all(c in POOL_Y[y] for y in YEARS))
    P3 = sorted(c for c in gov if sum(c in POOL_Y[y] for y in YEARS) >= 3)
    HIST = [c for c in P3 if c not in P5]

    # 分位 P / Z：均在当年池内计算
    P, PEQ, Z, ZR = {}, {}, {}, {}
    for y in YEARS:
        pool = POOL_Y[y]
        for c in pool:
            P[(c, y)] = pct_rank(WQ[(c, y)], [WQ[(x, y)] for x in pool])
            PEQ[(c, y)] = pct_rank(EQ[(c, y)], [EQ[(x, y)] for x in pool])
        mu = st.fmean([WQ[(x, y)] for x in pool])
        sd = st.pstdev([WQ[(x, y)] for x in pool]) or 1e-9
        for c in pool:
            Z[(c, y)] = (WQ[(c, y)] - mu) / sd
    for c in P5:
        vs = [Z[(c, y)] for y in YEARS]
        m, s = st.fmean(vs), st.pstdev(vs) or 1e-9
        for y in YEARS:
            ZR[(c, y)] = (Z[(c, y)] - m) / s

    def agg(c, table, wt):
        pr = [(w, table[(c, y)]) for w, y in zip(wt, YEARS) if w > 0]
        s = sum(w for w, _ in pr)
        return sum(w * v for w, v in pr) / s if s else None

    P_wq = {c: agg(c, P, WT['wq']) for c in P5}
    P_eq = {c: agg(c, PEQ, WT['wq']) for c in P5}
    P_var = {v: {c: agg(c, P, w) for c in P5} for v, w in WT.items()}

    # rel / SEN
    REL, MED = {}, {}
    for y in YEARS:
        MED[y] = st.median([WQ[(x, y)] for x in POOL_Y[y]])
        for c in POOL_Y[y]:
            REL[(c, y)] = WQ[(c, y)] - MED[y]
    SEN, SEN_R3, SEN_NO24, RHO = {}, {}, {}, {}
    xs = [float(y) for y in YEARS]
    for c in P5:
        SEN[c] = ols_slope(xs, [REL[(c, y)] for y in YEARS])
        SEN_R3[c] = ols_slope(xs[2:], [REL[(c, y)] for y in YEARS[2:]])
        SEN_NO24[c] = ols_slope(xs[:3] + xs[4:],
                                [REL[(c, YEARS[i])] for i in (0, 1, 2, 4)])
        RHO[c] = spearman(xs, [REL[(c, y)] for y in YEARS])
    mS = st.fmean([SEN[c] for c in P5])
    sS = st.pstdev([SEN[c] for c in P5]) or 1e-9
    ZSEN = {c: (SEN[c] - mS) / sS for c in P5}
    CLS = {c: ('明显上升' if ZSEN[c] >= 1 else
               '明显下降' if ZSEN[c] <= -1 else '平稳') for c in P5}

    RK_WQ = rkmap(P_wq, P5)
    RK_EQ = rkmap(P_eq, P5)
    RK_Z = rkmap({c: st.fmean([Z[(c, y)] for y in YEARS]) for c in P5}, P5)
    RK_ZR = rkmap({c: st.fmean([ZR[(c, y)] for y in YEARS]) for c in P5}, P5)
    RK_VAR = {v: rkmap(P_var[v], P5) for v in WT if v != 'wq'}
    RK_Y = {y: rkmap({c: P[(c, y)] for c in POOL_Y[y]}, POOL_Y[y]) for y in YEARS}
    RK_Y_EQ = {y: rkmap({c: PEQ[(c, y)] for c in POOL_Y[y]}, POOL_Y[y]) for y in YEARS}
    RK_P3 = rkmap({c: agg(c, P, [1, 1, 1, 0, 0]) for c in P3}, P3)

    return dict(S=S, Q=Q, pairs=pairs, unpaired=unpaired, gov=gov,
                POOL_Y=POOL_Y, UNP=UNP, P5=P5, P3=P3, HIST=HIST,
                WQ=WQ, EQ=EQ, QUOTA=QUOTA, NPAIR=NPAIR, HI=HI, LO=LO,
                P=P, PEQ=PEQ, Z=Z, ZR=ZR, MED=MED, REL=REL,
                P_wq=P_wq, P_eq=P_eq, P_var=P_var,
                SEN=SEN, SEN_R3=SEN_R3, SEN_NO24=SEN_NO24, RHO=RHO,
                ZSEN=ZSEN, CLS=CLS, agg=agg,
                RK_WQ=RK_WQ, RK_EQ=RK_EQ, RK_Z=RK_Z, RK_ZR=RK_ZR,
                RK_VAR=RK_VAR, RK_Y=RK_Y, RK_Y_EQ=RK_Y_EQ, RK_P3=RK_P3)
