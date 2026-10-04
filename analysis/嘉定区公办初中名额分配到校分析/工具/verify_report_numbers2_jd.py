# -*- coding: utf-8 -*-
"""第二层扫描：核对报告**正文与各章表格**里的关键统计量是否与 CSV 实际值一致。

第一层（verify_report_numbers_jd.py）只覆盖主表与头部指标行。本脚本补齐：
  A. 核心结论里的极差 / Spearman / 池子数 / 检验统计量
  B. 2.1 敏感性表、2.2 近三年表、4.2–4.3 收敛表、5.2 趋势分类表、5.4 对照表
  C. 第 8 章个案里的加权均分与 SEN
  D. 逐年表里的 mean_score

凡是「表格里出现的数字」与「CSV 算出来的数字」不符，即为旧口径残留。
"""
import csv
import os
import re
import statistics as st

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = f'{D}/分析报告.md'
YS = ['2022', '2023', '2024', '2025', '2026']


def load(n):
    return list(csv.DictReader(open(f'{D}/{n}', encoding='utf-8-sig')))


W = {r['junior_high_school']: r for r in load('宽表-初中水平-嘉定区-2022-2026.csv')}
M = {r['junior_high_school']: r for r in load('rank-多口径总表-嘉定区-2022-2026.csv')}
S = {r['junior_high_school']: r for r in load('趋势分类-嘉定区-2022-2026.csv')}
IND = {r['year']: r for r in load('收敛指标-嘉定区-2022-2026.csv')}
TRD = {r['metric']: r for r in load('收敛趋势检验-嘉定区-2022-2026.csv')}
rep = open(REP, encoding='utf-8').read()
lines = rep.split('\n')
RK = [r for r in M.values() if r['row_type'] == 'ranked']
bad, checked = [], 0


def sp(a, b):
    def rk(a):
        # 平均秩（标准 Spearman 的并列处理）——必须与 build_v3_jd.py:252 一致。
        # 2026-10-04 修正：此前用顺序秩，与标准实现不一致，导致同线内 rho 被低估约 0.03。
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    ra, rb = rk(a), rk(b)
    ma, mb = st.fmean(ra), st.fmean(rb)
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / den


