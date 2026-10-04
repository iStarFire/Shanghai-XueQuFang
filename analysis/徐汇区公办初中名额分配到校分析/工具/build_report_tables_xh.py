#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 5 辅助：把 CSV 转成报告用的 markdown 表格片段。

⚠️ 报告里的**所有数字表**都由本脚本生成，⛔ 不得手写 ——
普陀本轮教训：1.4 表格手写导致金鼎均分漏一个「—」、培佳 745.41 应为 745.40。
用法：python3 build_report_tables_xh.py <表名>，或 `all` 输出到 /tmp 便于粘贴。
"""
import csv
import statistics as st
from pathlib import Path

D_A = Path(__file__).resolve().parents[1]
YEARS = ['2022', '2023', '2024', '2025', '2026']


def load(n):
    with open(D_A / n, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def sh(n):
    return n.replace('上海市', '')


def f(x, nd=None):
    if x in (None, ''):
        return '—'
    v = float(x)
    return f'{v:.{nd}f}' if nd is not None else f'{v:g}'


W = load('宽表-初中水平-徐汇区-2022-2026.csv')
M = load('rank-多口径总表-徐汇区-2022-2026.csv')
R2 = load('收敛指标-徐汇区-2022-2026.csv')
R3 = load('收敛趋势检验-徐汇区-2022-2026.csv')
R4 = load('趋势分类-徐汇区-2022-2026.csv')
RANKED = [r for r in W if r['row_type'] == 'ranked']
mbyname = {r['junior_high_school']: r for r in M}


def t_sample():
    out = ['| row_type | 校数 | 含义 |', '|---|---|---|']
    lab = {'ranked': '五年全勤（1 所为四年制），进入跨年排名与趋势判断',
           'short_sample': '数据不足 4 年，不进排名',
           'exited': '已退出名额到校体系（原因待核实）',
           'excluded_private': '民办（2024 届起参与），不参与任何排名口径'}
    from collections import Counter
    c = Counter(r['row_type'] for r in W)
    for k in ('ranked', 'short_sample', 'exited', 'excluded_private'):
        out.append(f'| `{k}` | {c.get(k, 0)} | {lab[k]} |')
    return '\n'.join(out)


def t_pools():
    pk = {y: sum(1 for r in RANKED if r['mean_score_base_%s' % y] not in ('', None))
          for y in YEARS}
    head = ('| 年 | P/Z/ZR 百分位池 | `rel` 与收敛池（公办非退出） | 参与基线线 |\n'
            '|---|---|---|---|')
    return head + '\n' + '\n'.join(
        '| %s | %d | %d | %s |' % (
            y, sum(1 for r in W if r['P_base_%s' % y] != ''), pk[y],
            RANKED[0]['base_n_%s' % y]) for y in YEARS)


def t_main():
    out = ['| # | 学校 | P_wq | 名次 | 26 位次 | 5 年变化 | 近 3 年 | 近 2 年 | 年均名额 |',
           '|---|---|---|---|---|---|---|---|---|']
    for r in [x for x in M if x['row_type'] == 'ranked']:
        # quota6_avg / rel_avg / sen 在**主表**里（宽表没有 quota6_avg）
        out.append(
            f"| {r['rank_P_wq']} | {sh(r['junior_high_school'])} | {f(r['P_wq'], 4)} | "
            f"{r['rank_P_wq']} | {f(r['rank_2026'], 1)} | {f(r['rank_chg_5y'], 1)} | "
            f"{r['rank_P_recent3']} | {r['rank_P_recent2']} | {r['quota6_avg']} |")
    return '\n'.join(out)


def t_time():
    out = ['| # | 学校 | `lin` | `exp` | 近 3 年 | 近 2 年 | 2026 位次 | 五年 vs 一年方向 |',
           '|---|---|---|---|---|---|---|---|']
    for r in [x for x in M if x['row_type'] == 'ranked']:
        a, b = f(r['rank_chg_5y']), f(r['rank_chg_1y'])
        flip = '⚠️ 相反' if a != '—' and b != '—' and \
            float(r['rank_chg_5y']) * float(r['rank_chg_1y']) < 0 else '同向'
        out.append(f"| {r['rank_P_wq']} | {sh(r['junior_high_school'])} | "
                   f"{r['rank_P_lin']} | {r['rank_P_exp']} | {r['rank_P_recent3']} | "
                   f"{r['rank_P_recent2']} | {f(r['rank_2026'], 1)} | {flip} |")
    return '\n'.join(out)


def t_converge():
    ks = ['sigma', 'cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm']
    nm = {'sigma': 'σ', 'cv': 'CV', 'iqr_norm': 'IQR/中位', 'gini': 'Gini',
          'r90_10_norm': '(P90−P10)/中位', 'range_norm': '极差/中位', 'mad_norm': 'MAD/中位'}
    out = ['| 指标 | 2022 | 2026 | 斜率 | p | 95% CI | 判定 |', '|---|---|---|---|---|---|---|']
    for r in R3:
        lo, hi = float(r['ci_lo']), float(r['ci_hi'])
        out.append(f"| {nm[r['metric']]} | {f(r['v2022'], 5)} | {f(r['v2026'], 5)} | "
                   f"{f(r['slope_b'], 5)} | {f(r['p'], 4)} | "
                   f"[{lo:+.5f}, {hi:+.5f}] | "
                   f"{'**显著收窄**' if lo * hi > 0 else 'CI 跨 0 ⇒ 无法判定'} |")
    return '\n'.join(out)


def t_trend():
    out = ['| 学校 | 分类 | SEN | 近三年 SEN | Δrel | MK p | 校正后 p |', '|---|---|---|---|---|---|---|']
    for lab in ('明显上升', '基本持平', '明显下降'):
        for r in [x for x in R4 if x['trend_class'] == lab]:
            out.append(f"| {sh(r['junior_high_school'])} | {lab} | {f(r['sen'], 2)} | "
                       f"{f(r['sen_recent3'], 2)} | {f(r['delta_rel'], 1)} | "
                       f"{r['mk_p']} | {r['mk_p_bonferroni']} |")
    return '\n'.join(out)


def t_outside():
    out = ['| 年 | 固定样本 | 当年池 | 池外校数 | 池外分位均值 | σ | Gini |', '|---|---|---|---|---|---|---|']
    for r in R2:
        out.append(f"| {r['year']} | {r['n_fixed']} | {r['pool_n']} | {r['outside_n']} | "
                   f"{f(r['outside_pct_mean'], 4)} | {f(r['sigma'], 3)} | {f(r['gini'], 5)} |")
    return '\n'.join(out)


TABLES = {'sample': t_sample, 'pools': t_pools, 'main': t_main, 'time': t_time,
          'converge': t_converge, 'trend': t_trend, 'outside': t_outside}
if __name__ == '__main__':
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    for k, fn in TABLES.items():
        if which in ('all', k):
            print('\n===== %s =====' % k)
            print(fn())
