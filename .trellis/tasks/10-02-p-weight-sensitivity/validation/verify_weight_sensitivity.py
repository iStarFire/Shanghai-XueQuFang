# -*- coding: utf-8 -*-
"""2.4 独立复算：主口径 P 的时间加权变体。

独立点：
1. 名次用**排序分组法**（先按分数降序排，同分组取 (i+j)/2+1），而非 2.3 的逐值比较法；
2. 加权聚合用 **(校,年) 矩阵 + 权重向量点积**，而非 2.3 的逐方案循环；
3. 普陀的逐年 P 从**原始分数线**重建；徐汇从**宽表逐年分数列**重建（不 import 任何 2.3 脚本）。

比对对象：
- 两区 `rank-加权敏感性-*.csv` 全表（P_eq/P_lin/P_exp/P_recent3 + 4 个名次 + 3 个 shift）；
- 两区 `rank-标准化-*.csv` 的 P（**完整性检查**：P_eq 必须与既有主口径一致）；
- 报告表格抽样正则核对。
"""
import csv, statistics as st, re

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
YEARS = [2022, 2023, 2024, 2025, 2026]
WEIGHTS = {'eq': [1, 1, 1, 1, 1], 'lin': [1, 2, 3, 4, 5],
           'exp': [1, 2, 4, 8, 16], 'recent3': [0, 0, 1, 1, 1]}


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


def py_ranks(scores):
    """逐年分位：排序分组法（独立于 2.3 的逐值比较法）。"""
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


# ---------- 普陀：从原始分数线重建 ----------
PT = f"{ROOT}/analysis/普陀区公办初中名额分配到校分析"
QU = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']
raw = load(f"{ROOT}/data/普陀区/学校/名额到校最低分数线-普陀区-2022-2026.csv")
S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): float(r['min_score'])
     for r in raw if r['min_score'] not in ('', None)}
pt_per = {}
for c in {k[0] for k in S}:
    for y in YEARS:
        vs = [S[(c, h, y)] for h in QU if (c, h, y) in S]
        if vs:
            pt_per.setdefault(y, {})[c] = st.fmean(vs)
pt_P = {y: py_ranks(v) for y, v in pt_per.items()}
Pmat_pt = {c: [pt_P[y].get(c) for y in YEARS] for c in {k[0] for k in S}}


def wagg2(Py, w):
    """(校,年) 向量 × 权重向量；缺年份跳过并按可用权重归一。"""
    wv = WEIGHTS[w]
    num = den = 0.0
    for p, i in zip(Py, wv):
        if p is None or i == 0:
            continue
        num += p * i
        den += i
    return num / den if den else None


# 用 Pmat 复算两区
def recompute(csv_rows, Pmat):
    got = {r['junior_high_school']: r for r in csv_rows}
    bad = n = 0
    vals = {}
    for c, row in got.items():
        if c not in Pmat:
            continue
        d = {}
        for w in WEIGHTS:
            m = wagg2(Pmat[c], w)
            d['P_' + w] = m
            for col, lab in [('P_eq', 'eq'), ('P_lin', 'lin'), ('P_exp', 'exp'),
                             ('P_recent3', 'recent3')]:
                if w == lab:
                    n += 1
                    if abs(m - F(row[col])) > 5e-3:
                        bad += 1
                        print(f'    MISMATCH {c} {col}: 交付={row[col]} 独立={m:.6f}')
        vals[c] = d
    # 名次与 shift
    for w in WEIGHTS:
        key = 'P_' + w
        order = sorted(vals, key=lambda c: -vals[c][key])
        for i, c in enumerate(order, 1):
            n += 1
            if int(got[c]['rank_' + w]) != i:
                bad += 1
                print(f'    MISMATCH {c} rank_{w}: 交付={got[c]["rank_" + w]} 独立={i}')
    for w in ['lin', 'exp', 'recent3']:
        for c in vals:
            n += 1
            exp = int(got[c]['rank_' + w]) - int(got[c]['rank_eq'])
            if int(got[c]['shift_' + w]) != exp:
                bad += 1
                print(f'    MISMATCH {c} shift_{w}: 交付={got[c]["shift_" + w]} 独立={exp}')
    return n, bad


