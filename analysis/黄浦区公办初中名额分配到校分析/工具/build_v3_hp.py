#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""产出黄浦分析的 7 个交付 CSV。计算全部在 hp_core.compute()。"""
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hp_core import (A, YEARS, BREAK_2024, dispersion, num, compute,  # noqa: E402
                     write,
                     ols_slope)

R = compute()
P5, P3, POOL_Y, WQ = R['P5'], R['P3'], R['POOL_Y'], R['WQ']
os.makedirs(A, exist_ok=True)
print('=== 池定义 ===')
for y in YEARS:
    print(f'  {y} 当年池 n={len(POOL_Y[y])}｜名额未用满组合 {R["UNP"][y]}')
print(f'  五年全勤 {len(P5)}｜三年 {len(P3)}｜仅三年 {R["HIST"]}')

# ---------- 1) 宽表（唯一事实源） ----------
per = ('wq', 'eq', 'P', 'P_eq', 'Z', 'rel', 'quota', 'n_pairs', 'hi', 'lo')
cols = (['junior_high_school', 'ownership', 'in_pool5', 'in_pool3', 'historic',
         'structural_break_2024', 'n_years']
        + [f'{v}_{y}' for y in YEARS for v in per]
        + ['quota_avg', 'P_wq', 'P_eq', 'Z_avg', 'ZR_avg', 'rel_avg', 'rel_first',
           'rel_last', 'delta_rel', 'SEN', 'sen_recent3', 'sen_ex2024', 'spearman',
           'sen_z', 'trend_class', 'rank_P_wq', 'rank_P_eq', 'rank_Z', 'rank_Z_wq_comb',
           'rank_P_lin', 'rank_P_exp', 'rank_P_recent3', 'shift_wq_eq']
        + [f'rank_P_{y}' for y in YEARS] + [f'rank_P_eq_{y}' for y in YEARS])
rows = []
for c in R['gov']:
    d = {'junior_high_school': c, 'ownership': '公办',
         'in_pool5': int(c in P5), 'in_pool3': int(c in P3),
         'historic': int(c in R['HIST']),
         'structural_break_2024': int(c in BREAK_2024),
         'n_years': sum(c in POOL_Y[y] for y in YEARS)}
    for y in YEARS:
        has = c in POOL_Y[y]
        d[f'wq_{y}'] = num(WQ.get((c, y)))
        d[f'eq_{y}'] = num(R['EQ'].get((c, y)))
        d[f'P_{y}'] = num(R['P'].get((c, y)))
        d[f'P_eq_{y}'] = num(R['PEQ'].get((c, y)))
        d[f'Z_{y}'] = num(R['Z'].get((c, y)))
        d[f'rel_{y}'] = num(R['REL'].get((c, y)), 3)
        d[f'quota_{y}'] = R['QUOTA'].get((c, y), '')
        d[f'n_pairs_{y}'] = R['NPAIR'].get((c, y), '')
        d[f'hi_{y}'] = num(R['HI'].get((c, y)), 1)
        d[f'lo_{y}'] = num(R['LO'].get((c, y)), 1)
        d[f'rank_P_{y}'] = R['RK_Y'][y].get(c, '') if has else ''
        d[f'rank_P_eq_{y}'] = R['RK_Y_EQ'][y].get(c, '') if has else ''
    if c in P5:
        d.update({
            'quota_avg': num(st.fmean([R['QUOTA'][(c, y)] for y in YEARS]), 1),
            'P_wq': num(R['P_wq'][c]), 'P_eq': num(R['P_eq'][c]),
            'Z_avg': num(st.fmean([R['Z'][(c, y)] for y in YEARS])),
            'ZR_avg': num(st.fmean([R['ZR'][(c, y)] for y in YEARS])),
            'rel_avg': num(st.fmean([R['REL'][(c, y)] for y in YEARS]), 3),
            'rel_first': num(R['REL'][(c, YEARS[0])], 3),
            'rel_last': num(R['REL'][(c, YEARS[-1])], 3),
            'delta_rel': num(R['REL'][(c, YEARS[-1])] - R['REL'][(c, YEARS[0])], 3),
            'SEN': num(R['SEN'][c], 4), 'sen_recent3': num(R['SEN_R3'][c], 4),
            'sen_ex2024': num(R['SEN_NO24'][c], 4), 'spearman': num(R['RHO'][c], 4),
            'sen_z': num(R['ZSEN'][c], 3), 'trend_class': R['CLS'][c],
            'rank_P_wq': R['RK_WQ'][c], 'rank_P_eq': R['RK_EQ'][c],
            'rank_Z': R['RK_Z'][c], 'rank_Z_wq_comb': R['RK_ZR'][c],
            'rank_P_lin': R['RK_VAR']['lin'][c], 'rank_P_exp': R['RK_VAR']['exp'][c],
            'rank_P_recent3': R['RK_VAR']['r3'][c],
            'shift_wq_eq': R['RK_WQ'][c] - R['RK_EQ'][c]})
    rows.append(d)
