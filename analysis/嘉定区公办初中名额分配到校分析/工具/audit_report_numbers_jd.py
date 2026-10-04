# -*- coding: utf-8 -*-
"""全量数字普查：报告中出现的每个小数，都应能在 CSV 或其派生量中找到出处。

动机：口径变更后，「表格已更新、正文散落旧数字」屡查屡有
（已发现 +0.509 / 精度提示 0.818 / 3.1 正文 / 第 8 章斜率等）。
逐类写校验容易漏，本脚本改**反向穷举**：
  1. 从 CSV + 派生量建立「合法数字集合」（按报告使用的各种精度展开）；
  2. 扫出报告里所有小数；
  3. 报告有、集合没有的 → 列为可疑，附上下文供人工判定。

这不是门禁（会有正常误报，如页码、百分比、年份），而是**发现器**。
它能兜住「手工替换漏了几处」这类错误。
"""
import csv
import os
import re
import statistics as st

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YS = ['2022', '2023', '2024', '2025', '2026']
OK = set()


def add(v, nds=(0, 1, 2, 3, 4, 5, 6)):
    """把一个数值按多种精度加入合法集合（报告各列精度不同）。"""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return
    for nd in nds:
        OK.add(f'{x:.{nd}f}')
        OK.add(f'{abs(x):.{nd}f}')


# ---- 1) 所有 CSV 的全部数值 ----
for fn in os.listdir(D):
    if not fn.endswith('.csv'):
        continue
    for r in csv.DictReader(open(f'{D}/{fn}', encoding='utf-8-sig')):
        for v in r.values():
            # 容忍科学计数法（如 3.71e-05），否则这类值会被漏收而误报
            if v and re.fullmatch(r'-?\d+(\.\d+)?([eE][-+]?\d+)?', v.strip()):
                add(v)

# ---- 2) 派生量：极差 / 均值 / Spearman / 计数 ----
M = [r for r in csv.DictReader(open(f'{D}/rank-多口径总表-嘉定区-2022-2026.csv',
                                   encoding='utf-8-sig')) if r['row_type'] == 'ranked']
M.sort(key=lambda r: int(r['rank_P_wq_all']))
p = [float(r['P_wq_all']) for r in M]
for a, b in ((0, 1), (2, 4), (5, 7), (0, 4)):
    add(p[a] - p[b])
    add(round(p[a] - p[b], 3))

IND = list(csv.DictReader(open(f'{D}/收敛指标-嘉定区-2022-2026.csv',
                               encoding='utf-8-sig')))
for r in IND:
    for k in ('pool_n', 'outside_n'):
        add(r[k])
    if r['outside_pct_mean']:
        add(r['outside_pct_mean'])
S = list(csv.DictReader(open(f'{D}/趋势分类-嘉定区-2022-2026.csv',
                             encoding='utf-8-sig')))
for r in S:
    for k in r:
        if 'p' in k.lower() or 'sen' in k or 'delta' in k or 'mk' in k.lower():
            add(r[k])
    for k in ('sen_recent3',):
        add(r[k])
# 类别计数
from collections import Counter
for c, n in Counter(r['trend_class'] for r in S).items():
    add(n)

