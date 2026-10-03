# -*- coding: utf-8 -*-
"""嘉定宽表扩容 2.4 独立复算（宽表为单一事实源，但宽表本身逐格回源）。"""
import csv
import io
import os
import re
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))
D_S = f'{ROOT}/data/嘉定区/学校'
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = [2022, 2023, 2024, 2025, 2026]
HS = [('交大嘉定', '142002'), ('上师嘉新', '142004'), ('嘉定一中', '142001'),
      ('上海中学', '042032'), ('交大本部', '102056'), ('复旦附中', '102057'),
      ('华师大二附', '152003'), ('上师大附中', '152006')]
QU3 = ['142001', '142002', '142004']
PASS, FAIL, FAILMSGS = 0, 0, []


def load(p, d=None):
    with open(f'{d or D_S}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def ck(name, got, exp, tol=None):
    global PASS, FAIL
    ok = (abs(got - exp) <= tol) if (tol is not None and isinstance(got, (int, float))
                                     and isinstance(exp, (int, float))) else (got == exp)
    if ok:
        PASS += 1
        print(f'  [OK] {name}: {got}')
    else:
        FAIL += 1
        FAILMSGS.append(f'{name}: 重算={got} 期望={exp}')
        print(f'  [!!] {name}: 重算={got} 期望={exp}')


score = load('名额到校最低分数线-嘉定区-2022-2026.csv')
plan = (load('名额到校计划-嘉定区-2023-2026.csv')
        + load('名额到校计划-嘉定区-2022-图片转录.csv'))
S, Q = {}, {}
for r in score:
    if r['min_score']:
        S[(r['junior_high_school'], r['senior_high_school_code'],
           int(r['year']))] = float(r['min_score'])
for r in plan:
    Q[(r['junior_high_school'], r['senior_high_school_code'],
       int(r['year']))] = int(r['quota'])
W = {r['junior_high_school']: r for r in load('宽表-初中水平-嘉定区-2022-2026.csv', D_A)}
schools = sorted(W)
SHORT = lambda n: n.replace('上海市嘉定区', '').replace('上海市', '')


def wq_mean(c, y):
    """名额加权均分（独立实现，仅取当年有分数的区属线）。"""
    pr = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in QU3 if (c, h, y) in S]
    if not pr or sum(q for _, q in pr) <= 0:
        return None
    return sum(v * q for v, q in pr) / sum(q for _, q in pr)


# ---------- [10] 宽表 ↔ 原始 CSV 逐格回源 ----------
print('\n' + '=' * 68)
print('[10] 宽表 ↔ 原始 CSV 逐格回源（8 线 × 5 年 × 分数/名额）')
print('=' * 68)
ns_ok = ns_bad = nq_ok = nq_bad = 0
bad = []
for c in schools:
    for short, code in HS:
        for y in YEARS:
            gv, ev = W[c][f'score_{short}_{y}'], S.get((c, code, y))
            if (gv == '' and ev is None) or (gv != '' and ev is not None
                                             and abs(float(gv) - ev) < 1e-9):
                ns_ok += 1
            else:
                ns_bad += 1
                bad.append(('score', c, short, y, gv, ev))
            gq, eq = W[c][f'quota_{short}_{y}'], Q.get((c, code, y))
            if (gq == '' and eq is None) or (gq != '' and eq is not None and int(gq) == eq):
                nq_ok += 1
            else:
                nq_bad += 1
                bad.append(('quota', c, short, y, gq, eq))
NCELL = len(schools) * len(HS) * len(YEARS)
ck('宽表铺满格数 = 43x8x5', NCELL, 1720, tol=0)
ck('分数线格全部一致', ns_ok, NCELL, tol=0)
ck('分数线格不一致', ns_bad, 0, tol=0)
ck('名额格全部一致', nq_ok, NCELL, tol=0)
ck('名额格不一致', nq_bad, 0, tol=0)
ck('非空分数线格 = 原始分数线格数',
   sum(1 for c in schools for sh, _ in HS for y in YEARS if W[c][f'score_{sh}_{y}'] != ''),
   len(S), tol=0)
ck('非空名额格 = 原始名额格数',
   sum(1 for c in schools for sh, _ in HS for y in YEARS if W[c][f'quota_{sh}_{y}'] != ''),
   len(Q), tol=0)
for b in bad[:8]:
    print('     不一致:', b)
ck('宽表列数', len(W[schools[0]]), 191, tol=0)
ck('宽表行数', len(W), 43, tol=0)
ck('逐线分数列数',
   len([k for k in W[schools[0]] if re.match(r'^score_[^_]+_\d{4}$', k)]), 40, tol=0)
ck('逐线名额列数',
   len([k for k in W[schools[0]] if re.match(r'^quota_[^_]+_\d{4}$', k)]), 40, tol=0)