pt_csv = load(f'{PT}/rank-加权敏感性-普陀区-2022-2026.csv')
n1, b1 = recompute(pt_csv, Pmat_pt)
print(f'[1] 普陀 加权 CSv 全表复算：{n1} 项，超容差 {b1} 项')

# 完整性：P_eq vs 既有 rank-标准化 CSV
pt_rank = {r['junior_high_school']: r for r in load(f'{PT}/rank-标准化-普陀区-2022-2026.csv')
           if r['ranked'] == '1'}
b2 = n2 = 0
for c, r in pt_rank.items():
    n2 += 1
    mine = wagg2(Pmat_pt[c], 'eq')
    if abs(mine - F(r['P'])) > 5e-4:
        b2 += 1
        print(f'    [完整性] {c}: 重建 {mine:.5f} vs 主口径 CSV {r["P"]}')
print(f'[2] 普陀 完整性检查（P_eq vs rank-标准化 CSV）：{n2} 所，不一致 {b2} 项')

# ---------- 徐汇：从宽表逐年分数列重建 ----------
XH = f"{ROOT}/analysis/徐汇区公办初中名额分配到校分析"
B5 = ['042001', '042008', '042035', '043015', '042036']
wide = load(f'{XH}/宽表-初中水平-徐汇区-2022-2026.csv')
xh_per = {}
for r in wide:
    for y in YEARS:
        vs = [F(r.get(f'score_{h}_{y}')) for h in B5]
        vs = [v for v in vs if v is not None]
        if vs:
            xh_per.setdefault(y, {})[r['junior_high_school']] = st.fmean(vs)
xh_P = {y: py_ranks(v) for y, v in xh_per.items()}
Pmat_xh = {c: [xh_P[y].get(c) for y in YEARS] for c in {r['junior_high_school'] for r in wide}}
xh_csv = load(f'{XH}/rank-加权敏感性-徐汇区-2022-2026.csv')
n3, b3 = recompute(xh_csv, Pmat_xh)
print(f'[3] 徐汇 加权 CSV 全表复算：{n3} 项，超容差 {b3} 项')

xh_rank = {r['junior_high_school']: r for r in load(f'{XH}/rank-标准化-徐汇区-2022-2026.csv')
           if r['ranked'] == '1'}
b4 = n4 = 0
for c, r in xh_rank.items():
    n4 += 1
    mine = wagg2(Pmat_xh[c], 'eq')
    if abs(mine - F(r['P'])) > 5e-4:
        b4 += 1
        print(f'    [完整性] {c}: 重建 {mine:.5f} vs 主口径 CSV {r["P"]}')
print(f'[4] 徐汇 完整性检查（P_eq vs rank-标准化 CSV）：{n4} 所，不一致 {b4} 项')

# ---------- 报告抽样 ----------
def check_report(path, csv_rows, key='P_lin'):
    rep = open(path, encoding='utf-8').read()
    bad = n = 0
    for r in csv_rows[:6] + csv_rows[-3:]:
        n += 1
        v = f"{F(r[key]):.3f}"
        if v not in rep:
            bad += 1
            print(f'    REPORT 未找到 {r["junior_high_school"]} 的 {key}={v}')
    return n, bad


n5, b5 = check_report(f'{PT}/分析报告.md', pt_csv)
n6, b6 = check_report(f'{XH}/分析报告.md', xh_csv)
print(f'[5] 报告 A1/A8.2 表抽样：普陀 {n5} 行、徐汇 {n6} 行，未匹配 {b5 + b6}')

tot_bad = b1 + b2 + b3 + b4 + b5 + b6
print('\n结论:', '全部通过' if tot_bad == 0 else f'存在 {tot_bad} 项超容差，需排查')
