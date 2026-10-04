#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 3.4 判定：与 0.3 基线（归并前 committed 宽表）逐格比对。

基线文件：validation/baseline-wide-premerge.csv
  = 提交 5aa61a1 的宽表，44 行 × 199 列（兴陇独立成行、西校未入表、无 row_type）。

比对范围：两版共有的学校 × 共有的非「名次类」字段
  （排除 rank_P_* / P_recent*：聚合名次是顺序秩，单校变动会引发全体重排，
    无法逐校归因；名次联动单独用 shift_wq_eq 观察）。

判定：全部差异必须落在下列**三类已声明影响面**内，否则判为异常。
  A. 归并面：曹杨第二中学附属实验中学（吸收兴陇 2022）
  B. ownership 补全面：光新 / 武宁（'' → '公办'，阶段 2.1）
  C. 名次联动面：shift_wq_eq（曹二名次 23→25 引发周边 ±1 位）

容差：数值 5e-4（与阶段 2.3 独立复算同容差），位次/计数精确相等。
"""
import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_BASE_REL = 'validation/baseline-wide-premerge.csv'
_TASK_DIR = '.trellis/tasks/10-04-putuo-apply-jiading-method'
# 基线随 Trellis 任务目录走：任务归档后从 `tasks/<id>/` 移到
# `tasks/archive/<YYYY-MM>/<id>/`。硬编码任一位置都会在另一种状态下失效
# —— 普陀归档（defc75e）后本门禁即因此 FileNotFoundError，而当时**归档后
# 未复跑门禁**，导致它空挂了整个提交周期才发现。故两种位置都找，
# 且**都找不到就直接报错**，绝不静默跳过。
_ARCH = sorted((_ROOT / '.trellis/tasks/archive').glob('*/10-04-putuo-apply-jiading-method'))
_CANDS = [_ROOT / _TASK_DIR / _BASE_REL] + [p / _BASE_REL for p in _ARCH]
BASE = next((p for p in _CANDS if p.exists()), None)
if BASE is None:
    raise SystemExit('❌ 找不到基线文件 baseline-wide-premerge.csv，已尝试：\n  ' +
                     '\n  '.join(str(p) for p in _CANDS) +
                     '\n基线丢失时本门禁无法判定差异是否落在声明面内，不得跳过。')
CUR = Path(__file__).resolve().parents[1] / '宽表-初中水平-普陀区-2022-2026.csv'

MERGED = '上海市曹杨第二中学附属实验中学'
OWN_FIX = {'上海市光新学校', '上海市武宁中学'}
SHIFT_FIELD = 'shift_wq_eq'
TOL = 5e-4


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def is_exempt(k):
    return k.startswith(('rank_P_', 'P_recent', 'rel_', 'row_type',
                        'exit_reason', 'junior_high_school_former_names'))


def neq(a, b):
    if a == b:
        return False
    try:
        return abs(float(a) - float(b)) >= TOL
    except (TypeError, ValueError):
        return True


def main():
    old = {r['junior_high_school']: r for r in load(BASE)}
    new = {r['junior_high_school']: r for r in load(CUR)}
    common = sorted(set(old) & set(new))
    sample = next(iter(new.values()))
    fields = [c for c in sample if c in old[common[0]] and not is_exempt(c)]

    a = b = c = 0
    bad = []
    for s in common:
        for k in fields:
            if not neq(old[s].get(k, ''), new[s].get(k, '')):
                continue
            if s == MERGED:
                a += 1
            elif k == 'ownership' and s in OWN_FIX:
                b += 1
            elif k == SHIFT_FIELD:
                c += 1
            else:
                bad.append((s, k, old[s].get(k, ''), new[s].get(k, '')))

    dropped = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    print(f'基线 {len(old)} 行 → 当前 {len(new)} 行')
    print(f'  归并后消失：{[x.replace("上海市", "") for x in dropped]}')
    print(f'  归并后新增：{[x.replace("上海市", "") for x in added]}')
    print(f'逐格比对：{len(common)} 校 × {len(fields)} 字段 = {len(common) * len(fields)} 格')
    print(f'  A 归并面（{MERGED.replace("上海市", "")}）      {a:>3} 处')
    print(f'  B ownership 补全面（光新/武宁）  {b:>3} 处')
    print(f'  C 名次联动面（{SHIFT_FIELD}）  {c:>3} 处')
    print(f'  合计 {a + b + c} 处，异常 {len(bad)} 处')
    if bad:
        print('\n❌ 异常差异（不在任何已声明影响面内）：')
        for s, k, x, y in bad[:20]:
            print(f'  {s} | {k} | {x!r} → {y!r}')
        return 1
    assert (dropped, added) == (['上海市兴陇中学'], []), \
        f'行集变动与声明不符：消失={dropped} 新增={added}'
    print('\n✅ 全部差异落在三类已声明影响面内，异常 0；行集变动与归并声明一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
