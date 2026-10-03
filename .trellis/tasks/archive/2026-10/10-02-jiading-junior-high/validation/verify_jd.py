# -*- coding: utf-8 -*-
"""2.4 独立复算：嘉定区名额到校分析（不 import 2.3 脚本，名次与 Spearman 独立实现）。"""
import csv
import os
import re
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))))
D = f'{ROOT}/data/嘉定区/学校'
A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = [2022, 2023, 2024, 2025, 2026]
QLINE = ['142001', '142002', '142004']
fails = []
n = 0


def ck(name, got, exp, tol=0.005):
    global n
    n += 1
    ok = abs(got - exp) <= tol if isinstance(exp, (int, float)) else got == exp
    if not ok:
        fails.append(f'{name}: 重算={got} 报告={exp}')
    print(f'  [{"OK" if ok else "FAIL"}] {name}: 重算={got} 报告={exp}')


def load(p, d=D):
    with open(f'{d}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


score = load('名额到校最低分数线-嘉定区-2022-2026.csv')
plan = load('名额到校计划-嘉定区-2023-2026.csv') + load('名额到校计划-嘉定区-2022-图片转录.csv')
rk = {r['junior_high_school']: r for r in load('rank-标准化-嘉定区-2022-2026.csv', A)}
S = {(r['junior_high_school'], r['senior_high_school_code'], int(r['year'])): float(r['min_score'])
     for r in score if r['senior_high_school_code'] in QLINE}
Q = {(r['junior_high_school'], r['senior_high_school_code'], int(r['year'])): int(r['quota'])
     for r in plan if r['senior_high_school_code'] in QLINE}
schools = sorted({k[0] for k in S} | {k[0] for k in Q})


def sp(x, y):
    def avg(a):
        s = sorted(a)
        return [sum(1 for t in s if t < v) + (sum(1 for t in s if t == v) + 1) / 2 for v in a]
    ra, rb = avg(x), avg(y)
    ma, mb = st.fmean(ra), st.fmean(rb)
    num = sum((p - ma) * (q - mb) for p, q in zip(ra, rb))
    den = (sum((p - ma) ** 2 for p in ra) * sum((q - mb) ** 2 for q in rb)) ** 0.5
    return num / den


per = {}
for y in YEARS:
    lines_y = [c for c in QLINE if any((s, c, y) in Q for s in schools)]
    sch = {}
    for s in schools:
        num = den = 0.0
        nl = 0
        for c in lines_y:
            v, q = S.get((s, c, y)), Q.get((s, c, y), 0)
            if v is not None:
                num += v * q
                den += q
                nl += 1
        if den:
            sch[s] = (num / den, nl)
    med = st.median([v for v, _ in sch.values()])
    items = sorted([(v, k) for k, (v, _) in sch.items()], key=lambda t: -t[0])
    rank = {}
    i = 0
    while i < len(items):
        j = i
        while j + 1 < len(items) and items[j + 1][0] == items[i][0]:
            j += 1
        pos = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            rank[items[k][1]] = pos
        i = j + 1
    for s, (v, nl) in sch.items():
        per[(s, y)] = {'wq': v, 'lines': nl, 'rel': v - med, 'rank': rank[s],
                        'P': 1 - (rank[s] - 1) / (len(items) - 1)}

print('=== [1] 排名主表（名额加权 P）===')
core = [s for s in schools if len([y for y in YEARS if (s, y) in per]) >= 4]
P5 = {s: st.fmean([per[(s, y)]['P'] for y in YEARS if (s, y) in per]) for s in core}
R5 = {s: st.fmean([per[(s, y)]['rel'] for y in YEARS if (s, y) in per]) for s in core}
Q5 = {s: st.fmean([sum(Q.get((s, c, y), 0) for c in QLINE) for y in YEARS if (s, y) in per])
      for s in core}
for i, s in enumerate(sorted(core, key=lambda s: -P5[s])[:5], 1):
    ck(f'第 {i} 名名次', i, int(rk[s]['rank_P_wq']))
    ck(f'  {s[:12]} P', round(P5[s], 3), round(float(rk[s]['P_wq']), 3), tol=0.0015)
ck('入榜样本 n≥4', len(core), 28, tol=0)
ck('末位名次', max(int(rk[s]['rank_P_wq']) for s in core), 28, tol=0)

print('\n=== [2] 逐年离散度 ===')
for y, (sg, iqr) in zip(YEARS, [(10.08, 13.8), (8.81, 15.0), (8.87, 11.9), (10.94, 12.3), (8.79, 10.9)]):
    v = sorted(per[(s, y)]['wq'] for s in schools if (s, y) in per)
    m = len(v)
    ck(f'{y} σ', round(st.pstdev(v), 2), sg, tol=0.01)
    ck(f'{y} IQR', round(v[(3 * m) // 4] - v[m // 4], 1), iqr, tol=0.05)

print('\n=== [3] 收敛回归 rel2022 → rel_y ===')
full = [s for s in schools if len([y for y in YEARS if (s, y) in per]) == 5]
for y, (b_e, r_e) in zip(YEARS[1:], [(0.232, 0.086), (0.144, 0.029), (0.282, 0.061), (0.081, 0.008)]):
    xs = [per[(s, 2022)]['rel'] for s in full]
    ys = [per[(s, y)]['rel'] for s in full]
    mx, my = st.fmean(xs), st.fmean(ys)
    b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    a0 = my - b * mx
    sse = sum((c - (a0 + b * a)) ** 2 for a, c in zip(xs, ys))
    sst = sum((c - my) ** 2 for c in ys)
    ck(f'{y} b', round(b, 3), b_e, tol=0.002)
    ck(f'{y} R²', round(1 - sse / sst, 3), r_e, tol=0.002)

print('\n=== [4] 名额与位次（两层检验）===')
qs = [Q5[s] for s in core]
ck('ρ(名额, P)', round(sp(qs, [P5[s] for s in core]), 3), 0.509, tol=0.002)
ck('ρ(名额, rel均名)', round(sp(qs, [R5[s] for s in core]), 3), 0.578, tol=0.002)
A_, B_ = [], []
for y in YEARS:
    for c in [x for x in QLINE if any((s, x, y) in Q for s in schools)]:
        vals = {s: S[(s, c, y)] for s in schools if (s, c, y) in S}
        for s, v in vals.items():
            if Q.get((s, c, y), 0) > 0:
                A_.append(Q[(s, c, y)])
                B_.append(sum(1 for w in vals.values() if w > v)
                          + (sum(1 for w in vals.values() if w == v) + 1) / 2)
ck('同线内 n', len(A_), 411, tol=0)
ck('同线内 ρ', round(sp(A_, B_), 3), -0.211, tol=0.002)

print('\n=== [5] 名额占比极差（切点深度前提）===')
for c, exp in (('142001', 0.333), ('142002', 0.333), ('142004', 0.250)):
    worst = 0.0
    for y in YEARS:
        base = {s: sum(Q.get((s, x, y), 0) for x in QLINE) for s in schools}
        v = [Q.get((s, c, y), 0) / base[s] for s in base
             if base[s] > 0 and Q.get((s, c, y), 0) > 0]
        if len(v) >= 5:
            worst = max(worst, max(v) - min(v))
    ck(f'{c} 占比极差最大值', round(worst, 3), exp, tol=0.002)

print('\n=== [6] 头/尾分组（2025–2026）===')
NAME = {'142001': '嘉定一中', '142002': '交大附中嘉定分校', '142004': '上师大附中嘉定新城'}
for y, head_e, tail_e in ((2025, '142002', '142001'), (2026, '142002', '142001')):
    d = {}
    for c in QLINE:
        v = [S[(s, c, y)] for s in schools if (s, c, y) in S]
        if v:
            d[c] = st.fmean(v)
    o = sorted(d, key=lambda c: -d[c])
    ck(f'{y} 头线', NAME[o[0]], NAME[head_e])
    ck(f'{y} 尾线', NAME[o[-1]], NAME[tail_e])

print('\n=== [7] 区属线扩容与委属线覆盖 ===')
for y, k in zip(YEARS, [2, 2, 2, 3, 3]):
    ck(f'{y} 区属线数', len({c for c in QLINE if any((s, c, y) in Q for s in schools)}), k, tol=0)
sc_all = load('名额到校最低分数线-嘉定区-2022-2026.csv')
for c, nm, exp in (('042032', '上海中学', 12), ('102056', '交大附中本部', 13),
                   ('102057', '复旦附中', 11), ('152003', '华师大二附中', 14),
                   ('152006', '上师大附中', 5)):
    tot = sum(1 for r in sc_all if r['senior_high_school_code'] == c)
    ck(f'委属 {nm} 5 年所次', tot, exp, tol=0)
ck('区属名额合计 2026', sum(Q.get((s, c, 2026), 0) for s in schools for c in QLINE), 599, tol=0)

print('\n=== [8] 报告表格与 CSV 一致性（抽样 12 处）===')
rep = open(f'{A}/分析报告.md', encoding='utf-8').read()
tbl = dict()
for line in rep.split('\n'):
    m = re.match(r'\| (\d+) \| ([^|]+?) \| ([\d.]+) \| ([+-][\d.]+) \| ([\d.]+) \|', line)
    if m:
        tbl[int(m.group(1))] = (m.group(2).strip(), float(m.group(3)), float(m.group(4)), float(m.group(5)))
ck('报告主表行数', len(tbl), 28, tol=0)
for i in (1, 2, 3, 4, 5, 8, 10, 14, 20, 28):
    nm, p, rel, q = tbl[i]
    s = next(k for k in rk if k.replace('上海市嘉定区', '').replace('上海市', '') == nm)
    ck(f'  第{i}行 P', p, round(float(rk[s]['P_wq']), 3), tol=0.0015)
    ck(f'  第{i}行 名额', q, float(rk[s]['quota_avg']), tol=0.06)


print('\n=== [9] 报告独立性：不得含跨区对照 ===')
BAN = ['普陀', '徐汇', '黄浦', '浦东', '闵行', '静安', '长宁', '杨浦', '虹口', '其他区', '异地']
rep_txt = open(f'{A}/分析报告.md', encoding='utf-8').read()
bad = [(k, rep_txt.count(k)) for k in BAN if k in rep_txt]
ck('报告中跨区引用', bad, [])
ck('报告行数', rep_txt.count('\n') + 1, 379, tol=0)
ck('委属线排除理由已本地化', '100% 是「1 个名额」' in rep_txt and '−0.060' in rep_txt, True)
ck('含第 6 章「证据强度/反向证据/替代解释」', '## 6 结论的证据强度、反向证据与替代解释' in rep_txt, True)
ck('含不可回答问题清单', '不可由本报告回答的问题' in rep_txt, True)

print('\n' + '=' * 60)
print(f'总计 {n} 项检查，不通过 {len(fails)} 项')
for f in fails:
    print('  FAIL:', f)
if not fails:
    print('全部通过')