# ---------- [11] 宽表内部自洽 ----------
print('\n' + '=' * 68)
print('[11] 宽表内部自洽')
print('=' * 68)
e1 = e2 = e3 = e4 = 0
for c in schools:
    r = W[c]
    for y in YEARS:
        if r[f'quota3_{y}'] == '':
            continue
        if int(r[f'quota3_{y}']) != sum(int(r[f'quota_{s}_{y}'] or 0)
                                        for s, cd in HS if cd in QU3):
            e1 += 1
        vp = sum(1 for s, cd in HS if cd in QU3 and r[f'score_{s}_{y}'] != '')
        if int(r[f'valid_pairs_{y}']) != vp:
            e2 += 1
    ys5 = [y for y in YEARS if r[f'P_wq_{y}'] != '']
    if ys5 and abs(float(r['P_wq'])
                   - st.fmean(float(r[f'P_wq_{y}']) for y in ys5)) > 1e-5:
        e3 += 1
    if r['ranked'] == '1' and r['rank_P_wq'] != '' and float(r['P_wq']) != float(r['P_wq_all']):
        e4 += 1
ck('quota3_y ≠ 三条区属线之和', e1, 0, tol=0)
ck('valid_pairs_y ≠ 有分数的区属线数', e2, 0, tol=0)
ck('P_wq ≠ 逐年 P_wq 均值', e3, 0, tol=0)
ck('P_wq ≠ P_wq_all', e4, 0, tol=0)
tb = [c for c in schools if W[c]['ranked'] == '1']
ck('入榜样本数', len(tb), 28, tol=0)
ck('五年全勤数', len([c for c in schools if W[c]['years_included'] == '5']), 25, tol=0)
ck('民办学校数', len([c for c in schools if W[c]['ownership'] == '民办']), 7, tol=0)
ck('rank_P_wq 为 1..28 连续无重',
   sorted(int(W[c]['rank_P_wq']) for c in tb) == list(range(1, 29)), True)

# ---------- [12] 独立重算主排名与 SEN ----------
print('\n' + '=' * 68)
print('[12] 从原始 CSV 独立重算 P_wq / rank_P_wq / SEN')
print('=' * 68)
py = {}
for y in YEARS:
    per = {c: wq_mean(c, y) for c in schools}
    per = {c: v for c, v in per.items() if v is not None}
    xs = sorted(per.values())
    for c, v in per.items():
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        py.setdefault(c, []).append(1 - ((b + (e + 1) / 2) - 1) / (len(xs) - 1))
P5 = {c: st.fmean(v) for c, v in py.items() if len(v) == 5}
P4 = {c: st.fmean(v) for c, v in py.items() if len(v) == 4}
P = {**P5, **P4}
order = sorted(P, key=lambda c: -P[c])
RK = {c: i for i, c in enumerate(order, 1)}
ck('P_wq 最大偏差', round(max(abs(P[c] - float(W[c]['P_wq'])) for c in order), 6),
   0.0, tol=1e-5)
ck('入榜域 = 5 年全勤 25 + 恰好 4 年 3', len(order), 28, tol=0)
ck('rank_P_wq 不一致学校数', [c for c in order if RK[c] != int(W[c]['rank_P_wq'])], [])
med = {}
for y in YEARS:
    vals = sorted(v for c in schools if (v := wq_mean(c, y)) is not None)
    med[y] = st.median(vals)
ck('逐年池量 27/28/35/38/39',
   [len([c for c in schools if wq_mean(c, y) is not None]) for y in YEARS],
   [27, 28, 35, 38, 39])
smax = 0.0
for c in schools:
    if W[c]['SEN'] == '':
        continue
    pts = [(i, wq_mean(c, y) - med[y]) for i, y in enumerate(YEARS)
           if wq_mean(c, y) is not None]
    if len(pts) < 3:
        continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx, my = st.fmean(xs), st.fmean(ys)
    slope = sum((xs[i] - mx) * (ys[i] - my)
                for i in range(len(xs))) / sum((i - mx) ** 2 for i in xs)
    smax = max(smax, abs(slope - float(W[c]['SEN'])))
ck('SEN 最大偏差（独立 OLS vs 宽表）', round(smax, 5), 0.0, tol=1e-3)
ck('SEN 未被再次低估（同济二附中）', round(float(W['同济大学附属实验中学']['SEN']), 2),
   -3.17, tol=0.01)
ck('SEN 单位为「分/年」（华亭学校 ≈ -7.92）',
   round(float(W['上海市嘉定区华亭学校']['SEN']), 2), -7.92, tol=0.01)

