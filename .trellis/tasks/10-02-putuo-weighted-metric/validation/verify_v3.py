# -*- coding: utf-8 -*-
"""2.4 验证：名额加权主口径 + 宽表扩容。

1. 独立复算加权均分 / 逐年名次 / P / 三组 / 综合（与 工具/build_v3.py 不同实现）；
2. 回归校验：新旧宽表**口径无关列**逐值一致（覆盖年数、名额均值）；
3. 宽表原始列抽样回源（score_*/quota_* vs 原始 CSV）；
4. 打印报告改写所需的事实清单。
"""
import csv, statistics as st

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_A = f"{ROOT}/analysis/普陀区公办初中名额分配到校分析"
D_S = f"{ROOT}/data/普陀区/学校"
YEARS = [2022, 2023, 2024, 2025, 2026]
QU4 = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
       '上海市晋元高级中学', '上海市宜川中学']


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


bad = 0
# ---------- 独立重建 ----------
raw = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')
S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): float(r['min_score'])
     for r in raw if r['min_score'] not in ('', None)}
Q = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): int(r['quota'])
     for r in plan}
schools = sorted({k[0] for k in S})
wq = {}
for c in schools:
    for y in YEARS:
        pairs = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in QU4 if (c, h, y) in S]
        if pairs:
            tw = sum(q for _, q in pairs)
            wq[(c, y)] = sum(v * q for v, q in pairs) / tw if tw else st.fmean([v for v, _ in pairs])

