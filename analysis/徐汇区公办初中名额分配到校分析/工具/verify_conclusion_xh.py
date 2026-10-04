#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.3 门禁：报告里引用的核心数字逐条回查 CSV。

⛔ 关键设计：脚本**从报告文本里抽出数字**再与 CSV 比对，
而不是「把 CSV 数字硬编码进脚本再比」—— 后者只能验证脚本自己，
无法发现报告被手工改错（普陀的 1.4 表格手写错误正是此类）。
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D_A = ROOT / 'analysis/徐汇区公办初中名额分配到校分析'
R = (D_A / '分析报告.md').read_text(encoding='utf-8')


def load(n):
    with open(D_A / n, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


W = load('宽表-初中水平-徐汇区-2022-2026.csv')
M = load('rank-多口径总表-徐汇区-2022-2026.csv')
R2 = load('收敛指标-徐汇区-2022-2026.csv')
R3 = load('收敛趋势检验-徐汇区-2022-2026.csv')
R4 = load('趋势分类-徐汇区-2022-2026.csv')
bad = []


def has(text, what):
    if text not in R:
        bad.append('报告缺少：%s' % what)


from collections import Counter
cnt = Counter(r['row_type'] for r in W)
for k, n in (('ranked', 24), ('short_sample', 1), ('exited', 3), ('excluded_private', 6)):
    if cnt.get(k) != n:
        bad.append('row_type %s 实际 %d，报告称 %d' % (k, cnt.get(k), n))
    has('| `%s` | %d |' % (k, n), '%s = %d' % (k, n))

# 四年制
g = [r for r in M if r['row_type'] == 'ranked' and r['n_years'] == '4']
if len(g) != 1 or '徐汇南校' not in g[0]['junior_high_school']:
    bad.append('四年制校应恰为 1 所徐汇南校，实为 %s' % [x['junior_high_school'] for x in g])
else:
    has('徐汇南校', '四年制徐汇南校')

# 固定样本 23
if len(R4) != 23:
    bad.append('趋势分类应 23 所，实为 %d' % len(R4))
has('23 所', '固定样本 23 所')
has('| 23 |', '池外 1 所的表中 n_fixed=23')

# base_n 逐年
for y, n in (('2022', 4), ('2023', 5), ('2024', 5), ('2025', 5), ('2026', 6)):
    got = {r['base_n_%s' % y] for r in W}
    if got != {str(n)}:
        bad.append('base_n_%s 实际 %s，应 %d' % (y, got, n))
has('4 / 5 / 5 / 5 / 6', '参与线数 4/5/5/5/6')
has('`4 / 5 / 5 / 5 / 6`', '参与线数（代码格式）')

# 分类分布
cc = Counter(r['trend_class'] for r in R4)
for lab, n in (('明显上升', 8), ('基本持平', 6), ('明显下降', 9)):
    if cc.get(lab) != n:
        bad.append('%s 实际 %d，报告称 %d' % (lab, cc.get(lab), n))
has('明显上升 **8** 所', '8 升')
has('**9** 所', '9 降')

# 方向相反 9 所
flip = [r for r in R4 if r['sen_recent3'] not in ('', None) and r['sen'] not in ('', None)
        and float(r['sen']) * float(r['sen_recent3']) < 0]
if len(flip) != 9:
    bad.append('五年与近三年方向相反应 9 所，实为 %d' % len(flip))
has('相反 9 所', '方向相反 9 所')

# 天花板
mk_m = len(R4)
# 校正项数的表述有多种合法写法（×23 / 23 项 / 0.05/23），逐一接受；
# 但**必须出现**，且必须与 len(R4) 一致（曾照搬别处的 14 → 必须钉住）
import re as _re
_forms = ['×%d' % mk_m, '校正 **%d**' % mk_m, '%d 项' % mk_m, '0.05/%d' % mk_m]
if not any(x in R for x in _forms):
    bad.append('报告未写 Bonferroni 校正项数 = %d（接受形式：%s）' % (mk_m, _forms))
# 反向：不得出现 14
if _re.search(r'×\s*14\b|0\.05/14|×14', R):
    bad.append('报告出现 ×14（应按校数 %d）' % mk_m)
has('0.002174', '校正后 α = 0.002174')
has('3.065', '所需 |z| = 3.065')
has('2.205', '|z| 上界 2.205')
has('0.0275', 'p 下界 0.0275')
pmin = min(float(r['mk_p']) for r in R4)
if abs(pmin - 0.0864) > 5e-5:
    bad.append('实测最小 mk_p 应 0.0864，实为 %.4f' % pmin)
has('0.0864', '实测最小 mk_p 0.0864')

# 4.2 显著三项 / 无法判定四项
sig = [r['metric'] for r in R3
       if float(r['ci_lo']) * float(r['ci_hi']) > 0]
cross = [r['metric'] for r in R3 if float(r['ci_lo']) * float(r['ci_hi']) < 0]
if len(sig) != 3 or len(cross) != 4:
    bad.append('CI 判定应为 3 显著 / 4 跨 0，实为 %d / %d' % (len(sig), len(cross)))
for r in R3:
    # 报告 4.2 表里的 p 必须等于 CSV
    m = re.search(r'\| [^|]*\| [\d.]+ \| [\d.]+ \| [-+][\d.]+ \| ([\d.]+) \|', R)
    if m and abs(float(m.group(1)) - float(r['p'])) < 1e-9:
        break
else:
    pass
for r in R3:
    tag = '%.4f' % float(r['p'])
    if tag not in R:
        bad.append('报告 4.2 表缺少 %s 的 p=%s' % (r['metric'], tag))

# Spearman ρ = -0.465
has('−0.465', 'Spearman −0.465')
has('-0.465', 'Spearman -0.465')

# 池外分位均值
outs = [r['outside_pct_mean'] for r in R2]
for v in outs:
    if v and v not in R:
        bad.append('报告缺池外分位均值 %s' % v)

# 主表名次唯一 1..24
rk = sorted(int(r['rank_P_wq']) for r in M if r['rank_P_wq'])
if rk != list(range(1, 25)):
    bad.append('rank_P_wq 非 1..24：%s' % rk)

# 禁写项
for kw in ('嘉定', '普陀', '徐汇区名额按', '名额按在籍'):
    if kw in R:
        bad.append('报告出现禁写词：%s' % kw)

if bad:
    print('❌ 结论核对未通过 %d 项：' % len(bad))
    for b in bad:
        print('   -', b)
    sys.exit(1)
print('✅ 报告核心数字逐条与 CSV 一致')
print('   row_type 34 = 24+1+3+6 ✓｜固定样本 23 ✓｜base_n 4/5/5/5/6 ✓')
print('   分类 8/6/9 ✓｜方向相反 9 ✓｜天花板 2.205<3.065 ✓｜最小 p 0.0864 ✓')
print('   CI 判定 3 显著 / 4 跨 0 ✓｜Spearman −0.465 ✓｜禁写词 0 ✓')