# ---------- [13] 交付物完整性 ----------
print('\n' + '=' * 68)
print('[13] 交付物完整性')
print('=' * 68)
FILES = [('宽表-初中水平-嘉定区-2022-2026.csv', 43, 191),
         ('趋势分析-嘉定区-2022-2026.csv', 25, None),
         ('rank-标准化-嘉定区-2022-2026.csv', 43, None),
         ('rank-多口径总表-嘉定区-2022-2026.csv', 28, None),
         ('rank-加权敏感性-嘉定区-2022-2026.csv', 28, None),
         ('单线视角-嘉定区-2022-2026.csv', 178, None)]
for fn, nrow, ncol in FILES:
    if not os.path.exists(f'{D_A}/{fn}'):
        ck(f'{fn} 存在', False, True)
        continue
    rows = load(fn, D_A)
    ck(f'{fn} 行数', len(rows), nrow, tol=0)
    if ncol:
        ck(f'{fn} 列数', len(rows[0]), ncol, tol=0)
sl = load('单线视角-嘉定区-2022-2026.csv', D_A)
ck('单线视角覆盖 8 条线', len({r['senior_high_school_code'] for r in sl}), 8, tol=0)
WEI = {'042032', '102056', '102057', '152003', '152006'}
ck('委属线每格名额均为 1（校 x 线 x 年逐格）',
   sorted({q for (c, cd, y), q in Q.items() if cd in WEI}), [1])
ck('委属线观测格数', len([1 for (c, cd, y) in S if cd in WEI]), 55, tol=0)
mt = load('rank-多口径总表-嘉定区-2022-2026.csv', D_A)
ck('多口径总表 comb 名次 1..28 连续',
   sorted(int(r['rank_P_wq_comb']) for r in mt) == list(range(1, 29)), True)
tr = load('趋势分析-嘉定区-2022-2026.csv', D_A)
ck('趋势分析含两式收敛回归列',
   all(f'convB_r2_{y}' in tr[0] for y in YEARS[1:]) and 'convA_r2' not in tr[0]
   and 'convA_resid_z' in tr[0], True)

# ---------- [14] 报告主表 ↔ 宽表 ----------
print('\n' + '=' * 68)
print('[14] 报告主表 ↔ 宽表逐格一致')
print('=' * 68)
rep = io.open(f'{D_A}/分析报告.md', encoding='utf-8').read()
n_main, dev = 0, []
for line in rep.split('\n'):
    if not line.startswith('| ') or line.count('|') < 11:
        continue
    cells = [x.strip() for x in line.strip('|').split('|')]
    if not cells[0].isdigit():
        continue
    m = [k for k in W if SHORT(k) == cells[1]]
    if not m:
        continue
    r = W[m[0]]
    n_main += 1
    for col, idx, nd in (('P_wq', 2, 3), ('rel_avg', 3, 2),
                         ('quota3_avg', 4, 1), ('SEN', 5, 3)):
        gv = cells[idx].replace('−', '-').replace('+', '')
        if abs(float(gv) - float(r[col])) > 1.0 * 10 ** (-nd) + 1e-9:
            dev.append((cells[1], col, gv, r[col]))
    for col, idx in (('rank_P_eq', 6), ('rank_Z_wq', 7), ('rank_P_lin', 8),
                     ('rank_P_exp', 9), ('rank_P_recent3', 10)):
        if cells[idx] != r[col]:
            dev.append((cells[1], col, cells[idx], r[col]))
ck('报告主表行数 = 入榜数', n_main, 28, tol=0)
ck('报告主表 ↔ 宽表不一致格数', dev, [])

# ---------- [15] 报告独立性与事实断言 ----------
print('\n' + '=' * 68)
print('[15] 报告独立性 + 事实断言')
print('=' * 68)
BAN = ['普陀', '徐汇', '黄浦', '浦东', '闵行', '静安', '长宁', '杨浦', '虹口',
       '其他区', '异地']
ck('报告中跨区引用', [(k, rep.count(k)) for k in BAN if k in rep], [])
ck('含交付物清单', '交付物（6 个 CSV' in rep, True)
ck('142004 事实已更正', '2025 年首次出现' in rep and '2024 起有分数线' not in rep, True)
ck('扩容年表述已更正',
   '仅 2025 一次扩容' in rep and '2024、2025 为口径扩容年' not in rep, True)
ck('含 SEN 口径说明', '最小二乘回归' in rep, True)
ck('含 3 处错误修订记录', 'B.2 2026-10-03 修订' in rep, True)
ck('142004 在 2022–2024 确无原始数据',
   [len([1 for (c, cd, y) in S if cd == '142004' and y == yy]) for yy in (2022, 2023, 2024)],
   [0, 0, 0])

print('\n' + '=' * 68)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
if FAILMSGS:
    print('不通过明细:')
    for m in FAILMSGS:
        print('  -', m)
else:
    print('全部通过')