print('\n=== 交付物 ===')
write('宽表-初中水平-黄浦区-2022-2026.csv', cols, rows)

# ---------- 2) 排序表 ----------
c2 = (['junior_high_school', 'rank_P_wq', 'P_wq', 'P_eq', 'Z_avg', 'SEN', 'trend_class']
      + [f'P_{y}' for y in YEARS] + [f'rank_P_{y}' for y in YEARS]
      + [f'quota_{y}' for y in YEARS])
write('排序表-名额分配到校-黄浦区-2022-2026.csv', c2,
      [{**{k: d[k] for k in c2[:7]},
        **{f'P_{y}': d[f'P_{y}'] for y in YEARS},
        **{f'rank_P_{y}': d[f'rank_P_{y}'] for y in YEARS},
        **{f'quota_{y}': d[f'quota_{y}'] for y in YEARS}}
       for d in sorted([x for x in rows if x['in_pool5']],
                        key=lambda x: R['RK_WQ'][x['junior_high_school']])])

# ---------- 3) 多口径总表 ----------
c3 = ['junior_high_school', 'in_pool5', 'in_pool3', 'historic']
for y in YEARS:
    c3 += [f'P_{y}', f'rank_{y}']
c3 += ['P_wq', 'rank_wq', 'P_3y', 'rank_3y']
rows3 = []
for c in R['gov']:
    d = {'junior_high_school': c, 'in_pool5': int(c in P5), 'in_pool3': int(c in P3),
         'historic': int(c in R['HIST'])}
    for y in YEARS:
        d[f'P_{y}'] = num(R['P'].get((c, y)))
        d[f'rank_{y}'] = R['RK_Y'][y].get(c, '')
    d['P_wq'] = num(R['P_wq'].get(c))
    d['rank_wq'] = R['RK_WQ'].get(c, '')
    d['P_3y'] = num(R['agg'](c, R['P'], [1, 1, 1, 0, 0])) if c in P3 else ''
    d['rank_3y'] = R['RK_P3'].get(c, '')
    rows3.append(d)
write('rank-多口径总表-黄浦区-2022-2026.csv', c3, rows3)

# ---------- 4) 加权敏感性 ----------
c4 = ['junior_high_school', 'rank_wq', 'rank_lin', 'rank_exp', 'rank_r3',
      'P_wq', 'P_lin', 'P_exp', 'P_r3', 'shift_wq_eq', 'max_shift']
rows4 = []
for c in sorted(P5, key=lambda c: R['RK_WQ'][c]):
    sh = [abs(R['RK_VAR'][v][c] - R['RK_WQ'][c]) for v in ('lin', 'exp', 'r3')]
    rows4.append({'junior_high_school': c, 'rank_wq': R['RK_WQ'][c],
                  'rank_lin': R['RK_VAR']['lin'][c], 'rank_exp': R['RK_VAR']['exp'][c],
                  'rank_r3': R['RK_VAR']['r3'][c], 'P_wq': num(R['P_var']['wq'][c]),
                  'P_lin': num(R['P_var']['lin'][c]), 'P_exp': num(R['P_var']['exp'][c]),
                  'P_r3': num(R['P_var']['r3'][c]),
                  'shift_wq_eq': R['RK_WQ'][c] - R['RK_EQ'][c], 'max_shift': max(sh)})
write('rank-加权敏感性-黄浦区-2022-2026.csv', c4, rows4)

# ---------- 5) 趋势分析 ----------
c5 = (['junior_high_school', 'n_years', 'rel_first', 'rel_last', 'delta_rel', 'rel_avg',
       'SEN', 'sen_z', 'trend_class', 'sen_recent3', 'sen_ex2024', 'spearman',
       'structural_break_2024'] + [f'rel_{y}' for y in YEARS])
write('趋势分析-黄浦区-2022-2026.csv', c5,
      [{'junior_high_school': c, 'n_years': 5,
        'rel_first': num(R['REL'][(c, YEARS[0])], 3),
        'rel_last': num(R['REL'][(c, YEARS[-1])], 3),
        'delta_rel': num(R['REL'][(c, YEARS[-1])] - R['REL'][(c, YEARS[0])], 3),
        'rel_avg': num(st.fmean([R['REL'][(c, y)] for y in YEARS]), 3),
        'SEN': num(R['SEN'][c], 4), 'sen_z': num(R['ZSEN'][c], 3),
        'trend_class': R['CLS'][c], 'sen_recent3': num(R['SEN_R3'][c], 4),
        'sen_ex2024': num(R['SEN_NO24'][c], 4), 'spearman': num(R['RHO'][c], 4),
        'structural_break_2024': int(c in BREAK_2024),
        **{f'rel_{y}': num(R['REL'][(c, y)], 3) for y in YEARS}}
       for c in sorted(P5, key=lambda c: R['RK_WQ'][c])])