def short(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


def sec(pat):
    """取包含标题 pat 的整节文本"""
    m = re.search(pat, rep)
    if not m:
        return ''
    nxt = re.search(r'\n#{2,3} ', rep[m.end():])
    return rep[m.start(): m.end() + (nxt.start() if nxt else len(rep))]


def has(txt, s):
    global checked
    checked += 1
    return s in txt


print('=== A. 核心结论关键统计量 ===')
rows = sorted(RK, key=lambda r: int(r['rank_P_wq_all']))
core = sec(r'\*\*A\. 排名')
sp_r2 = abs(float(rows[0]['P_wq_all']) - float(rows[1]['P_wq_all']))
sp_r35 = abs(float(rows[4]['P_wq_all']) - float(rows[2]['P_wq_all']))
for label, val in (('第1–2名极差', f'{sp_r2:.3f}'), ('第3–5名极差', f'{sp_r35:.3f}')):
    checked += 1
    if val not in core:
        bad.append(('核心结论A', label, f'报告未含 {val}'))
eq = sp([int(r['rank_P_wq_all']) for r in rows], [int(r['rank_P_eq_all']) for r in rows])
z = sp([int(r['rank_P_wq_all']) for r in rows], [int(r['rank_Z_wq_comb']) for r in rows])
zr = sp([int(r['rank_P_wq_all']) for r in rows], [int(r['rank_ZR_wq_comb']) for r in rows])
for label, val in (('等权ρ', f'{eq:.3f}'), ('Zρ', f'{z:.3f}'), ('ZRρ', f'{zr:.3f}')):
    checked += 1
    if val not in core:
        bad.append(('核心结论A', label, f'实际 {val} 未出现在报告'))

print('=== B. 敏感性表 ===')
sen = sec(r'### 2\.1 口径敏感性')
for lab, key in (('等权', 'rank_P_eq_all'), ('Z', 'rank_Z_wq_comb'), ('ZR', 'rank_ZR_wq_comb'),
                 ('线性', 'rank_P_lin'), ('指数', 'rank_P_exp'),
                 ('近 3 年', 'rank_P_recent3'), ('近 2 年', 'rank_P_recent2')):
    v = [int(r[key]) for r in rows]
    base = [int(r['rank_P_wq_all']) for r in rows]
    d = [abs(x - y) for x, y in zip(base, v)]
    rho = sp(base, v)
    checked += 1
    if f'{rho:.3f}' not in sen:
        bad.append(('2.1敏感性', lab, f'实际 ρ={rho:.3f} 未出现'))
    checked += 1
    if f'| {max(d)} 位 |' not in sen:
        bad.append(('2.1敏感性', lab, f'实际最大位移 {max(d)} 位 未出现'))

print('=== C. 收敛表 4.2 / 4.3 ===')
c42 = sec(r'### 4\.2')
for y in YS:
    checked += 1
    row = [ln for ln in c42.split('\n') if ln.startswith(f'| {y} |')]
    if not row:
        bad.append(('4.2', y, '缺该年行'))
        continue
    cells = [c.strip() for c in row[0].strip('|').split('|')]
    # 按**报告实际显示精度**比对，否则四舍五入会被误判为不一致
    ND = {'pool_median': 1, 'sigma': 2, 'cv': 4, 'iqr_norm': 4, 'gini': 4,
          'r90_10_norm': 4, 'range_norm': 4, 'mad_norm': 4}
    for idx, key in ((3, 'pool_median'), (4, 'sigma'), (5, 'cv'), (6, 'iqr_norm'),
                     (7, 'gini'), (8, 'r90_10_norm'), (9, 'range_norm'), (10, 'mad_norm')):
        checked += 1
        try:
            if abs(float(cells[idx]) - float(IND[y][key])) > 0.5 * 10 ** (-ND[key]) + 1e-9:
                bad.append(('4.2', f'{y}/{key}',
                            f'报告={cells[idx]} 实际={float(IND[y][key]):.{ND[key]}f}'))
        except ValueError:
            bad.append(('4.2', f'{y}/{key}', f'报告值非数值：{cells[idx]!r}'))

c43 = sec(r'### 4\.3')
for k in ('cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm'):
    lo, hi = TRD[k]['ci_lo'], TRD[k]['ci_hi']
    checked += 1
    if f'[{float(lo):+.5f}, {float(hi):+.5f}]' not in c43:
        bad.append(('4.3', k, f'CI 实际=[{float(lo):+.5f}, {float(hi):+.5f}] 未出现'))

print('=== D. 趋势分类表 5.2 ===')
c52 = sec(r'### 5\.2')
from collections import Counter
cnt = Counter(r['trend_class'] for r in load('趋势分类-嘉定区-2022-2026.csv'))
for cls, n in cnt.items():
    checked += 1
    rows_in = [ln for ln in c52.split('\n') if ln.startswith(f'| {cls} |')]
    if len(rows_in) != n:
        bad.append(('5.2', cls, f'报告 {len(rows_in)} 行，实际 {n} 所'))
for r in load('趋势分类-嘉定区-2022-2026.csv'):
    if short(r['junior_high_school']) not in c52:
        bad.append(('5.2', short(r['junior_high_school']), '未出现在清单中'))

print('=== E. 第 8 章个案：加权均分与 SEN ===')
c8 = sec(r'## 8 代表性公办初中个案')
for full, s in S.items():
    disp = short(full)
    if disp not in c8:
        continue
    # 该校逐年表里的均分
    m = re.search(r'\*\*' + re.escape(disp) + r'\*\*.*?\n\n(\|.*?)\n\n', c8, re.S)
    if not m:
        continue
    tbl = m.group(1)
    for y in YS:
        v = W[full].get(f'mean_score_base3_wq_{y}', '')
        if not v:
            continue
        exp = f'| {y} | {float(v):.1f} |'
        checked += 1
        if exp not in tbl:
            bad.append(('第8章', f'{disp}/{y}', f'均分实际 {float(v):.1f} 未出现'))

print('=== H. 本轮新发现项（防回归）===')
# H1 1.1 宽表结构应为 200 列 × 40 行
_w = list(load('宽表-初中水平-嘉定区-2022-2026.csv'))
for txt in (f'**{len(_w[0])} 列 × {len(_w)} 行', f'在宽表 {len(_w)} 行'):
    checked += 1
    if txt not in rep:
        bad.append(('1.1', '宽表结构', f'实际「{txt}」未出现'))
# H2 1.2 委属线：从未出现校数 + 规模相关（符号易错）
_WS = ['上海中学', '交大本部', '复旦附中', '华师大二附', '上师大附中']
_c0 = sum(1 for r in _w if not any(r.get(f'quota_{w}_{y}', '') not in ('', None)
                                   and float(r[f'quota_{w}_{y}']) > 0
                                   for y in YS for w in _WS))
checked += 1
if f'**{_c0} 所初中 5 年从未出现**' not in rep:
    bad.append(('1.2', '从未出现校数', f'实际 {_c0} 所未出现'))
_sz = [float(r['quota3_avg'] or 0) for r in _w]
_ct = [sum(1 for y in YS for w in _WS
           if r.get(f'quota_{w}_{y}', '') not in ('', None) and float(r[f'quota_{w}_{y}']) > 0)
       for r in _w]
_rho = sp(_sz, _ct)
checked += 1
if f'{_rho:+.3f}' not in rep:
    bad.append(('1.2', '规模偏置ρ', f'实际 {_rho:+.3f} 未出现'))
# H3 第 7 章第一梯队：只有等权与 ZR 成员不变，ρ 范围须与实际一致
_alkeys = [('等权', 'rank_P_eq_all'), ('Z', 'rank_Z_wq_comb'), ('ZR', 'rank_ZR_wq_comb'),
           ('线性', 'rank_P_lin'), ('指数', 'rank_P_exp'), ('近 3 年', 'rank_P_recent3'),
           ('近 2 年', 'rank_P_recent2')]
_base = {r['junior_high_school'] for r in RK if int(r['rank_P_wq_all']) <= 5}
_keep = [lb for lb, k in _alkeys
         if {r['junior_high_school'] for r in RK if int(r[k]) <= 5} == _base]
_rhos = [sp([int(r['rank_P_wq_all']) for r in RK], [int(r[k]) for r in RK]) for _, k in _alkeys]
checked += 1
if f'{min(_rhos):.3f}–{max(_rhos):.3f}' not in rep:
    bad.append(('第7章', 'Spearman范围', f'实际 {min(_rhos):.3f}–{max(_rhos):.3f} 未出现'))
checked += 1
# 去空格比对：报告里的中英文空格习惯易变，长度断言不该被空格绊倒
_ns = lambda x: re.sub(r'\s+', '', x)
if _ns(f'仅{"与".join(_keep)}两种口径下成员不变') not in _ns(rep):
    bad.append(('第7章', '成员不变口径', f'实际仅 {_keep} 不变'))
checked += 1
if '全部为前 5' in rep:
    bad.append(('第7章', '旧断言', '仍含「全部为前 5」，与实际不符'))
# H4 2.0 精度提示三组极差
_p5 = sorted([float(r['P_wq_all']) for r in RK], reverse=True)
for lab, a, b in (('1-2', 0, 1), ('3-5', 2, 4), ('6-8', 5, 7)):
    v = f'{_p5[a] - _p5[b]:.3f}'
    checked += 1
    if v not in rep:
        bad.append(('2.0', f'第{lab}名极差', f'实际 {v} 未出现'))

print('=== I. 3.3 线难度（仅公办口径，2025 尾线易错）===')
c33 = sec(r'### 3\.3')
_pub = [r for r in _w if r['ownership'] == '公办']
_ld = {}
for y in ('2025', '2026'):
    _ld[y] = {}
    for nm in ('交大嘉定', '上师嘉新', '嘉定一中'):
        vs = [float(r[f'score_{nm}_{y}']) for r in _pub
              if r.get(f'score_{nm}_{y}', '') not in ('', None)]
        _ld[y][nm] = st.fmean(vs) if vs else None
for y in ('2025', '2026'):
    for nm, v in _ld[y].items():
        checked += 1
        if v is not None and f'{v:.1f}' not in c33:
            bad.append(('3.3', f'{y}/{nm}均分', f'实际 {v:.1f} 未出现'))
# 尾线 = 均分最低那条；2025 应为上师嘉新
for y in ('2025', '2026'):
    tail = min(_ld[y], key=lambda k: _ld[y][k])
    checked += 1
    if y == '2025':
        if '上师大附中嘉定新城**' not in c33:
            bad.append(('3.3', '2025 尾线', f'实际应为 {tail}（上师嘉新）'))
    else:
        if '| 嘉定一中 |' not in c33:
            bad.append(('3.3', '2026 尾线', f'实际应为 {tail}'))

print('=== G. 第 3 章名额相关性 ===')
c31 = sec(r'### 3\.1')
# 报告用 U+2212（−）表示负号，脚本生成 ASCII(-)，直接 in 判断会误报。
# 归一化两种减号后再比对。
_norm_rho = lambda t: t.replace('\u2212', '-').replace('\u2013', '-')
_c31n = _norm_rho(c31)
_repn = _norm_rho(rep)
# 复算 3.1 的三个关键 ρ（跨样本用 ranked 28 所；同线内用全区 40 所，含民办，保持可比）
_all = list(load('宽表-初中水平-嘉定区-2022-2026.csv'))
_r = [r for r in _all if r['row_type'] == 'ranked' and r['P_wq']]
_r2 = [r for r in _all if r['row_type'] == 'ranked' and r['rel_avg']]
LN = [('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')]
_pr = []
for r in _all:
    for y in YS:
        for nm, c in LN:
            q, rk = r[f'quota_{nm}_{y}'], r[f'rank_base3_wq_{y}']
            if q not in ('', None) and rk not in ('', None):
                _pr.append((int(q), int(float(rk)), c))
_expect = {
    '名额~P': (f"{sp([float(r['quota3_avg']) for r in _r], [float(r['P_wq']) for r in _r]):+.3f}", c31),
    '名额~rel': (f"{sp([float(r['quota3_avg']) for r in _r2], [float(r['rel_avg']) for r in _r2]):+.3f}", c31),
    '同线内': (f"{sp([x[0] for x in _pr], [x[1] for x in _pr]):+.3f}", c31),
}
whole = rep  # 同线内 ρ 也在第 7 章被引用
for lab, (val, _where) in _expect.items():
    checked += 1
    if val not in _c31n:
        bad.append(('3.1', lab, f'实际 {val} 未出现'))
    checked += 1
    if val not in _repn:
        bad.append(('3.1', lab + '(全文)', f'{val} 未出现'))
checked += 1
if f'| {len(_pr)} |' not in c31:
    bad.append(('3.1', '同线内 n', f'实际 {len(_pr)} 未出现'))
# 第 7 章证据表不得残留旧值
for stale in ('0.509', '0.211', 'n=411'):
    checked += 1
    if stale in rep:
        bad.append(('第7章', stale, '旧值残留'))

print('=== F. 池子数与公办口径 ===')
c41 = sec(r'### 4\.1')
# 报告用中文「2022 年 27 所 → 2026 年 32 所」表述，不能假定斜杠格式
# 逐年池子数在报告里是**表格**（表头 2022..2026，数据行「公办池学校数」）
seq = [(y, IND[y]['pool_n']) for y in YS]
prow = [ln for ln in c41.split('\n') if ln.startswith('| 公办池学校数')]
checked += 1
if not prow:
    bad.append(('4.1', '池子逐年数', '未找到「公办池学校数」行'))
else:
    cells = [x.strip() for x in prow[0].strip('|').split('|')][1:]
    got = dict(zip(YS, cells))
    for y, n in seq:
        checked += 1
        if got.get(y) != n:
            bad.append(('4.1', f'{y} 公办池数', f'报告={got.get(y)} 实际={n}'))
# 混淆量化表逐年核对
for y in YS:
    checked += 1
    row = [ln for ln in c41.split('\n') if ln.startswith(f'| {y} |')]
    if not row:
        bad.append(('4.1', f'{y}混淆行', '缺该年行'))
        continue
    c = [x.strip() for x in row[0].strip('|').split('|')]
    if c[1] != IND[y]['outside_n']:
        bad.append(('4.1', f'{y}/样本外校数', f'报告={c[1]} 实际={IND[y]["outside_n"]}'))
    # 报告用「—」表示无值，CSV 为空串，二者等价
    norm = lambda t: '' if t in ('—', '-', '') else t
    if norm(c[2]) != norm(IND[y]['outside_pct_mean']):
        bad.append(('4.1', f'{y}/平均分位', f'报告={c[2]} 实际={IND[y]["outside_pct_mean"]}'))
q2 = sec(r'\*\*C\. 差距是否缩小')
for tag, val in (('明显上升', cnt.get('明显上升', 0)), ('明显下降', cnt.get('明显下降', 0))):
    checked += 1
    if f'**{val} 所**' not in q2:
        bad.append(('核心结论C/D', tag, f'实际 {val} 所 未出现'))

print()
print(f'第二层机械比对 {checked} 处')
if not bad:
    print('✅ 全部一致')
else:
    print(f'❌ {len(bad)} 处不一致：')
    for where, who, why in bad:
        print(f'  [{where}] {who}: {why}')
