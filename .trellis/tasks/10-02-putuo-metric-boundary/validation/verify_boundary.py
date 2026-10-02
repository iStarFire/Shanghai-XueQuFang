# -*- coding: utf-8 -*-
"""2.4 独立复算：本轮新增/修正的数值（3.3 切点深度、3.4 覆盖边界与并列、局限声明第 9 条）。

原则：从 `data/普陀区/学校/` 的原始分数线与计划表重建，不引用 2.3 的加工脚本；
交付表（宽表）只作为比对对象，不作为计算来源。
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
D_S = f'{ROOT}/data/普陀区/学校'
D_A = f'{ROOT}/analysis/普陀区公办初中名额分配到校分析'
YEARS = [2022, 2023, 2024, 2025, 2026]
ML = '上海市梅陇中学'
SH = {'华二普陀': '华东师范大学第二附属中学（普陀校区）', '二中': '上海市曹杨第二中学',
      '晋元': '上海市晋元高级中学', '宜川': '上海市宜川中学'}
Q4 = [SH['华二普陀'], SH['二中'], SH['晋元'], SH['宜川']]

fails = []
checks = 0


def ck(name, got, exp, tol=0.05):
    global checks
    checks += 1
    ok = (abs(got - exp) <= tol) if isinstance(exp, (int, float)) and isinstance(
        got, (int, float)) else (got == exp)
    if not ok:
        fails.append(f'{name}: 重算={got} 报告={exp}')
    print(f'  [{"OK" if ok else "FAIL"}] {name}: 重算={got} 报告={exp}')


def load(p, d=D_S):
    with open(f'{d}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


raw = load('名额到校最低分数线-普陀区-2022-2026.csv')
plan = load('名额到校计划-普陀区-2022-2026.csv')
S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): float(r['min_score'])
     for r in raw if r['min_score']}
Q = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): int(r['quota'])
     for r in plan}
W = {r['junior_high_school']: r for r in load('宽表-初中水平-普陀区-2022-2026.csv', D_A)}
core = [c for c in W if W[c]['years_included'] == '5']

print('=' * 72)
print('[1] 3.3 切点深度：梅陇 4 线名额占其名额批次的比例')
print('=' * 72)
tot4 = st.fmean([sum(Q.get((ML, h, y), 0) for h in Q4) for y in YEARS])
ck('梅陇 4 线名额合计年均', round(tot4, 1), 62.4)
for k, h in SH.items():
    q = st.fmean([Q.get((ML, h, y), 0) for y in YEARS])
    ck(f'{k} 年均名额', round(q, 1), {'华二普陀': 7.0, '二中': 18.2, '晋元': 18.6, '宜川': 18.6}[k])
    ck(f'{k} 占名额批次', round(q / tot4, 3), {'华二普陀': 0.112, '二中': 0.292,
                                             '晋元': 0.298, '宜川': 0.298}[k], tol=0.001)

print()
print('=' * 72)
print('[2] 3.3 名额占比的校际离散（31 所五年全勤）')
print('=' * 72)
size = {c: st.fmean([sum(Q.get((c, h, y), 0) for h in Q4) for y in YEARS]) for c in core}
rep = {'宜川': (0.227, 0.299, 0.333), '晋元': (0.227, 0.291, 0.326),
       '二中': (0.214, 0.291, 0.318), '华二普陀': (0.079, 0.115, 0.250)}
for k, (lo, md, hi) in rep.items():
    v = sorted(st.fmean([Q.get((c, SH[k], y), 0) for y in YEARS]) / size[c] for c in core)
    ck(f'{k} 占比最小', round(v[0], 3), lo, tol=0.001)
    ck(f'{k} 占比中位', round(st.median(v), 3), md, tol=0.001)
    ck(f'{k} 占比最大', round(v[-1], 3), hi, tol=0.001)

print()
print('=' * 72)
print('[3] 3.4 覆盖缺口：区内名额合计与切点深度换算')
print('=' * 72)
tot = {y: sum(Q.get((c, h, y), 0) for c in {k[0] for k in Q} for h in Q4) for y in YEARS}
ck('区内 4 线名额 5 年合计', sum(tot.values()), 3273, tol=0)
print(f'     逐年: {tot}  → 区间 {min(tot.values())}–{max(tot.values())}')
ck('切点·华二普陀（按批次 11.2% × 17%）', round(0.112 * 17, 1), 1.9, tol=0.05)
ck('切点·其余三线（按批次 29.8% × 17%）', round(0.298 * 17, 1), 5.1, tol=0.05)
print('     注：17% 为估算覆盖率（仓库无普陀考生数），报告已标注为估算值')

print()
print('=' * 72)
print('[4] 3.4 实质并列：全身口径 P_wq')
print('=' * 72)
schools = sorted({k[0] for k in S})
per_year = {}
for y in YEARS:
    per = {}
    for c in schools:
        num = den = 0.0
        for h in Q4:
            q = Q.get((c, h, y), 0)
            v = S.get((c, h, y))
            if q and v:
                num += q * v
                den += q
        if den:
            per[c] = num / den
    xs = list(per.values())
    for c, v in per.items():
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        per_year.setdefault(c, []).append(1 - ((b + (e + 1) / 2) - 1) / (len(xs) - 1))
P = {c: st.fmean(v) for c, v in per_year.items() if len(v) == 5}
ck('真北 全身 P', round(P['上海市真北中学'], 4), 0.7116, tol=0.0001)
ck('梅陇 全身 P', round(P[ML], 4), 0.7102, tol=0.0001)
ck('华师大附属外国语 全身 P', round(P['上海市华东师范大学附属外国语实验学校']
   if '上海市华东师范大学附属外国语实验学校' in P else
   P['华东师范大学附属外国语实验学校'], 4), 0.7100, tol=0.0001)
three = [P['上海市真北中学'], P[ML], P['华东师范大学附属外国语实验学校']]
ck('三者极差', round(max(three) - min(three), 4), 0.0015, tol=0.0001)

print()
print('=' * 72)
print('[5] 局限声明第 9 条：未按 years_included 过滤的排名陷阱')
print('=' * 72)
allr = [c for c in W if W[c]['P_wq_comb'] not in ('', None)]
o_all = sorted(allr, key=lambda c: -float(W[c]['P_wq_comb']))
o_core = sorted(core, key=lambda c: -float(W[c]['P_wq_comb']))
r_all = [i for i, c in enumerate(o_all, 1) if c == ML][0]
r_core = [i for i, c in enumerate(o_core, 1) if c == ML][0]
ck('未过滤时梅陇名次', r_all, 7)
ck('过滤后（31 所五年全勤）梅陇名次', r_core, 6)
xh = [(i, c) for i, c in enumerate(o_all, 1)
      if W[c]['years_included'] != '5' and i < r_all]
print(f'     未过滤时排在梅陇之前的低年数学校: {[(i, c.replace("上海市", ""), W[c]["years_included"]) for i, c in xh]}')
ck('民办新黄浦（3 年）综合 P', round(float(W['上海市民办新黄浦实验学校']['P_wq_comb']), 4), 0.7796, tol=0.0001)
ck('民办新黄浦未过滤名次', [i for i, c in enumerate(o_all, 1)
                     if c == '上海市民办新黄浦实验学校'][0], 3)
ck('宽表总行数', len(W), 44, tol=0)
ck('P_wq_comb 非空行数', len(allr), 44, tol=0)

print()
print('=' * 72)
print('[6] 综合口径前 6（与核心结论 A 组一致）')
print('=' * 72)
for c, exp in [('上海市晋元高级中学附属学校', 0.8270), ('上海市江宁学校', 0.7949),
               ('上海市曹杨第二中学附属学校', 0.7653), ('上海市中远实验学校', 0.7509),
               ('上海市真北中学', 0.7260), (ML, 0.7193)]:
    ck(f'{c.replace("上海市", "")} P_wq_comb', round(float(W[c]['P_wq_comb']), 4), exp, tol=0.0001)

print()
print('=' * 72)
print(f'总计 {checks} 项检查，不通过 {len(fails)} 项')
if fails:
    for f in fails:
        print('  FAIL:', f)
else:
    print('全部通过')