# ---- 2b) Spearman 派生量（报告引用了大量 ρ，CSV 里没有） ----
_W = list(csv.DictReader(open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
def sp(xs, ys):
    def rk(v):
        # 平均秩（与 build_v3_jd.py:252 一致）。2026-10-04 修正：此前顺序秩会低估同线内 rho。
        s = sorted(v)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in v]
    a, b = rk(xs), rk(ys)
    ma, mb = st.fmean(a), st.fmean(b)
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den


_alk = ['rank_P_eq_all', 'rank_Z_wq_comb', 'rank_ZR_wq_comb', 'rank_P_lin',
        'rank_P_exp', 'rank_P_recent3', 'rank_P_recent2']
_base = [int(r['rank_P_wq_all']) for r in M]
for k in _alk:
    add(sp(_base, [int(r[k]) for r in M]))
add(sp([float(r['quota3_avg']) for r in M], [float(r['P_wq_all']) for r in M]))
add(sp([float(r['quota3_avg']) for r in M],
       [float(r['rel_avg']) for r in _W if r['row_type'] == 'ranked' and r['rel_avg']]))
# 线难度（当年均分）：报告 3.3 用了公办/全池两种口径
for sel in (_W, [r for r in _W if r['ownership'] == '公办']):
    for nm in ('交大嘉定', '上师嘉新', '嘉定一中'):
        for y in YS:
            vs = [float(r[f'score_{nm}_{y}']) for r in sel
                  if r.get(f'score_{nm}_{y}', '') not in ('', None)]
            if vs:
                add(st.fmean(vs))
# 3.2 逐线占比极差（仅公办口径）
for nm in ('嘉定一中', '交大嘉定', '上师嘉新'):
    for y in YS:
        vals = [int(r[f'quota_{nm}_{y}'] or 0) for r in _W if r['ownership'] == '公办']
        tot = sum(vals)
        sh = [v / tot for v in vals if v > 0]
        if sh:
            add(max(sh) - min(sh))
            add(st.median(sh))   # 3.2 表末行「中位占比」
# Bonferroni α
add(0.05 / 14)
add(0.05 / 14, (4,))

# ---- 2c) 本任务新引入的派生量 ----
# (1) 3.1 同线内三种 ρ（平均秩口径，含分线），自变量 quota 在小值处并列多
_LN = [('嘉定一中', '142001'), ('交大嘉定', '142002'), ('上师嘉新', '142004')]
_pr2 = []
for r in _W:
    for y in YS:
        for nm, c in _LN:
            q, rk = r.get(f'quota_{nm}_{y}', ''), r.get(f'rank_base3_wq_{y}', '')
            if q not in ('', None) and rk not in ('', None):
                _pr2.append((int(q), int(float(rk)), c))


def _rkavg(a):
    s2 = sorted(a)
    return [sum(1 for w in s2 if w < t) + (sum(1 for w in s2 if w == t) + 1) / 2 for t in a]


add(sp([x[0] for x in _pr2], [x[1] for x in _pr2]))
for _nm, _c in _LN:
    _sub = [x for x in _pr2 if x[2] == _c]
    add(sp([x[0] for x in _sub], [x[1] for x in _sub]))
# (2) 1.2 委属规模偏置 ρ（平均秩）+ 名额占比跨年 CV / 同年跨校范围
_WS8 = ['上海中学', '交大本部', '复旦附中', '华师大二附', '上师大附中']
add(sp([float(r['quota3_avg'] or 0) for r in _W],
       [sum(1 for y in YS for w in _WS8
            if r.get(f'quota_{w}_{y}', '') not in ('', None) and float(r[f'quota_{w}_{y}']) > 0)
        for r in _W]))
_shs = {}
for r in _W:
    if r['ownership'] != '公办':
        continue
    for nm in ('嘉定一中', '交大嘉定'):
        v = [int(r[f'quota_{nm}_{y}'] or 0) for y in YS]
        tot = [sum(int(k[f'quota_{nm}_{y}'] or 0) for k in _W if k['ownership'] == '公办') for y in YS]
        for i in range(5):
            if v[i] > 0 and tot[i] > 0:
                _shs.setdefault(r['junior_high_school'], []).append(v[i] / tot[i])
for c, arr in _shs.items():
    if len(arr) >= 4:
        m = st.fmean(arr)
        if m:
            add(st.pstdev(arr) / m)          # 跨年 CV
            add(min(arr)); add(max(arr))     # 占比范围
# (3) 「同年跨校占比范围 0.0290–0.0757」「相差 2.6 倍」「近 2 年位移 16 位」
_al = [x for arr in _shs.values() for x in arr]
if _al:
    add(min(_al)); add(max(_al)); add(max(_al) / min(_al), (1,))
# 报告写的是「各校占比**均值**」的跨校范围（0.0290–0.0757）
_means = [st.fmean(arr) for arr in _shs.values() if len(arr) >= 4]
if _means:
    add(min(_means)); add(max(_means))
add(13); add(16)

# ---- 3) 扫报告 ----
rep = open(f'{D}/分析报告.md', encoding='utf-8').read()
lines = rep.split('\n')
sus = []
for i, ln in enumerate(lines, 1):
    if ln.startswith('#') or not ln.strip():
        continue
    for m in re.finditer(r'(?<![\d.])(\d+\.\d+)(?![\d])', ln):
        v = m.group(1)
        if v in OK:
            continue
        # 排除明显非统计量：年份区间、页码、百分比区间、CSS/URL
        if re.fullmatch(r'(19|20)\d\d\.\d', v):
            continue
        ctx = ln[max(0, m.start() - 40):m.end() + 30].strip()
        sus.append((i, v, ctx))

DEC = re.compile(r'(?<![\d.])(\d+\.\d+)(?![\d])')
hit = sum(1 for ln in lines for m in DEC.finditer(ln) if m.group(1) in OK)
# ---- 白名单：经人工确认为「合理但不在 CSV 中」的历史/反事实数值 ----
# 每条必须写明理由，且**限定上下文**，避免变成「屏蔽一切」的空口子。
ALLOW = [
    (r'主排序 `P_wq` 因此重算', '归并前的反事实值（假设不与 2022 年合并的 4 年均值）'),
    (r'与上一版数值的差异', '排名池口径变更前的历史 Spearman，用于对照说明'),
]
kept = []
for i, v, ctx in sus:
    # 用前后 3 行的窗口匹配：说明句常与数字行分离（如「⚠ 与上一版数值的差异」在上一行）
    win = '\n'.join(lines[max(0, i - 4):i + 3])
    if any(re.search(pat, win) for pat, _ in ALLOW):
        continue
    kept.append((i, v, ctx))
sus = kept

print(f'合法数字集合 {len(OK)} 个；报告小数命中 {hit} 个')
print(f'可疑（报告中出现但 CSV/派生量中无出处）：{len(sus)} 处\n')
for i, v, ctx in sus:
    print(f'  L{i:<4} {v:<12} …{ctx}…')
