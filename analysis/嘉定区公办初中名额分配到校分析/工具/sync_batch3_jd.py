# -*- coding: utf-8 -*-
"""批次 3：同步第 4 章（收敛）与第 5 章（趋势）到新口径。"""
import csv
import os
from collections import Counter

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YS = ['2022', '2023', '2024', '2025', '2026']
IND = list(csv.DictReader(open(f'{D}/收敛指标-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
TRD = {r['metric']: r for r in csv.DictReader(
    open(f'{D}/收敛趋势检验-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
CLS = list(csv.DictReader(open(f'{D}/趋势分类-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
M = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/rank-多口径总表-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}


def sh(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


# ---------- 4.2 ----------
L = ['| 年 | 固定样本 | 公办池 | 公办池中位 | σ | CV | IQR | Gini | P90−P10 | 极差 | MAD |',
     '|---|---|---|---|---|---|---|---|---|---|---|']
for r in IND:
    L.append(f"| {r['year']} | {r['n_fixed']} | {r['pool_n']} | {float(r['pool_median']):.1f} "
             f"| {float(r['sigma']):.2f} | {float(r['cv']):.4f} | {float(r['iqr_norm']):.4f} "
             f"| {float(r['gini']):.4f} | {float(r['r90_10_norm']):.4f} "
             f"| {float(r['range_norm']):.4f} | {float(r['mad_norm']):.4f} |")
T42 = '\n'.join(L)

# ---------- 4.3 ----------
METRICS = [('sigma', 'σ'), ('cv', 'CV'), ('iqr_norm', 'IQR'), ('gini', 'Gini'),
           ('r90_10_norm', 'P90−P10'), ('range_norm', '极差'), ('mad_norm', 'MAD')]
L = ['| 指标 | 2022 | 2026 | 斜率 b（/年） | 95% CI | p |', '|---|---|---|---|---|---|']
n_pos = n_neg = 0
for k, lab in METRICS:
    t = TRD[k]
    b = float(t['slope_b'])
    n_pos += b > 0
    n_neg += b < 0
    L.append(f"| {lab} | {float(t['v2022']):.5f} | {float(t['v2026']):.5f} | {b:+.6f} "
             f"| [{float(t['ci_lo']):+.5f}, {float(t['ci_hi']):+.5f}] | {float(t['p']):.3f} |")
T43 = '\n'.join(L)

# ---------- 4.1 混淆量化 ----------
L = ['| 年 | 固定样本（27 所）外的公办校数 | 它们的平均分位（0=最弱，1=最强） |', '|---|---|---|']
for r in IND:
    L.append(f"| {r['year']} | {r['outside_n']} | {r['outside_pct_mean'] or '—'} |")
T41 = '\n'.join(L)

qq = TRD['qq_slope']

# ---------- 5.2 ----------
L = ['| 类别 | 学校 | n | SEN | OLS 斜率 | Δrel（首末年差） | 近 3 年斜率 | MK p |',
     '|---|---|---|---|---|---|---|---|']
for r in CLS:
    L.append(f"| {r['trend_class']} | {sh(r['junior_high_school'])} | {r['n_years']} "
             f"| {r['sen']} | {r['sen_ols']} | {r['delta_rel']} | {r['sen_recent3']} | {r['mk_p']} |")
T52 = '\n'.join(L)
c = Counter(r['trend_class'] for r in CLS)

# ---------- 5.4 ----------
up = [r for r in CLS if float(r['sen']) > 0 and float(r['sen_recent3']) < 0]
dn = [r for r in CLS if float(r['sen']) < 0 and float(r['sen_recent3']) > 0]
T54 = ('| 类型 | 学校（SEN → 近 3 年斜率） |\n|---|---|\n'
       '| 五年升、近三年降 | '
       + '；'.join(f"{sh(r['junior_high_school'])}（{r['sen']} → {r['sen_recent3']}）" for r in up)
       + ' |\n| 五年降、近三年升 | '
       + '；'.join(f"{sh(r['junior_high_school'])}（{r['sen']} → {r['sen_recent3']}）" for r in dn) + ' |')

# ---------- 5.5 阈值敏感 ----------
near = [r for r in CLS if abs(abs(float(r['sen'])) - 1.10) < 0.02]
T55 = ('**' + '、'.join(f"{sh(r['junior_high_school'])} SEN={r['sen']}"
                       f"（{r['trend_class']}）" for r in near) + '**'
       if near else '**无学校紧贴阈值**')

n_sig = sum(1 for r in CLS if r['mk_p'] != '' and float(r['mk_p']) < 0.05)

p = f'{D}/分析报告.md'
s = open(p, encoding='utf-8').read()

# 4.1 混淆量化表
i = s.index('| 年 | 固定样本（27 所）外的新增校数 |')
j = s.index('**平均分位长期在')
s = s[:i] + T41 + '\n\n' + s[j:]
# 结论句里的分位区间按新数据改写
import re as _re
s = _re.sub(r'\*\*平均分位长期在 [\d.]+–[\d.]+',
            '**平均分位长期在 0.66–0.96', s)

# 4.2 表
i = s.index('| 年 | 固定样本 | 全池 | 全池中位 |')
j = s.index('### 4.3 趋势检验')
s = s[:i] + T42 + '\n\n' + s[j:]
s = s.replace('指标均以「当年全区全池中位」归一化', '指标均以「当年**公办池**中位」归一化')
s = s.replace('全区参与分位计算的池子逐年扩大：**2022 年 27 所 → 2026 年 39 所**。',
              '全区**公办**池逐年扩大：**2022 年 27 所 → 2026 年 32 所**'
              '（2024 年起民办已全部退出排名口径）。')

# 4.3 表
i = s.index('| 指标 | 2022 | 2026 | 斜率 b（/年） |')
j = s.index('**6 个指标的 95% 置信区间')
s = s[:i] + T43 + '\n\n' + s[j:]
s = s.replace('**6 个指标的 95% 置信区间全部跨过 0**，方向 4 正 2 负，无一达到 p<0.1。',
              f'**6 个指标的 95% 置信区间全部跨过 0**，方向 {n_pos} 正 {n_neg} 负，'
              f'无一达到 p<0.1。')

# 5.2 清单
i = s.index('| 类别 | 学校 | n | SEN |')
j = s.index('### 5.3')
s = s[:i] + T52 + '\n\n' + s[j:]

# 5.3 计数
s = s.replace('| Mann-Kendall 未校正 p<0.05 | **1 所** |',
              f'| Mann-Kendall 未校正 p<0.05 | **{n_sig} 所** |')
i = s.index('- 阈值 **|sen| = 1.10 分/年**')
s = s[:i] + f"""- 阈值 **|sen| = 1.10 分/年**，取自实测 |sen| 升序排列的**自然间隙**（0.86 与 1.10 之间断层），非主观设定；
- 分类优先级：方向不一 > 明显上升/下降 > 温和升/降。

**2026-10-03 结果（仅公办池口径）**：明显上升 **{c.get('明显上升', 0)} 所**、
明显下降 **{c.get('明显下降', 0)} 所**、温和上升 {c.get('温和上升', 0)} 所、
温和下降 {c.get('温和下降', 0)} 所、方向不一 {c.get('方向不一', 0)} 所。

""" + s[i + len('- 阈值 **|sen| = 1.10 分/年**，取自实测 |sen| 升序排列的**自然间隙**（0.86 与 1.10 之间断层），非主观设定；\n- 分类优先级：方向不一 > 明显上升/下降 > 温和升/降。\n\n'):]

# 5.4 表
i = s.index('| 类型 | 学校（SEN → 近 3 年斜率） |')
j = s.index('最典型的是')
s = s[:i] + T54 + '\n\n' + s[j:]

# 5.5 阈值敏感
i = s.index('**朱桥学校 SEN =')
j = s.index('### 5.6')
s = s[:i] + (T55 + '\n\n阈值 1.10 来自自然间隙，但**个别学校恰好紧贴阈值**，'
              '「明显上升 N 所」这个数字对阈值敏感，引用时应一并说明。\n\n') + s[j:]

open(p, 'w', encoding='utf-8').write(s)
print('第 4 章 / 第 5 章已同步')
print(f'  4.3 方向：{n_pos} 正 {n_neg} 负')
print(f'  5.2 分类：{dict(c)}')
print(f'  5.3 未校正 p<0.05：{n_sig} 所')
print(f'  5.5 阈值敏感：{T55[:90]}')
print(f'  4.4 Q-Q β={qq["slope_b"]} CI=[{qq["ci_lo"]},{qq["ci_hi"]}] p={qq["p"]}')
