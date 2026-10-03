# -*- coding: utf-8 -*-
"""生成嘉定区主表（含「名次·变化」合并列与趋势列，格式参考黄浦区）。

口径要点（与黄浦的差异必须显式处理）：
  - 黄浦「2026 名次」与五年榜同池（都是 17 所公办），可直接相减；
  - 嘉定 2026 年**公办池为 32 所**、五年榜为 28 所，**仍不同池**。
    本表把三列变化都改为在**同一公办池口径**下可比：
      近 3 年 / 近 2 年  -> rank_P_wq vs rank_P_recent3 / rank_P_recent2（同一 28 所）
      2026              -> rank_P_wq vs 2026 位次（**同为公办**，但 28 vs 32 略有差异，
                            已在列说明中标注）
  变化 = 五年榜名次 − 该口径名次，**正 = 较五年榜上升**。
"""
import csv
import os

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


W = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
M = list(csv.DictReader(
    open(f'{D}/rank-多口径总表-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
S = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/趋势分类-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}

HEAD = ('| 名 | 初中 | 数据年度 | P_wq | rel 均名 | 名额 | SEN | 等权名次 | Z 名次 '
        '| 线性 | 指数 | **近 3 年（名次·变化）** | **近 2 年（名次·变化）** '
        '| **2026（名次·变化）** | 趋势 |')
SEP = '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|'


def fmt(rk, base):
    """名次（变化）——变化 = 五年榜名次 − 该口径名次，正 = 上升"""
    if rk in ('', None):
        return '—'
    d = base - int(float(rk))
    return f'**{int(float(rk))}**（{d:+d}）'


L = [HEAD, SEP]
rk_rows = [r for r in M if r['row_type'] == 'ranked']
for r in sorted(rk_rows, key=lambda r: int(r['rank_P_wq_all'])):
    n = r['junior_high_school']
    w, s = W[n], S[n]
    base = int(r['rank_P_wq_all'])
    r26 = w['rank_base3_wq_2026']
    L.append(
        f"| {base} | {sh(n)} | {'2022–2026' if w['years_included'] == '5' else '2023–2026'} "
        f"| {float(r['P_wq_all']):.3f} | {float(w['rel_avg']):+.2f} "
        f"| {float(w['quota3_avg']):.1f} | {float(w['SEN']):+.3f} "
        f"| {r['rank_P_eq_all']} | {r['rank_Z_wq_comb']} | {r['rank_P_lin']} | {r['rank_P_exp']} "
        f"| {fmt(r['rank_P_recent3'], base)} | {fmt(r['rank_P_recent2'], base)} "
        f"| {fmt(r26, base)} | {s['trend_class']} |")

# 新开办学校：只有近 2 年 / 2026 有单年数据，无五年榜故变化不可算
for r in [x for x in M if x['row_type'] == 'new_school']:
    n = r['junior_high_school']
    w = W[n]
    yr = '2025–2026' if w['years_included'] == '2' else '2026'
    L.append(
        f"| — | {sh(n)} ^ | {yr} | — | — | — | — | — | — | — | — "
        f"| — | — | {'**' + str(int(float(w['rank_base3_wq_2026']))) + '**（—）' if w['rank_base3_wq_2026'] else '—'} "
        f"| 数据不足 |")

out = '\n'.join(L)
open('/tmp/main_table2.md', 'w', encoding='utf-8').write(out)
print(out)
print(f'\n共 {len(L) - 2} 行（{len(rk_rows)} 入榜 + 4 新开办），'
      f'{len(L[0].split("|")) - 2} 列')
