#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.4 门禁：与 0.1 基线（**旧口径**宽表）比对。

⚠️ 本比对**不是**逐格相等校验 —— 基线是**旧方法**产物（`mean_rank_base4` 平均名次、
117 列 × 28 行、无 `row_type`），与新口径**不可逐格对齐**。

可比的部分只有**身份与覆盖**：
  · 学校集合（应 34 = 28 公办 + 6 民办）
  · 每校 `years_included`
  · 旧有的 `quota_zone_avg` 与新 `quota6_avg`（同源：区属线名额之和）

不可比的部分（旧有、新无）：`mean_rank_base4*` / `nanmo_rank*` / `CORE` 相关列。
判定：差异必须**全部落在已声明的口径迁移面**内，且身份类字段逐项相等。
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D_A = ROOT / 'analysis/徐汇区公办初中名额分配到校分析'

# 基线文件随 Trellis 任务目录走：任务归档后从 `tasks/<id>/` 移到
# `tasks/archive/<YYYY-MM>/<id>/`。硬编码任一位置都会在另一种状态下
# FileNotFoundError —— 本轮归档后即因此失效过一次（归档后未复跑门禁）。
# 故两种位置都找，且**都找不到就直接报错**，绝不静默跳过校验。
_BASE_REL = 'validation/baseline-wide-premerge.csv'
_ARCH = sorted((ROOT / '.trellis/tasks/archive').glob('*/10-04-xuhui-apply-jiading-method'))
_CANDS = ([ROOT / '.trellis/tasks/10-04-xuhui-apply-jiading-method' / _BASE_REL]
          + [p / _BASE_REL for p in _ARCH])
BASE = next((p for p in _CANDS if p.exists()), None)
if BASE is None:
    raise SystemExit(
        '❌ 找不到基线文件 baseline-wide-premerge.csv，已尝试：\n  ' +
        '\n  '.join(str(p.relative_to(ROOT)) for p in _CANDS) +
        '\n基线丢失时本门禁无法判定「差异是否落在声明面内」，不得跳过。')


def load(p):
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


old = {r['junior_high_school']: r for r in load(BASE)}
new = {r['junior_high_school']: r for r in load(D_A / '宽表-初中水平-徐汇区-2022-2026.csv')}
bad = []
print('基线（旧口径）%d 行 × %d 列 ｜ 当前（新口径）%d 行 × %d 列'
      % (len(old), len(next(iter(old.values()))), len(new), len(next(iter(new.values())))))

only_new = sorted(set(new) - set(old))
only_old = sorted(set(old) - set(new))
print('  当前新增（基线无）：%s' % ('、'.join(x.replace('上海市', '') for x in only_new) or '无'))
print('  基线独有（当前无）：%s' % ('、'.join(x.replace('上海市', '') for x in only_old) or '无'))

# ---- 已声明的口径迁移面（基线为旧方法产物）----
# ① 民办 6 所：旧脚本 `ownership=='公办'` 过滤，从未进旧宽表；新口径纳入并标
#    `excluded_private` ⇒ 34 = 28 公办 + 6 民办。
# ⛔ 校名**不得手写**（易错：世外/西南模范在名录里无「民办」二字）——
# 从宽表的 row_type == 'excluded_private' 直接取，避免名不符导致门禁误报。
MINBAN = {r['junior_high_school'] for r in load(D_A / '宽表-初中水平-徐汇区-2022-2026.csv')
          if r['row_type'] == 'excluded_private'}
assert len(MINBAN) == 6, '民办应 6 所，实为 %d：%s' % (len(MINBAN), MINBAN)
# ② 退出校 3 所 + 短样本 1 所：旧脚本按「有计划行」纳入，但当前口径要求
#    「至少 1 条分数线可算加权均分」⇒ 位育体校的 2023（有额无线）不再计入。
EXPECT_ONLY_NEW = MINBAN | {
    '上海市宛平中学', '上海师大附中附属龙华中学', '上海市徐汇位育体校',
    '上海市徐汇区上汇实验学校'}
