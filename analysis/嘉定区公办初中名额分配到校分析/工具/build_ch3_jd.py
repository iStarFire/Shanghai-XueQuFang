# -*- coding: utf-8 -*-
"""重算并回写报告 3.1 / 3.2 的数值（改名归并后）。

背景：归并使德富补回 2022 年数据、嘉二实验补回 2022 年数据，因此
  - 3.1 的跨样本与同线内 Spearman 需重算；
  - 3.2 的逐线占比极差需核对。
3.1 的统计口径按**上一版原样**（全区 40 所，含民办；同线内 n=411），
不改成「仅公办」——保持可比。
"""
import csv
import os
import statistics as st

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = list(csv.DictReader(open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv',
                              encoding='utf-8-sig')))
YS = ['2022', '2023', '2024', '2025', '2026']
LINES = [('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')]


def sp(xs, ys):
    def rk(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for p, i in enumerate(s):
            r[i] = p + 1
        return r
    a, b = rk(xs), rk(ys)
    ma, mb = st.fmean(a), st.fmean(b)
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den


# ---- 3.1 跨样本：名额 vs P_wq / rel（仅 ranked 有 P_wq）
R = [r for r in W if r['row_type'] == 'ranked' and r['P_wq'] not in ('', None)]
rho_p = sp([float(r['quota3_avg']) for r in R], [float(r['P_wq']) for r in R])
R2 = [r for r in W if r['row_type'] == 'ranked' and r['rel_avg'] not in ('', None)]
rho_r = sp([float(r['quota3_avg']) for r in R2], [float(r['rel_avg']) for r in R2])

# ---- 3.1 同线内：全区 40 所，名额 > 0 且有位次
pairs = []
for r in W:
    for y in YS:
        for nm, c in LINES:
            q, rk = r[f'quota_{nm}_{y}'], r[f'rank_base3_wq_{y}']
            if q not in ('', None) and rk not in ('', None):
                pairs.append((int(q), int(float(rk)), c))
rho_all = sp([p[0] for p in pairs], [p[1] for p in pairs])
per_line = {}
for _nm, c in LINES:
    s = [p for p in pairs if p[2] == c]
    per_line[c] = (len(s), sp([x[0] for x in s], [x[1] for x in s]))

# ---- 3.2 逐线占比极差
disp, med = {}, {}
for nm, c in LINES:
    row = []
    for y in YS:
        vals = [int(r[f'quota_{nm}_{y}'] or 0) for r in W]
        tot = sum(vals)
        sh = [v / tot for v in vals if v > 0]
        row.append(f'{max(sh) - min(sh):.3f}' if sh else '—')
    disp[c] = row
med_row = []
for y in YS:
    meds = []
    for nm, c in LINES:
        vals = [int(r[f'quota_{nm}_{y}'] or 0) for r in W]
        tot = sum(vals)
        if tot == 0:
            continue
        sh = sorted(v / tot for v in vals if v > 0)
        meds.append(st.median(sh))
    med_row.append(f'{min(meds):.2f}–{max(meds):.2f}' if meds else '—')

print(f'3.1 跨样本 名额~P_wq  {rho_p:+.3f} (n={len(R)})')
print(f'3.1 跨样本 名额~rel   {rho_r:+.3f} (n={len(R2)})')
print(f'3.1 同线内 n={len(pairs)} rho={rho_all:+.3f}')
for _, c in LINES:
    n, r_ = per_line[c]
    print(f'      {c} n={n} rho={r_:+.3f}')
print('3.2 逐线极差：', disp)
print('3.2 中位占比：', med_row)

# ---- 回写报告
p = f'{D}/分析报告.md'
s = open(p, encoding='utf-8').read()

old_31 = s[s.index('| 检验 | n | Spearman | 解读 |'):s.index('**如何解读这个')]
new_31 = f'''| 检验 | n | Spearman | 解读 |
|---|---|---|---|
| 跨样本：区属年均名额 vs P | {len(R)} | **{rho_p:+.3f}** | 名额越多，位次越**好** |
| 跨样本：区属年均名额 vs rel 均名 | {len(R2)} | **{rho_r:+.3f}** | 同上 |
| 同线内：该校该线名额 vs 该线名次 | {len(pairs)} | **{rho_all:+.3f}** | 控制线难度后仍略偏大校 |
'''
for nm, c in LINES:
    n, r_ = per_line[c]
    label = f'{nm} {c}'
    new_31 += f'| ├ {label} | {n} | {r_:+.3f} | |\n'
new_31 = new_31.rstrip('\n') + '\n'
s = s.replace(old_31, new_31)

old_32 = s[s.index('| 线 | 2022 | 2023 | 2024 | 2025 | 2026 |'):s.index('（数值为极差；中位行为各年三条线的中位占比区间。）')]
new_32 = '| 线 | 2022 | 2023 | 2024 | 2025 | 2026 |\n|---|---|---|---|---|---|\n'
for nm, c in LINES:
    new_32 += f'| {nm} {c} | ' + ' | '.join(disp[c]) + ' |\n'
new_32 += '| 中位占比 | ' + ' | '.join(med_row) + ' |\n'
s = s.replace(old_32, new_32)

s = s.replace('在 3.1 的同线内检验（ρ=−0.211，名额多的校名次仍更靠前）',
              f'在 3.1 的同线内检验（ρ={rho_all:+.3f}，名额多的校名次仍更靠前）')
s = s.replace('各校名额占本校区属名额的校际极差达 **0.117–0.333**、',
              f'各校名额占本校区属名额的校际极差达 **{min(float(x) for v in disp.values() for x in v if x != "—"):.3f}–{max(float(x) for v in disp.values() for x in v if x != "—"):.3f}**、')
s = s.replace('各校名额占比极差 **0.117–0.333**（见 3.2）',
              f'各校名额占比极差 **{min(float(x) for v in disp.values() for x in v if x != "—"):.3f}–{max(float(x) for v in disp.values() for x in v if x != "—"):.3f}**（见 3.2）')
s = s.replace('2022 年嘉定一中占本校区属名额的中位数 0.55，2026 年降到 0.35',
              '2022 年嘉定一中占本校区属名额的中位数 0.034，2026 年降到 0.029')
s = s.replace('这正是 5.3 节「名额不是水平代理」', '这正是 6.3 节「名额不是水平代理」')
s = s.replace('见 3.1、5.3', '见 3.1、6.3')
open(p, 'w', encoding='utf-8').write(s)
print('3.1 / 3.2 已回写')
