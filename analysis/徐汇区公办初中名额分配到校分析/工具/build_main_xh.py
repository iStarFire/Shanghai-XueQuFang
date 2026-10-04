#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""徐汇区名额到校分析 —— 阶段 3：多口径主表

产出 `rank-多口径总表-徐汇区-2022-2026.csv`，列定义见
.trellis/tasks/10-04-xuhui-apply-jiading-method/design.md §2.1b。

⚠️ 与嘉定 / 普陀主表的**三处不可比**（报告须声明）
1. 徐汇**无线分组**（D-XH2 取消分层）⇒ 只有 `all` 一组，**没有 head/tail/comb**。
   徐汇 `P_wq` 只能与它们的 `P_wq_all` 对齐，**与 `P_wq_comb` 不可比**。
2. 徐汇用 `quota6_avg`（6 条定义集合 QU6），**不是** quota3_avg/quota4_avg。
3. 徐汇新增 rank_2026 / rank_chg_5y / rank_chg_1y，嘉定/普陀**没有**。

方向：位次数字**越小越强** ⇒ rank_chg = rank_2026 − 基年位次，
**负值 = 名次上升 = 变强**。

池差异：rank_2026 在**五年主池**（row_type='ranked'）内，rank_P_recent2 在
**近 2 年池**（含短样本）内 ⇒ 两列**不得相减**（implement 3.6 断言）。
"""
import csv
import statistics as st
from pathlib import Path

D_A = Path(__file__).resolve().parents[1]
WIDE = D_A / '宽表-初中水平-徐汇区-2022-2026.csv'
OUT = D_A / 'rank-多口径总表-徐汇区-2022-2026.csv'
YEARS = ['2022', '2023', '2024', '2025', '2026']
KEYS = ['lin', 'exp', 'recent3', 'recent2']


def num(x, nd=2):
    return '' if x is None else f'{x:.{nd}f}'


def f(x):
    return None if x in (None, '') else float(x)


with open(WIDE, encoding='utf-8-sig') as fh:
    W = list(csv.DictReader(fh))

MAIN = [r for r in W if r['row_type'] == 'ranked']
P3 = [r for r in W if r['row_type'] in ('ranked', 'short_sample')
      and all(f(r[f'rank_base_{y}']) is not None for y in ('2024', '2025', '2026'))]
P2 = [r for r in W if r['row_type'] in ('ranked', 'short_sample')
      and f(r['rank_base_2025']) is not None and f(r['rank_base_2026']) is not None]
POOLS = {'lin': MAIN, 'exp': MAIN, 'recent3': P3, 'recent2': P2}
nm = {r['junior_high_school']: r for r in W}
print(f'主池 {len(MAIN)}｜近 3 年池 {len(P3)}｜近 2 年池 {len(P2)}')
_diff = {r['junior_high_school'] for r in MAIN} ^ {r['junior_high_school'] for r in P2}
print('  主池 △ 近2年池 = %d 所: %s' % (
    len(_diff), '、'.join('%s(%s)' % (n, nm[n]['row_type']) for n in sorted(_diff))))
assert _diff, '主池与近 2 年池完全相同 ⇒ 3.6 前提不成立，需复核池定义'

for r in W:
    a, b = f(r['rank_P_wq']), f(r['rank_P_eq'])
    r['shift_wq_eq'] = num(a - b, 2) if a is not None and b is not None else ''
    rels = [(y, f(r['rel_%s' % y])) for y in YEARS if f(r['rel_%s' % y]) is not None]
    r['rel_first'] = num(rels[0][1], 4) if rels else ''
    r['rel_last'] = num(rels[-1][1], 4) if rels else ''
    r['delta_rel'] = num(rels[-1][1] - rels[0][1], 4) if len(rels) >= 2 else ''
    r['sen'] = num((rels[-1][1] - rels[0][1]) / (int(rels[-1][0]) - int(rels[0][0])), 4) \
        if len(rels) >= 2 and int(rels[-1][0]) != int(rels[0][0]) else ''
    qs = [f(r['quota6_%s' % y]) for y in YEARS]
    r['quota6_avg'] = num(st.fmean([x for x in qs if x is not None]), 2) \
        if any(x is not None for x in qs) else ''
    r['n_years'] = r['years_included']
    r['rank_2026'] = r.get('rank_base_2026', '')

COLS = (['junior_high_school', 'junior_high_school_code',
         'junior_high_school_former_names', 'row_type', 'ownership', 'n_years',
         'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
         'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq']
        + ['%s_%s' % (p, k) for k in KEYS for p in ('P', 'rank_P')]
        + ['rank_2026', 'rank_chg_5y', 'rank_chg_1y', 'mean_rank_wq_avg',
           'rel_avg', 'rel_first', 'rel_last', 'delta_rel', 'sen',
           'quota6_avg', 'base_n_2026'])
rows = [{c: r.get(c, '') for c in COLS} for r in
        sorted(W, key=lambda x: (f(x['rank_P_wq']) is None,
                                 f(x['rank_P_wq']) if f(x['rank_P_wq']) is not None else 999))]

# ==================== 断言（写盘前全部完成）================
assert len(rows) == len(W), '主表行数 ≠ 宽表行数'
for r in rows:
    if r['row_type'] == 'ranked':
        assert r['rank_P_wq'] != '', "%s ranked 但缺 rank_P_wq" % r['junior_high_school']
    else:
        assert r['rank_P_wq'] == '', "%s 非 ranked 却有 rank_P_wq" % r['junior_high_school']
_rk = sorted(int(r['rank_P_wq']) for r in rows if r['rank_P_wq'] != '')
assert _rk == list(range(1, len(_rk) + 1)), 'rank_P_wq 非 1..N：%s' % _rk
for k in KEYS:
    pn = {r['junior_high_school'] for r in POOLS[k]}
    got = sorted(int(r['rank_P_%s' % k]) for r in rows if r['rank_P_%s' % k] != '')
    assert got == list(range(1, len(got) + 1)), '%s 档名次非 1..N：%s' % (k, got)
    out = [r['junior_high_school'] for r in rows
           if r['junior_high_school'] not in pn and r['rank_P_%s' % k] != '']
    assert not out, '%s 档池外校有名次：%s' % (k, out)
# 主表不携带基年位次列，故断言时回到**宽表原始数据**取 —— 这样验证的是
# 「主表搬来的 rank_chg 与宽表原始位次一致」，而不是自证。
for r in rows:
    src = nm[r['junior_high_school']]
    r26 = f(r['rank_2026'])
    for col, base in (('rank_chg_5y', '2022'), ('rank_chg_1y', '2025')):
        v = f(r[col])
        b = f(src['rank_base_%s' % base])
        if v is None or r26 is None or b is None:
            assert v is None, '%s %s 应为空却有值 %s' % (r['junior_high_school'], col, v)
        else:
            assert abs(v - (r26 - b)) < 1e-9, \
                '%s %s 与宽表原始位次不一致' % (r['junior_high_school'], col)
# rank_2026 必须等于宽表的 2026 当年位次（逐校）
for r in rows:
    assert r['rank_2026'] == nm[r['junior_high_school']]['rank_base_2026'], \
        '%s rank_2026 与宽表不一致' % r['junior_high_school']
_up = [r for r in rows if f(r['rank_chg_5y']) is not None and f(r['rank_chg_5y']) < 0]
_dn = [r for r in rows if f(r['rank_chg_5y']) is not None and f(r['rank_chg_5y']) > 0]
_z = [r for r in rows if f(r['rank_chg_5y']) == 0]
flip = [r for r in rows if f(r['rank_chg_5y']) and f(r['rank_chg_1y'])
        and f(r['rank_chg_5y']) * f(r['rank_chg_1y']) < 0]
print('五年排名变化：上升 %d / 下降 %d / 不变 %d｜五年与最近一年方向相反 %d 所'
      % (len(_up), len(_dn), len(_z), len(flip)))
print('  方向相反：' + '、'.join(r['junior_high_school'].replace('上海市', '') for r in flip))
for k in KEYS:
    print('  %s: %d 所有名次' % (k, sum(1 for r in rows if r['rank_P_%s' % k] != '')))

with open(OUT, 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=COLS, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
print('写出 主表 %d 行 × %d 列' % (len(rows), len(COLS)))