# ---------- 6) 收敛分析 ----------
rows6 = []
for y in YEARS:
    dy = dispersion([WQ[(x, y)] for x in POOL_Y[y]])
    df = dispersion([WQ[(x, y)] for x in P5 if x in POOL_Y[y]])
    wr = st.fmean([R['HI'][(x, y)] - R['LO'][(x, y)] for x in POOL_Y[y]
                   if R['HI'].get((x, y)) is not None])
    rows6.append({'year': y, **dy, **{f'{k}_f': v for k, v in df.items()},
                  'within_line_range': num(wr, 2)})
c6 = (['year', 'n', 'iqr', 'sd', 'cv', 'range', 'top_bottom', 'n_f', 'iqr_f', 'sd_f',
       'cv_f', 'range_f', 'top_bottom_f', 'within_line_range'])
write('收敛分析-黄浦区-2022-2026.csv', c6, rows6)
iq_y = [r['iqr'] for r in rows6]
iq_f = [r['iqr_f'] for r in rows6]
cv_y = [r['cv'] for r in rows6]
xs = [float(y) for y in YEARS]

print('\n=== 离散度双口径 ===')
print(f"  {'年':<6}{'n':>4}{'IQR':>7}{'σ':>7}{'CV':>8}{'极差':>7}{'头尾':>7}  |"
      f"{'n':>4}{'IQR':>7}{'σ':>7}{'CV':>8}  {'校内极差':>9}")
for r in rows6:
    print(f"  {r['year']:<6}{r['n']:>4}{r['iqr']:>7.1f}{r['sd']:>7.1f}{r['cv']:>8.4f}"
          f"{r['range']:>7.1f}{r['top_bottom']:>7.1f}  |{r['n_f']:>4}{r['iqr_f']:>7.1f}"
          f"{r['sd_f']:>7.1f}{r['cv_f']:>8.4f}  {r['within_line_range']:>9.1f}")
b_y, b_f = ols_slope(xs, iq_y), ols_slope(xs, iq_f)
print(f"  IQR 逐年斜率：当年池 b={b_y:+.3f}｜固定池 b={b_f:+.3f}")
print(f"  首尾：当年池 {iq_y[0]:.1f}→{iq_y[-1]:.1f}｜固定池 {iq_f[0]:.1f}→{iq_f[-1]:.1f}")
print(f"  同向判定：{'同向' if b_y*b_f > 0 else '不同向'}（判读规则要求同向才给方向结论）")

# ---------- 7) 单线视角 ----------
c7 = ['junior_high_school', 'senior_high_school', 'n_years', 'mean_score',
      'total_quota', 'first_year', 'last_year']
lines = sorted({k[2] for k in R['pairs']})
rows7 = []
for c in R['gov']:
    for l in lines:
        ys = [y for y in YEARS if (y, c, l) in R['pairs']]
        if not ys:
            continue
        rows7.append({'junior_high_school': c, 'senior_high_school': l,
                      'n_years': len(ys),
                      'mean_score': num(st.fmean([R['pairs'][(y, c, l)][0] for y in ys]), 2),
                      'total_quota': sum(R['pairs'][(y, c, l)][1] for y in ys),
                      'first_year': ys[0], 'last_year': ys[-1]})
write('单线视角-黄浦区-2022-2026.csv', c7, rows7)

print('\n=== 主口径排名 前 8（五年全勤 17 所）===')
print(f"  {'名':>3} {'初中':<24}{'P_wq':>8}{'rel均名':>8}{'名额':>7}{'SEN':>8}  趋势")
for c in sorted(P5, key=lambda c: R['RK_WQ'][c])[:8]:
    print(f"  {R['RK_WQ'][c]:>3} {c.replace('上海市','')[:22]:<24}"
          f"{R['P_wq'][c]:>8.3f}{st.fmean([R['REL'][(c,y)] for y in YEARS]):>8.2f}"
          f"{st.fmean([R['QUOTA'][(c,y)] for y in YEARS]):>7.1f}"
          f"{R['SEN'][c]:>8.2f}  {R['CLS'][c]}")
print('\n=== 趋势分类统计 ===')
for k in ('明显上升', '平稳', '明显下降'):
    print(f'  {k}: {sum(1 for c in P5 if R["CLS"][c] == k)} 所 '
          f'{[c.replace("上海市","")[:8] for c in P5 if R["CLS"][c]==k]}')