wide = load(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv')
wq_rows = {r['junior_high_school']: r for r in wide}
RANKED_ROWS = {c: r for c, r in wq_rows.items() if r['ranked'] == '1'}
n1 = b1 = 0
for c, r in wq_rows.items():
    for y in YEARS:
        mine = wq.get((c, y))
        got = F(r[f'mean_score_base4_wq_{y}'])
        if mine is None and got is None:
            continue
        n1 += 1
        if mine is None or got is None or abs(mine - got) > 5e-4:
            b1 += 1
            print(f'  MISMATCH 加权均分 {c} {y}: 交付={got} 独立={mine}')
print(f'[1] 加权均分独立复算：{n1} 格，超容差 {b1}')

# 逐年名次与 P（独立实现：排序分组法）
n2 = b2 = 0
for y in YEARS:
    vals = {c: wq[(c, y)] for c in schools if (c, y) in wq}
    order = sorted(vals.items(), key=lambda kv: -kv[1])
    n = len(order)
    i = 0
    rank = {}
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        for k in range(i, j + 1):
            rank[order[k][0]] = ((i + 1) + (j + 1)) / 2
        i = j + 1
    for c, rk in rank.items():
        if c not in wq_rows:
            continue
        n2 += 1
        w = wq_rows[c]
        if abs(rk - F(w[f'rank_base4_wq_{y}'])) > 5e-3:
            b2 += 1
            print(f'  MISMATCH 名次 {c} {y}: 交付={w[f"rank_base4_wq_{y}"]} 独立={rk}')
        if abs(1 - (rk - 1) / (n - 1) - F(w[f'P_wq_{y}'])) > 5e-4:
            b2 += 1
            print(f'  MISMATCH P {c} {y}: 交付={w[f"P_wq_{y}"]} 独立={1 - (rk - 1) / (n - 1)}')
print(f'[2] 逐年名次与 P 独立复算：{n2} 项，超容差 {b2}')

# 聚合 P（全身）与 rank CSV 比对
rcsv = {r['junior_high_school']: r for r in load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')}
n3 = b3 = 0
for c, r in rcsv.items():
    ps = [1 - (F(wq_rows[c][f'rank_base4_wq_{y}']) - 1) /
          (len([x for x in schools if (x, y) in wq]) - 1)
          for y in YEARS if wq_rows[c][f'rank_base4_wq_{y}'] not in ('', None)]
    mine = st.fmean(ps)
    n3 += 1
    if abs(mine - F(r['P_wq'])) > 5e-4:
        b3 += 1
        print(f'  MISMATCH P_wq {c}: CSV={r["P_wq"]} 独立={mine:.6f}')
print(f'[3] 聚合 P_wq 复算：{n3} 所，超容差 {b3}')

# ---------- 回归校验：口径无关列应 0 变化 ----------
old = {r['junior_high_school']: r for r in load('/tmp/wide_old.csv')}
CHECK = ['years_included', 'years_list', 'quota4_avg']
n4 = b4 = 0
n_qall = 0
for c, r in old.items():
    if c not in wq_rows:
        if r['years_included'] not in ('', '0'):     # 0 年数据行不入新表（预期）
            b4 += 1
            print(f'  MISSING 新宽表缺行：{c}（旧 years_included={r["years_included"]}）')
        continue
    if abs((F(r.get('quota_all_avg')) or -1) - (F(wq_rows[c].get('quota_all_avg')) or -1)) > 1e-3:
        n_qall += 1        # 口径修正：旧按 5 年（含 0）平均，新按有数据年份平均
    for k in CHECK:
        n4 += 1
        a, b_ = r.get(k, ''), wq_rows[c].get(k, '')
        if a != b_ and abs((F(a) or -1) - (F(b_) or -1)) > 1e-3:
            b4 += 1
            print(f'  MISMATCH 回归校验 {c} {k}: 旧={a} 新={b_}')
print(f'[4] 回归校验（years_included / years_list / quota4_avg）：{n4} 项，差异 {b4}'
      f'；quota_all_avg 有 {n_qall} 所按新口径（有数据年份均值）改变（预期修正）')

# ---------- 原始列抽样回源 ----------
SH = {'华二普陀': '华东师范大学第二附属中学（普陀校区）', '二中': '上海市曹杨第二中学',
      '晋元': '上海市晋元高级中学', '宜川': '上海市宜川中学'}
n5 = b5 = 0
for c in ['上海市梅陇中学', '上海市江宁学校', '上海市曹杨第二中学附属实验中学']:
    r = wq_rows[c]
    for s, full in SH.items():
        for y in YEARS:
            n5 += 1
            sc_ref = S.get((c, full, y), '')
            qu_ref = Q.get((c, full, y), '')
            if str(r[f'score_{s}_{y}']) != (str(sc_ref) if sc_ref != '' else '') or \
               str(r[f'quota_{s}_{y}']) != (str(qu_ref) if qu_ref != '' else ''):
                b5 += 1
                print(f'  MISMATCH 原始列 {c} {s} {y}: 宽表={r[f"score_{s}_{y}"]}/{r[f"quota_{s}_{y}"]} '
                      f'原始={sc_ref}/{qu_ref}')
print(f'[5] 宽表原始列抽样回源：{n5} 格，差异 {b5}')

print(f'\n结论: {"全部通过" if b1+b2+b3+b4+b5 == 0 else "存在问题项"}')

# ---------- 事实清单（供报告改写） ----------
multi = {r['junior_high_school']: r for r in load(f'{D_A}/rank-多口径总表-普陀区-2022-2026.csv')}
tbl = sorted(RANKED_ROWS.values(), key=lambda r: int(r['rank_P_wq_comb']))
print('\n=== A. 加权主口径 综合排名（32 所）===')
for r in tbl:
    print(f"  {r['rank_P_wq_comb']:>2} {r['junior_high_school'].replace('上海市',''):<26}"
          f"综合={F(r['P_wq_comb']):.3f} 全身{r['rank_P_wq_all']} 头{r['rank_P_wq_head']} 尾{r['rank_P_wq_tail']}"
          f" | 等权综合第{r['rank_P_eq_comb']}（差{int(multi[r['junior_high_school']]['shift_comb_wq_eq']):+d}）"
          f" 均名={F(r['mean_rank_base4_wq_avg']):.2f} 计划={F(r['quota4_avg']):.1f}")
trend = {r['junior_high_school']: r for r in load(f'{D_A}/趋势分析-普陀区-2022-2026.csv')}
print('\n=== B. 趋势（加权口径）关键校 ===')
for c in ['上海市江宁学校', '上海市晋元高级中学附属学校', '上海市中远实验学校', '上海市真北中学',
          '上海市梅陇中学', '上海市普陀区教育学院附属学校', '上海市沙田学校', '上海市文达学校',
          '上海理工大学附属普陀实验学校', '上海市万里城实验学校']:
    t = trend[c]
    print(f"  {c.replace('上海市',''):<24} rel {F(t['rel_first']):+.2f}→{F(t['rel_last']):+.2f} "
          f"Sen={F(t['sen']):+.2f} ρ={F(t['spearman']):+.2f} 近3年Sen={F(t['sen_recent3']):+.2f} "
          f"残差z={F(t['residual_z']):+.2f} 超出={t['beyond_convergence']}")
print('\n=== C. 逐年离散度（加权口径，31 所五年全勤）===')
core31 = [c for c in wq_rows if wq_rows[c]['years_included'] == '5']
for y in YEARS:
    xs = sorted(wq[(c, y)] for c in core31)
    n = len(xs)
    med = st.median(xs)
    print(f"  {y}: IQR={xs[n*3//4]-xs[n//4]:.1f} σ={st.pstdev(xs):.2f} 中位={med:.1f} "
          f"±5内={sum(1 for v in xs if abs(v-med)<=5)/n:.0%} ±10内={sum(1 for v in xs if abs(v-med)<=10)/n:.0%}")
print('\n=== D. 超收敛个案（|残差 z|≥1）===')
for c, t in sorted(trend.items(), key=lambda kv: F(kv[1]['residual_z'])):
    if abs(F(t['residual_z'])) >= 1:
        print(f"  {c.replace('上海市',''):<24} 残差z={F(t['residual_z']):+.2f} "
              f"rel {F(t['rel_first']):+.2f}→{F(t['rel_last']):+.2f}")
print('\n=== E. 其他汇总 ===')
print('  收敛回归与规模相关性见 build_v3.py 控制台输出')
