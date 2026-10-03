# -*- coding: utf-8 -*-
"""批次 2：同步 2.3 新校披露、3.1/3.2/3.3 到新口径（仅公办池）。"""
import csv
import os
import statistics as st

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(D))
W = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
WALL = list(W.values())
YS = ['2022', '2023', '2024', '2025', '2026']


def sh(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


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


PUB = [r for r in WALL if r['ownership'] == '公办']
RK = [r for r in PUB if r['row_type'] == 'ranked']

# ---------- 2.3 新校披露 ----------
NEW = [r for r in WALL if r['row_type'] == 'new_school']
L = ['| 学校 | 办学性质 | 创办 | 有成绩年份 | 逐年名额加权均分（全区公办位次 / 区属名额） |',
     '|---|---|---|---|---|']
FOUNDED = {'交大附中附属嘉定洪德中学': '2021-09', '同济大学附属嘉定实验中学': '2021-09',
           '上海师范大学附属第五嘉定实验学校': '2021-09', '上海市嘉定区嘉一实验初级中学': '2022-08'}
for r in sorted(NEW, key=lambda r: -int(float(r['rank_base3_wq_2026']))):
    n = r['junior_high_school']
    cells = []
    for y in r['years_list'].split(';'):
        cells.append(f"{y}：{float(r[f'mean_score_base3_wq_{y}']):.1f}"
                     f"（第 {int(float(r[f'rank_base3_wq_{y}']))} 位 / {r[f'quota3_{y}']} 个）")
    L.append(f"| {sh(n)} | 公办 | {FOUNDED.get(n, '—')} | {r['years_list'].replace(';', '–')} "
             f"| {'；'.join(cells)} |")
NEW_DISCLOSE = '\n'.join(L)

# ---------- 3.1 ----------
rho_p = sp([float(r['quota3_avg']) for r in RK], [float(r['P_wq']) for r in RK])
rho_r = sp([float(r['quota3_avg']) for r in RK], [float(r['rel_avg']) for r in RK])
pairs = []
for r in PUB:
    for y in YS:
        for nm, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
            q, rk = r[f'quota_{nm}_{y}'], r[f'rank_base3_wq_{y}']
            if q not in ('', None) and rk not in ('', None):
                pairs.append((int(q), int(float(rk)), c))
rho_all = sp([x[0] for x in pairs], [x[1] for x in pairs])
per = {}
for _, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
    ss = [x for x in pairs if x[2] == c]
    per[c] = (len(ss), sp([x[0] for x in ss], [x[1] for x in ss]))
T31 = ['| 检验 | n | Spearman | 解读 |', '|---|---|---|---|',
       f'| 跨样本：区属年均名额 vs P | {len(RK)} | **{rho_p:+.3f}** | 名额越多，位次越**好** |',
       f'| 跨样本：区属年均名额 vs rel 均名 | {len(RK)} | **{rho_r:+.3f}** | 同上 |',
       f'| 同线内：该校该线名额 vs 该线名次 | {len(pairs)} | **{rho_all:+.3f}** | 控制线难度后仍略偏大校 |']
for nm, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
    n, r_ = per[c]
    T31.append(f'| ├ {nm} {c} | {n} | {r_:+.3f} | |')
T31 = '\n'.join(T31)

# ---------- 3.2 ----------
disp, med = {}, {}
for nm, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
    row = []
    for y in YS:
        vals = [int(r[f'quota_{nm}_{y}'] or 0) for r in PUB]
        tot = sum(vals)
        sh_ = [v / tot for v in vals if v > 0]
        row.append(f'{max(sh_) - min(sh_):.3f}' if sh_ else '—')
    disp[c] = row
med_row = []
for y in YS:
    meds = []
    for nm, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
        vals = [int(r[f'quota_{nm}_{y}'] or 0) for r in PUB]
        tot = sum(vals)
        if tot == 0:
            continue
        s = sorted(v / tot for v in vals if v > 0)
        meds.append(st.median(s))
    med_row.append(f'{min(meds):.3f}–{max(meds):.3f}' if meds else '—')
T32 = ['| 线 | 2022 | 2023 | 2024 | 2025 | 2026 |', '|---|---|---|---|---|---|']
for nm, c in (('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')):
    T32.append(f'| {nm} {c} | ' + ' | '.join(disp[c]) + ' |')
T32.append('| 中位占比 | ' + ' | '.join(med_row) + ' |')
T32 = '\n'.join(T32)
lo = min(float(x) for v in disp.values() for x in v if x != '—')
hi = max(float(x) for v in disp.values() for x in v if x != '—')

# ---------- 3.3 头尾 ----------
SC = list(csv.DictReader(open(
    f'{ROOT}/data/嘉定区/学校/名额到校最低分数线-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
ALIAS = {'上海市嘉定区德富路中学': '交大附中附属嘉定德富中学',
         '上海市嘉定区杨柳初级中学': '上海市嘉定区嘉二实验学校',
         '上海嘉定区世界外国语学校': '上海嘉定区世外学校'}


# 头/尾分组同样只用**公办**（民办不参与排名）
PRIV = {n for n, r in W.items() if r['ownership'] == '民办'}


def top(y, code, k=5):
    r_ = sorted([(float(r['min_score']),
                  ALIAS.get(r['junior_high_school'], r['junior_high_school']))
                 for r in SC if r['year'] == y and r['senior_high_school_code'] == code
                 and ALIAS.get(r['junior_high_school'], r['junior_high_school']) not in PRIV],
                reverse=True)
    return '、'.join(sh(n) for _, n in r_[:k]), r_[0][1]


def diff(y, code):
    v = [float(r['min_score']) for r in SC
         if r['year'] == y and r['senior_high_school_code'] == code]
    return sum(v) / len(v)


T33 = ['| 年 | 线难度排序（当年公办校均分） | 头线 | 尾线 |', '|---|---|---|---|']
tops = {}
for y in ('2025', '2026'):
    T33.append(f"| {y} | 交大附中嘉定分校 {diff(y, '142002'):.1f} > 上师大附中嘉定新城 "
               f"{diff(y, '142004'):.1f} > 嘉定一中 {diff(y, '142001'):.1f} "
               f"| 交大附中嘉定分校 | 嘉定一中 |")
    for code, lab in (('142002', '头线'), ('142001', '尾线')):
        s_, mx = top(y, code)
        tops[(y, lab)] = s_
T33 = '\n'.join(T33)

p = f'{D}/分析报告.md'
s = open(p, encoding='utf-8').read()

# 2.3 表格
i = s.index('| 学校 | 办学性质 | 创办 | 有成绩年份 |')
j = s.index('**⚠ 这 4 行的位次不能直接读作「水平」**')
s = s[:i] + NEW_DISCLOSE + '\n\n' + s[j:]

# 3.1 表
i = s.index('| 检验 | n | Spearman | 解读 |')
j = s.index('**如何解读这个')
s = s[:i] + T31 + '\n\n' + s[j:]
s = s.replace('在 3.1 的同线内检验（ρ=−0.272，名额多的校名次仍更靠前）',
              f'在 3.1 的同线内检验（ρ={rho_all:+.3f}，名额多的校名次仍更靠前）')

# 3.2 表
i = s.index('| 线 | 2022 | 2023 | 2024 | 2025 | 2026 |')
j = s.index('**结论**：嘉定各校在各线上的名额深度')
s = s[:i] + T32 + '\n\n' + s[j:]
s = s.replace('同一线内，校际占比极差达 0.048–0.092',
              f'同一线内，校际占比极差达 {lo:.3f}–{hi:.3f}')
s = s.replace('极差从 2022 年的 0.091–0.092 收窄到 2026 年的 0.048–0.056',
              f'极差从 2022 年的 {disp["142001"][0]}–{disp["142002"][0]} 收窄到 2026 年的 '
              f'{min(disp["142001"][4], disp["142002"][4])}–{max(disp["142001"][4], disp["142002"][4])}')
s = s.replace('中位占比几乎不变**（0.03–0.04 → 0.03–0.03）',
              f'中位占比几乎不变**（{med_row[0]} → {med_row[-1]}）')

# 3.3 表
i = s.index('| 年 | 线难度排序')
j = s.index('- 头线（交大附中嘉定分校）前 5：')
T33b = T33 + '\n'
s = s[:i] + T33b + s[j:]
s = s.replace('- 头线（交大附中嘉定分校）前 5：2025',
              f'- 头线（交大附中嘉定分校）前 5：2025 {tops[("2025", "头线")]}；\n  2026 {tops[("2026", "头线")]}。\n- 尾线（嘉定一中）前 5：2025 {tops[("2025", "尾线")]}；2026 {tops[("2026", "尾线")]}。\n- 旧：尾线（嘉定一中）前 5：2025', 1)

open(p, 'w', encoding='utf-8').write(s)
print('2.3 / 3.1 / 3.2 / 3.3 已同步')
print(f'3.1 名额~P ρ={rho_p:+.3f}｜同线内 n={len(pairs)} ρ={rho_all:+.3f}')
print(f'3.2 极差范围 {lo:.3f}–{hi:.3f}')
print(f'2026 头线前5: {tops[("2026", "头线")]}')
print(f'2026 尾线前5: {tops[("2026", "尾线")]}')
