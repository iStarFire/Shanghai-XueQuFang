# -*- coding: utf-8 -*-
"""普陀区「单线视角」与规模效应检验（2.3 计算）。

回答三个问题：
1. 只看某一条高中线（尤其曹杨二中）的排名是什么；
2. 名额规模是否系统性地压低/抬高本指标的位次（跨样本 + 同线内两种检验）；
3. 梅陇中学（公认最好）为何在 base4 均名口径下只排第 8。

口径与 build_wide_pt.py 完全一致：
- 排名池 = 当年有该线数据的**全部**学校（含民办，与 base4 口径相同）；
- 逐年名次 = 平均名次法（分高者名次小）；
- 单线指标 = 某校在该线上的逐年名次，取有数据年份的均值（n≥4 才列出）。

输出：单线视角-普陀区-2022-2026.csv（长表）+ 控制台逐节结果。
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
QU = {'华东师范大学第二附属中学（普陀校区）': '华二普陀',
      '上海市曹杨第二中学': '曹杨二中',
      '上海市晋元高级中学': '晋元',
      '上海市宜川中学': '宜川'}
ALL9 = list(QU) + ['华东师范大学第二附属中学', '上海市上海中学', '复旦大学附属中学',
                   '上海交通大学附属中学', '上海师范大学附属中学']


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def fnum(v):
    return float(v) if v not in ('', None) else None


score = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')

S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): fnum(r['min_score'])
     for r in score}
Q = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): int(r['quota'])
     for r in plan}
schools = sorted({r['junior_high_school'] for r in score} | {r['junior_high_school'] for r in plan})


def avg_rank(v, vals):
    """平均名次法：分高者名次小；并列取平均。"""
    better = sum(1 for w in vals if w > v)
    eq = sum(1 for w in vals if w == v)
    return better + (eq + 1) / 2


def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((p - mx) * (q - my) for p, q in zip(rx, ry))
    den = (sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5
    return num / den if den else None


# ---- 1) 单线逐年名次 ----
# line_rank[(school, senior_high, year)] = 名次；line_pool[year][senior_high] = n
line_rank = {}
line_pool = {}
for hs in ALL9:
    for y in YEARS:
        vals = {c: S[(c, hs, y)] for c in schools if (c, hs, y) in S and S[(c, hs, y)] is not None}
        line_pool[(y, hs)] = len(vals)
        for c, v in vals.items():
            line_rank[(c, hs, y)] = avg_rank(v, list(vals.values()))

# 单线汇总（长表）
rows_out = []
for c in schools:
    for hs in ALL9:
        rk = [line_rank[(c, hs, y)] for y in YEARS if (c, hs, y) in line_rank]
        sc = [S[(c, hs, y)] for y in YEARS if (c, hs, y) in S and S[(c, hs, y)] is not None]
        qs = [Q.get((c, hs, y), 0) for y in YEARS if (c, hs, y) in S and S[(c, hs, y)] is not None]
        rows_out.append({
            'junior_high_school': c,
            'senior_high_school': hs,
            'n_years': len(rk),
            'avg_rank_line': round(st.fmean(rk), 4) if rk else '',
            'avg_score_line': round(st.fmean(sc), 3) if sc else '',
            'quota_line_total': sum(qs) if qs else '',
        })
with open(f'{D_A}/单线视角-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['junior_high_school', 'senior_high_school', 'n_years',
                                      'avg_rank_line', 'avg_score_line', 'quota_line_total'])
    w.writeheader()
    for r in sorted(rows_out, key=lambda r: (r['junior_high_school'],
                                             ALL9.index(r['senior_high_school']))):
        w.writerow(r)

# ---- 2) 四条区属线各自前 8 ----
print('== 四条区属线：5 年均名前 8（单线口径）==')
for hs, sh in QU.items():
    lst = [(r['junior_high_school'], fnum(r['avg_rank_line']), r['n_years'], fnum(r['avg_score_line']))
           for r in rows_out if r['senior_high_school'] == hs and r['n_years'] >= 4]
    print(f'-- {sh}（当年池 n={[line_pool[(y, hs)] for y in YEARS]}）')
    for i, (nm, a, n, sc) in enumerate(sorted(lst, key=lambda t: t[1])[:8], 1):
        print(f'   {i:>2} {nm:<26} 均名={a:.2f} 均分={sc:.1f} ({n}年)')

# ---- 3) 只看曹杨二中线的完整排名 ----
CZ = '上海市曹杨第二中学'
lst = [(r['junior_high_school'], fnum(r['avg_rank_line']), r['n_years'], fnum(r['avg_score_line']))
       for r in rows_out if r['senior_high_school'] == CZ and r['n_years'] >= 4]
print(f'\n== 只看曹杨二中线的完整排名（n≥4 年，共 {len(lst)} 所）==')
for i, (nm, a, n, sc) in enumerate(sorted(lst, key=lambda t: t[1]), 1):
    print(f'  {i:>2} {nm:<26} 曹二线均名={a:.2f} 均分={sc:.1f} ({n}年)')

# ---- 4) 单线口径的噪声：同校四条线名次的最大落差 ----
print('\n== 单线口径的内在噪声：同校四条区属线名次的最大落差（前 6 大）==')
spread = []
for c in schools:
    rk = [line_rank[(c, hs, y)] for hs in QU for y in YEARS if (c, hs, y) in line_rank]
    if len(rk) < 12:
        continue
    per_line = [st.fmean([line_rank[(c, hs, y)] for y in YEARS if (c, hs, y) in line_rank])
                for hs in QU if any((c, hs, y) in line_rank for y in YEARS)]
    spread.append((c, max(per_line) - min(per_line), per_line))
for nm, sp, per in sorted(spread, key=lambda t: -t[1])[:6]:
    print(f'  {nm:<26} 落差={sp:>5.1f}  ' + ' '.join(f'{QU[hs]}={v:.1f}' for hs, v in zip(QU, per)))

# ---- 5) 规模效应：跨样本 与 同线内 ----
wide = load(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv')
rank_csv = load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')
core = [r for r in wide if r['years_included'] == '5']
Pv = {r['junior_high_school']: fnum(r['P']) for r in rank_csv}
qs = [fnum(r['quota4_avg']) for r in core]
avg = [fnum(r['mean_rank_base4_avg']) for r in core]
pv = [Pv[r['junior_high_school']] for r in core]
print('\n== 规模效应检验 ==')
print(f'  跨样本 n={len(core)}: Spearman(区属年均名额, 均名) = {spearman(qs, avg):+.3f}'
      f'   Spearman(区属年均名额, P) = {spearman(qs, pv):+.3f}')
A, B = [], []
for hs, sh in QU.items():
    a_, b_ = [], []
    for y in YEARS:
        for c in schools:
            if (c, hs, y) not in line_rank:
                continue
            q = Q.get((c, hs, y), 0)
            if q <= 0:
                continue
            a_.append(q)
            b_.append(line_rank[(c, hs, y)])
    print(f'  同线内 {sh:<5} n={len(a_):>3}: ρ(该校该线名额, 该线名次) = {spearman(a_, b_):+.3f}')
    A += a_
    B += b_
print(f'  同线内 合并 n={len(A):>3}: ρ = {spearman(A, B):+.3f}')

# ---- 6) 梅陇 / 江宁 / 晋元附校 逐线对照 ----
print('\n== 逐线对照：均分 / 均名 / 该线 5 年名额 ==')
for nm in ['上海市梅陇中学', '上海市江宁学校', '上海市晋元高级中学附属学校']:
    print(f'-- {nm}')
    for hs, sh in QU.items():
        r = [x for x in rows_out if x['junior_high_school'] == nm and x['senior_high_school'] == hs][0]
        if r['n_years']:
            print(f"   {sh:<6} 均分={fnum(r['avg_score_line']):>6.1f} 均名={fnum(r['avg_rank_line']):>5.2f} "
                  f"5年名额={r['quota_line_total']:>3}（均 {r['quota_line_total'] / 5:.1f}/年）")
w_m = [x for x in core if x['junior_high_school'] == '上海市梅陇中学'][0]
print(f"   梅陇区属年均名额={fnum(w_m['quota4_avg'])} 均名={fnum(w_m['mean_rank_base4_avg'])} "
      f"中位={fnum(w_m['mean_rank_base4_median'])} 全口径均名={fnum(w_m['mean_rank_all_avg'])}")

# ---- 7) A1 P 主表（31 所五年全勤，按 P 降序）----
print('\n== A1 主表（P 主口径）==')
w_by = {r['junior_high_school']: r for r in wide}
ranked = sorted([r for r in rank_csv if r['ranked'] == '1'], key=lambda r: int(r['rank_P']))
for r in ranked:
    w = w_by[r['junior_high_school']]
    print(f"| {r['rank_P']} | {r['junior_high_school']} | {fnum(r['P']):.3f} | "
          f"{fnum(r['Z']):+.2f} | {fnum(r['ZR']):+.2f} | {fnum(r['old_mean_rank']):.2f} | "
          f"{fnum(w['mean_rank_base4_median']):.1f} | {fnum(w['quota4_avg']):.1f} |")
