# -*- coding: utf-8 -*-
"""批次 1：同步核心结论 A 段、2.1 敏感性表、2.2 近三年排序表到新口径。"""
import csv
import os
import statistics as st

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


W = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
M = [r for r in csv.DictReader(
    open(f'{D}/rank-多口径总表-嘉定区-2022-2026.csv', encoding='utf-8-sig'))]
S = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/趋势分类-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
rows = sorted([r for r in M if r['row_type'] == 'ranked'],
              key=lambda r: int(r['rank_P_wq_all']))


def sp(a, b):
    def rk(x):
        s = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for p, i in enumerate(s):
            r[i] = p + 1
        return r
    ra, rb = rk(a), rk(b)
    ma, mb = st.fmean(ra), st.fmean(rb)
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / den


# ---------- 2.1 敏感性 ----------
base = [int(r['rank_P_wq_all']) for r in rows]
sens = []
for lab, k in [('等权 P（名次）', 'rank_P_eq_all'), ('Z（名次）', 'rank_Z_wq_comb'),
               ('ZR（名次）', 'rank_ZR_wq_comb'), ('时间权重 线性 1:5', 'rank_P_lin'),
               ('时间权重 指数 1:16', 'rank_P_exp'), ('时间权重 近 3 年', 'rank_P_recent3'),
               ('时间权重 近 2 年', 'rank_P_recent2')]:
    v = [int(r[k]) for r in rows]
    d = [abs(x - y) for x, y in zip(base, v)]
    sens.append(f'| {lab} | {sp(base, v):.3f} | {max(d)} 位 | {sum(1 for x in d if x >= 3)} 所 |')
SENS = '\n'.join(sens)

# 各口径前 5 是否与主口径一致
top5 = {r['junior_high_school'] for r in rows[:5]}
same = {}
for k in ('rank_P_eq_all', 'rank_Z_wq_comb', 'rank_ZR_wq_comb', 'rank_P_lin',
          'rank_P_exp', 'rank_P_recent3', 'rank_P_recent2'):
    same[k] = {r['junior_high_school'] for r in sorted(rows, key=lambda r: int(r[k]))[:5]} == top5
unchanged = [k for k, v in same.items() if v]
changed = [k for k, v in same.items() if not v]
LAB = {'rank_P_eq_all': '等权', 'rank_Z_wq_comb': 'Z', 'rank_ZR_wq_comb': 'ZR',
       'rank_P_lin': '线性', 'rank_P_exp': '指数', 'rank_P_recent3': '近 3 年',
       'rank_P_recent2': '近 2 年'}

# ---------- 2.2 近三年 ----------
L = ['| 近 3 年名次 | 初中 | P_recent3 | 主口径名次 | 位移 | 趋势分类 |',
     '|---|---|---|---|---|---|']
for r in sorted(rows, key=lambda r: int(r['rank_P_recent3'])):
    n = r['junior_high_school']
    d = int(r['rank_P_recent3']) - int(r['rank_P_wq_all'])
    L.append(f"| {r['rank_P_recent3']} | {sh(n)} | {float(r['rank_P_recent3']) and float(r['P_recent3']):.3f} "
             f"| {r['rank_P_wq_all']} | {d:+d} | {S[n]['trend_class']} |")
RECENT3 = '\n'.join(L)

# 近 2 年
L2 = ['| 近 2 年名次 | 初中 | P_recent2 | 主口径名次 | 位移 |', '|---|---|---|---|---|']
for r in sorted(rows, key=lambda r: int(r['rank_P_recent2'])):
    n = r['junior_high_school']
    d = int(r['rank_P_recent2']) - int(r['rank_P_wq_all'])
    L2.append(f"| {r['rank_P_recent2']} | {sh(n)} | {float(r['P_recent2']):.3f} "
              f"| {r['rank_P_wq_all']} | {d:+d} |")
RECENT2 = '\n'.join(L2)

