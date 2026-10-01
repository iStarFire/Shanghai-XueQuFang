# -*- coding: utf-8 -*-
"""2.4 独立复算：单线视角 / 规模效应 / P 主表。

原则：**从原始分数线与计划表重建**，不 import 2.3 的 singleline_pt.py，
并用与 2.3 不同的实现方式（显式排序 + 名次表；Spearman 用独立实现）。

比对对象：
1. `单线视角-普陀区-2022-2026.csv` 全表逐值（均名、均分、名额合计）；
2. 规模效应 ρ（跨样本 2 个 + 同线内 5 个）；
3. `rank-标准化-普陀区-2022-2026.csv` 的 P/Z/ZR/旧均名（全表）；
4. 报告 A1/A9 表格里的数值与 CSV 一致性（抽样正则核对）；
5. 回源抽样：3 个 (校, 线, 年) 单元格回到原始 CSV 核对分数与名额。
"""
import csv, statistics as st, re

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{ROOT}/data/普陀区/学校"
D_A = f"{ROOT}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
QU = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']
ALL9 = QU + ['华东师范大学第二附属中学', '上海市上海中学', '复旦大学附属中学',
             '上海交通大学附属中学', '上海师范大学附属中学']


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


raw = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')

# ---- 独立重建：逐校逐年逐线 (分数, 名额) ----
cell = {}
for r in raw:
    if r['min_score'] not in ('', None):
        cell[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = {
            'score': float(r['min_score']), 'doc': r['source_doc'], 'page': r['source_page']}
quota = {}
for r in plan:
    quota[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = int(r['quota'])

schools = sorted({k[0] for k in cell} | {k[0] for k in quota})

# ---- 逐年逐线名次（独立实现：排序后按位次取平均名次）----
lrank = {}
for hs in ALL9:
    for y in YEARS:
        items = sorted([(v['score'], k[0]) for k, v in cell.items()
                        if k[1] == hs and k[2] == y], key=lambda t: -t[0])
        i = 0
        while i < len(items):
            j = i
            while j + 1 < len(items) and items[j + 1][0] == items[i][0]:
                j += 1
            rk = ((i + 1) + (j + 1)) / 2          # 并列取平均名次
            for _, c in items[i:j + 1]:
                lrank[(c, hs, y)] = rk
            i = j + 1

# ---- 1) 单线视角 CSV 逐值比对 ----
deliv = load(f'{D_A}/单线视角-普陀区-2022-2026.csv')
bad = cmp_n = 0
for r in deliv:
    c, hs = r['junior_high_school'], r['senior_high_school']
    rk = [lrank[(c, hs, y)] for y in YEARS if (c, hs, y) in lrank]
    sc = [cell[(c, hs, y)]['score'] for y in YEARS if (c, hs, y) in cell]
    qs = [quota.get((c, hs, y), 0) for y in YEARS if (c, hs, y) in cell]
    for label, mine, got in [('n', len(rk), int(r['n_years'])),
                             ('均名', st.fmean(rk) if rk else None, F(r['avg_rank_line'])),
                             ('均分', st.fmean(sc) if sc else None, F(r['avg_score_line'])),
                             ('名额', sum(qs) if qs else None, F(r['quota_line_total']))]:
        cmp_n += 1
        if mine is None and got is None:
            continue
        if mine is None or got is None or abs(mine - got) > 5e-3:
            bad += 1
            print(f"  MISMATCH {c} / {hs} / {label}: 交付={got} 独立={mine}")
print(f"[1] 单线视角 CSV: {cmp_n} 项比对，超容差 {bad} 项（容差 5e-3，含 4 位小数舍入）")


# ---- 2) 规模效应 ρ（独立实现）----
def spearman(x, y):
    def rank(a):
        idx = sorted(range(len(a)), key=lambda i: a[i])
        out = [0.0] * len(a)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and a[idx[j + 1]] == a[idx[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in idx[i:j + 1]:
                out[k] = avg
            i = j + 1
        return out
    rx, ry = rank(x), rank(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


wide = load(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv')
rcsv = load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')
core = [r for r in wide if r['years_included'] == '5']
Pv = {r['junior_high_school']: F(r['P']) for r in rcsv}
q_arr = [F(r['quota4_avg']) for r in core]
avg_arr = [F(r['mean_rank_base4_avg']) for r in core]
p_arr = [Pv[r['junior_high_school']] for r in core]
rho_cross = spearman(q_arr, avg_arr)
rho_p = spearman(q_arr, p_arr)
print(f"[2] 跨样本 ρ(名额,均名) = {rho_cross:+.3f}（报告 −0.546）｜ρ(名额,P) = {rho_p:+.3f}（报告 +0.553）")

A, B = [], []
for hs in QU:
    a_, b_ = [], []
    for k, rk in lrank.items():
        if k[1] != hs:
            continue
        q = quota.get(k, 0)
        if q > 0:
            a_.append(q)
            b_.append(rk)
    A += a_
    B += b_
rho_within = spearman(A, B)
print(f"[3] 同线内 ρ = {rho_within:+.3f}（报告 −0.170，n={len(A)}）")

# ---- 3) P/Z/ZR/旧均名 全表复算 ----
per = {y: {} for y in YEARS}
for c in schools:
    for y in YEARS:
        vs = [cell[(c, h, y)]['score'] for h in QU if (c, h, y) in cell]
        if vs:
            per[y][c] = st.fmean(vs)
stat = {}
for y in YEARS:
    xs = sorted(per[y].values())
    n = len(xs)
    stat[y] = (st.fmean(xs), st.pstdev(xs), st.median(xs),
               xs[n * 3 // 4] - xs[n // 4])
R = {}
for y in YEARS:
    sv = per[y]
    for c, v in sv.items():
        better = sum(1 for w in sv.values() if w > v)
        eq = sum(1 for w in sv.values() if w == v)
        R[(c, y)] = better + (eq + 1) / 2
recomp = {}
for c in schools:
    ps, zs, zrs, rks = [], [], [], []
    for y in YEARS:
        if c not in per[y]:          # per 是按年的双层字典，勿写成 (c, y) not in per
            continue
        mu, sg, med, iqr = stat[y]
        x = per[y][c]
        r = R[(c, y)]
        zs.append((x - mu) / sg)
        zrs.append((x - med) / (iqr / 1.349))
        ps.append(1 - (r - 1) / (len(per[y]) - 1))
        rks.append(r)
    if ps:
        recomp[c] = (st.fmean(ps), st.fmean(zs), st.fmean(zrs), st.fmean(rks))

bad2 = cmp2 = 0
for r in rcsv:
    c = r['junior_high_school']
    if c not in recomp:
        continue
    P, Z, ZR, AVG = recomp[c]
    for label, mine, got in [('P', P, F(r['P'])), ('Z', Z, F(r['Z'])),
                             ('ZR', ZR, F(r['ZR'])), ('均名', AVG, F(r['old_mean_rank']))]:
        cmp2 += 1
        if mine is None or got is None or abs(mine - got) > 5e-3:
            bad2 += 1
            print(f"  MISMATCH {c} {label}: 交付={got} 独立={mine:.5f}")
print(f"[4] P/Z/ZR/均名 全表: {cmp2} 项比对，超容差 {bad2} 项")

# ---- 4) 报告表格数值抽样核对 ----
rep = open(f'{D_A}/分析报告.md', encoding='utf-8').read()
chk = 0
chk_bad = 0
for r in rcsv:
    if not r['rank_P']:                 # 未入榜（n<4）的行 rank_P 为空
        continue
    nm = r['junior_high_school']
    if int(r['rank_P']) > 6 and int(r['rank_P']) < 30:
        continue
    row_re = re.compile(r'\|\s*' + str(r['rank_P']) + r'\s*\|\s*' + re.escape(nm) + r'[^|]*\|\s*'
                        + re.escape(f"{F(r['P']):.3f}"))
    chk += 1
    if not row_re.search(rep):
        chk_bad += 1
        print(f"  REPORT-A1 未匹配 P 第 {r['rank_P']} {nm}")
print(f"[5] 报告 A1 表抽样核对: {chk} 行，未匹配 {chk_bad}")

# ---- 5) 回源抽样 ----
print('[6] 回源抽样（原始 CSV 的分数与名额）:')
for key in [('上海市梅陇中学', '上海市宜川中学', 2026),
            ('上海市江宁学校', '上海市曹杨第二中学', 2023),
            ('华东师范大学第四附属中学', '华东师范大学第二附属中学（普陀校区）', 2022)]:
    c = cell.get(key)
    q = quota.get(key)
    print(f"  {key[0]} × {key[1]} × {key[2]}: 分数={c['score'] if c else None} "
          f"名额={q} 来源={c['doc'] if c else '-'} 第{c['page'] if c else '-'}页")

print('\n结论:', '全部通过' if bad == 0 and bad2 == 0 and chk_bad == 0 else '存在超容差项，需排查')