unexpected = set(only_new) - EXPECT_ONLY_NEW
if unexpected:
    bad.append('出现未预期的新增学校：%s' % unexpected)
if only_old:
    bad.append('基线独有但当前缺失：%s' % only_old)

# 身份类字段必须逐项相等；`years_included` 允许**仅因口径变更**而不同
n_id = 0
COVER_CHANGE = {}          # 校 -> (基线, 当前, 原因)
for s in sorted(set(old) & set(new)):
    o, w = old[s], new[s]
    if o.get('junior_high_school_code') != w.get('junior_high_school_code'):
        bad.append('%s 代码不一致：%s vs %s'
                   % (s, o.get('junior_high_school_code'), w.get('junior_high_school_code')))
    n_id += 1
    if o.get('years_included') != w.get('years_included'):
        COVER_CHANGE[s] = (o.get('years_included'), w.get('years_included'),
                           '新口径以「可算加权均分」计年，有额无线的年份不计入')
        if o.get('years_included') == '1' or int(w.get('years_included', 0)) > int(o.get('years_included', 0)):
            bad.append('%s 覆盖年数异常变化：%s → %s'
                       % (s, o.get('years_included'), w.get('years_included')))
        n_id += 1
if COVER_CHANGE:
    print('  覆盖年数因口径变更而不同（%d 所，均为「有额无线」年份被剔除）：' % len(COVER_CHANGE))
    for k, (a, b, why) in COVER_CHANGE.items():
        print('     %s %s → %s（%s）' % (k.replace('上海市', ''), a, b, why))
if len(COVER_CHANGE) > 1:
    bad.append('覆盖年数变动超过 1 所，须逐条确认是否均为口径变更')

# 名额同源核对：旧 `quota_zone_total_{y}` vs 新 `quota6_{y}`（都是区属线名额之和）
n_q = 0
qdiff = []
for s in sorted(set(old) & set(new)):
    o, w = old[s], new[s]
    for y in (2022, 2023, 2024, 2025, 2026):
        a, b = o.get('quota_zone_total_%d' % y, ''), w.get('quota6_%d' % y, '')
        if a in ('', None) or b in ('', None):
            continue
        n_q += 1
        if abs(float(a) - float(b)) > 0.5:
            qdiff.append((s.replace('上海市', ''), y, a, b))
print('  名额同源核对：%d 格，差异 %d 处' % (n_q, len(qdiff)))
for x in qdiff[:8]:
    print('     %s %s 基线 %s vs 当前 %s' % x)
# 允许的差异：位育体校 2023（基线含「有额无线」的名额行，当前仅计有分数的线）
ALLOWED_Q = {('徐汇位育体校', 2023)}
hard_q = [x for x in qdiff if (x[0], x[1]) not in ALLOWED_Q]
if hard_q:
    bad.append('名额同源核对出现未预期差异：%s' % hard_q[:5])
else:
    for x in qdiff:
        if (x[0], x[1]) in ALLOWED_Q:
            print('     ↑ 已声明允许：%s %s 基线 %s vs 当前 %s（有额无线被剔除）' % x)

# 旧有的、新无的列（应全部属于「旧口径特有」）
old_only_cols = [c for c in next(iter(old.values()))
                 if c not in new and not c.startswith(('quota_', 'score_'))]
print('  旧宽表特有列 %d 个（例：%s）'
      % (len(old_only_cols), '、'.join(old_only_cols[:4])))

if bad:
    print('\n❌ 基线比对未通过 %d 项：' % len(bad))
    for b in bad:
        print('   -', b)
    sys.exit(1)
print('\n✅ 基线比对通过：身份类字段 %d 格全等；差异全部落在已声明的口径迁移面内' % n_id)
print('   （逐格相等不适用于本比对 —— 基线是旧方法产物，见脚本 docstring）')
