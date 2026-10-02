# -*- coding: utf-8 -*-
"""2.4 独立复算：多口径总表（三组结构口径 + 综合口径）。

独立点：
1. 逐年分位用**排序分组法**（先降序排、同分组取 (i+j)/2+1），而非 2.3 的逐值比较法；
2. 直接从**原始分数线 CSV** 重建三组均分（不读 2.3 的中间结果）；
3. 名次用「排序后枚举」独立生成。

比对：`rank-多口径总表-普陀区-2022-2026.csv` 全表（4 个 P + 4 个名次）、
`P_all` vs 既有主口径 `rank-标准化-普陀区-2022-2026.csv`、报告表 2-1/2-2 抽样。
"""
import csv, re

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{ROOT}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
GROUPS = {
    'all': ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
            '上海市晋元高级中学', '上海市宜川中学'],
    'head': ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学'],
    'tail': ['上海市晋元高级中学', '上海市宜川中学'],
}


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


def py_ranks(scores):
    """逐年分位（排序分组法）。"""
    order = sorted(scores.items(), key=lambda kv: -kv[1])
    n = len(order)
    out = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        rk = ((i + 1) + (j + 1)) / 2
        for k in range(i, j + 1):
            out[order[k][0]] = 1 - (rk - 1) / (n - 1)
        i = j + 1
    return out


import statistics as st

raw = load(f'{ROOT}/data/普陀区/学校/名额到校最低分数线-普陀区-2022-2026.csv')
S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): float(r['min_score'])
     for r in raw if r['min_score'] not in ('', None)}
schools = sorted({k[0] for k in S})

recomp = {}
for g, lines in GROUPS.items():
    per = {}
    for c in schools:
        for y in YEARS:
            vs = [S[(c, h, y)] for h in lines if (c, h, y) in S]
            if vs:
                per.setdefault(y, {})[c] = st.fmean(vs)
    Py = {y: py_ranks(v) for y, v in per.items()}
    for c in schools:
        v = [Py[y][c] for y in YEARS if c in Py[y]]
        if v:
            recomp[(c, g)] = st.fmean(v)

csvrows = load(f'{D}/rank-多口径总表-普陀区-2022-2026.csv')
bad = n = 0
for r in csvrows:
    c = r['junior_high_school']
    for g, col in [('all', 'P_all'), ('head', 'P_head'), ('tail', 'P_tail')]:
        n += 1
        if abs(recomp[(c, g)] - F(r[col])) > 5e-4:
            bad += 1
            print(f'  MISMATCH {c} {col}: 交付={r[col]} 独立={recomp[(c, g)]:.5f}')
    n += 1
    comb = (recomp[(c, 'all')] + recomp[(c, 'head')] + recomp[(c, 'tail')]) / 3
    if abs(comb - F(r['P_comb'])) > 5e-4:
        bad += 1
        print(f'  MISMATCH {c} P_comb: 交付={r["P_comb"]} 独立={comb:.5f}')
print(f'[1] 三组 P + 综合 P 复算：{n} 项，超容差 {bad} 项')

# 名次复算
for col, key in [('rank_P_comb', 'P_comb'), ('rank_P_all', 'P_all'),
                 ('rank_P_head', 'P_head'), ('rank_P_tail', 'P_tail')]:
    vals = {r['junior_high_school']: recomp[(r['junior_high_school'], key.split('_')[1])]
            if key != 'P_comb' else F(r['P_comb']) for r in csvrows}
    order = sorted(vals, key=lambda c: -vals[c])
    for i, c in enumerate(order, 1):
        got = [r for r in csvrows if r['junior_high_school'] == c][0][col]
        if int(got) != i:
            bad += 1
            print(f'  MISMATCH {c} {col}: 交付={got} 独立={i}')
print(f'[2] 名次复算完成（累计超容差 {bad}）')

# 完整性：P_all vs 既有主口径
rank_old = {r['junior_high_school']: r for r in load(f'{D}/rank-标准化-普陀区-2022-2026.csv')
            if r['ranked'] == '1'}
nb = 0
for c, r in rank_old.items():
    nb += 1
    if abs(recomp[(c, 'all')] - F(r['P'])) > 5e-4:
        bad += 1
        print(f'  MISMATCH(完整性) {c}: 独立 P_all={recomp[(c, "all")]:.5f} vs 主口径 CSV={r["P"]}')
print(f'[3] 完整性检查 P_all vs rank-标准化 CSV：{nb} 所（累计超容差 {bad}）')

# 报告表核对（全 32 所，两张表）
rep = open(f'{D}/分析报告.md', encoding='utf-8').read()
nb2 = 0
for r in csvrows:
    c = r['junior_high_school']
    checks = [
        f"| {r['rank_P_comb']} | {c} | {F(r['P_comb']):.3f} | {F(r['P_all']):.3f}（{r['rank_P_all']}）",
        f"| {c} | {F(r['P']):.3f}（{r['rank_P']}） | {F(r['Z']):+.2f}（{r['rank_Z']}）",
        (f"| {F(r['quota4_avg']):.1f} | {r['n_years']} 年 |"
         if r['n_years'] == '5' else
         f"| {F(r['quota4_avg']):.1f} | {r['n_years']} 年（精度低一年） |"),
    ]
    for s in checks:
        nb2 += 1
        if s.replace('-', '−') not in rep and s not in rep:
            bad += 1
            print(f'  REPORT 未匹配：{s[:60]}...')
print(f'[4] 报告表 2-1/2-2 全量核对：{nb2} 项（累计超容差 {bad}）')

print('\n结论:', '全部通过' if bad == 0 else f'存在 {bad} 项问题，需排查')