# ---------- 核心结论 A ----------
t3 = [r['junior_high_school'] for r in rows[:6]]
A = f'''**A. 排名（名额加权主口径，入榜 28 所；排名池仅公办）**

1. **头部 6 校**：同济大学附属实验中学（{float(rows[0]['P_wq_all']):.3f}）、
   上海外国语大学嘉定外国语学校（{float(rows[1]['P_wq_all']):.3f}）、
   新城实验中学（{float(rows[2]['P_wq_all']):.3f}）、苏民学校（{float(rows[3]['P_wq_all']):.3f}）、
   交大附中附属嘉定德富中学（{float(rows[4]['P_wq_all']):.3f}）、
   中科院上海实验学校（{float(rows[5]['P_wq_all']):.3f}）。
   **头部极度密集**：第 1–2 名极差 **{float(rows[0]['P_wq_all']) - float(rows[1]['P_wq_all']):.3f}**、
   第 3–5 名极差 **{float(rows[4]['P_wq_all']) - float(rows[2]['P_wq_all']):.3f}**，
   引用时应给区间而非精确名次。
2. **⚠ 排名口径 2026-10-03 修正**：此前分位池**包含民办**，而民办多为强校
   （2026 年民办远东 P=1.000 即全区第 1），机械压低了所有公办校的分位与名次。
   现已改为**分位、位次、rel 中位、收敛基准全部只用当年有数据的公办学校**
   （2026 年池 39 → **32 所**）。民办不参与任何排名，其 `P_*`／`rank_*` 列已置空。
3. **口径一致性**：主口径 P 与等权 P Spearman **{sp(base, [int(r['rank_P_eq_all']) for r in rows]):.3f}**、
   与 Z **{sp(base, [int(r['rank_Z_wq_comb']) for r in rows]):.3f}**、
   与 ZR **{sp(base, [int(r['rank_ZR_wq_comb']) for r in rows]):.3f}**。
   **前 5 名不变**的口径只有 {len(unchanged)} 种（{'、'.join(LAB[k] for k in unchanged)}）；
   {'、'.join(LAB[k] for k in changed)} 四种口径下前 5 会变动。
4. **时间窗口越短，榜单越不稳定**：近 3 年口径 Spearman 0.926、最大位移 8 位；
   **近 2 年（2025–2026）Spearman 仅 0.843、最大位移 13 位、15 所变动 ≥3 位**——
   窗口越短越贴近当下，也越容易被个别年份的波动带偏。
'''

p = f'{D}/分析报告.md'
s = open(p, encoding='utf-8').read()

# 替换核心结论 A 段
i = s.index('**A. 排名')
j = s.index('**B. 结构与规模**')
s = s[:i] + A + '\n' + s[j:]

# 替换 2.1 敏感性表 + 其后结论
i = s.index('| 对照口径 | 与主口径 Spearman | 最大位移 | 变动 ≥3 位 |')
j = s.index('### 2.2 近三年')
new21 = f'''| 对照口径 | 与主口径 Spearman | 最大位移 | 变动 ≥3 位 |
|---|---|---|---|
{SENS}

> **⚠ 与上一版数值的差异（排名池口径变更）**：此前分位池含民办，Spearman 普遍更高
> （等权 0.988、Z 0.944、近 3 年 0.903）。剔除民办后公办校的位置更贴近，
> 各口径与主口径的一致性反而**下降**（等权 {sp(base, [int(r['rank_P_eq_all']) for r in rows]):.3f}、
> 近 3 年 {sp(base, [int(r['rank_P_recent3']) for r in rows]):.3f}），
> 近 2 年更降至 {sp(base, [int(r['rank_P_recent2']) for r in rows]):.3f}。
> **这不是「排名变差」，而是「剔除民办后公办内部的真实差异更清楚地显出来」。**

'''
s = s[:i] + new21 + s[j:]

# 替换 2.2 的排序表
i = s.index('| 近 3 年名次 | 初中 | P_recent3 |')
j = s.index('**读法**')
s = s[:i] + RECENT3 + '\n\n' + s[j:]

open(p, 'w', encoding='utf-8').write(s)
print('核心结论 A 段 / 2.1 / 2.2 已同步')
print(f'前 5 不变口径: {[LAB[k] for k in unchanged]}')
print(f'前 5 会变口径: {[LAB[k] for k in changed]}')
print(RECENT2[:200])
open('/tmp/recent2.md', 'w', encoding='utf-8').write(RECENT2)
