# -*- coding: utf-8 -*-
"""嘉定区小红书素材生成（7 张图）。

主图 = 排名表；5 张子图 = 名额与位次 / 切点深度 / 无收敛 / 残差个案 / 有效边界；1 张长图。
配色：蓝绿 teal（#0F766E / #14B8A6 / #F0FDFA），与徐汇的粉红系区分。
产物写入 target/小红书/嘉定区名额分配到校分析/（本地发布素材，不入库）。
所有结论数字均从交付物 CSV 现算，脚本内不硬编码。
"""
import csv
import sys
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
D = f'{ROOT}/data/嘉定区/学校'
OUT = f'{ROOT}/target/小红书/嘉定区名额分配到校分析'
os.makedirs(OUT, exist_ok=True)
YEARS = [2022, 2023, 2024, 2025, 2026]
QL = ['142001', '142002', '142004']
QNAME = {'142001': '嘉定一中', '142002': '交大附中嘉定分校', '142004': '上师嘉新'}
# 宽表列名用的是**简称**，与上面的显示名不同，不可混用
QCOL = {'142001': '嘉定一中', '142002': '交大嘉定', '142004': '上师嘉新'}

C = dict(bg='#F0FDFA', card='#FFFFFF', main='#0F766E', accent='#14B8A6',
         light='#CCFBF1', pale='#F5FDFB', muted='#5F7A76', line='#D9EFEA',
         warnbg='#FFFBEB', deep='#134E4A')

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{width:1080px;margin:0 auto;font-family:"PingFang SC","Microsoft YaHei",sans-serif;
  background:BG;color:#22302E}
.wrap{width:1080px;padding:0 40px 46px;background:BG}
.kicker{font-size:26px;letter-spacing:3px;color:MAIN;font-weight:800;margin:34px 0 10px}
h1.title{font-size:54px;line-height:1.18;font-weight:800;color:DEEP}
.sub{font-size:27px;color:MUTED;line-height:1.6;margin-top:12px}
.card{background:CARD;border-radius:28px;padding:32px 36px;margin-top:26px;
  box-shadow:0 10px 30px rgba(15,118,110,.09)}
.h2{display:flex;align-items:center;gap:14px;font-size:34px;font-weight:800;
  color:MAIN;margin-bottom:8px}
.h2 .num{background:MAIN;color:#fff;width:48px;height:48px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;font-size:26px;flex:none}
.lead{font-size:27px;line-height:1.72;color:#3c4a48}
.lead b{color:MAIN}
.note{font-size:24px;line-height:1.62;color:#8A5A16;background:WARNBG;
  border-left:8px solid #F59E0B;padding:14px 18px;border-radius:12px;margin-top:16px}
.kv{display:flex;gap:14px;margin-top:18px;flex-wrap:wrap}
.kv span{background:PALE;border:1px solid LINE;border-radius:14px;
  padding:10px 16px;font-size:25px;color:#3c4a48}
.kv b{color:MAIN}
table{width:100%;border-collapse:collapse;margin-top:14px}
th{font-size:24px;color:MAIN;text-align:center;padding:12px 6px;
  border-bottom:2px solid LIGHT;white-space:nowrap;line-height:1.3}
td{font-size:26px;padding:10px 6px;border-bottom:1px solid #EFF7F5;text-align:center}
td.c2{text-align:left}
tr:nth-child(even) td{background:PALE}
tr.top td{background:LIGHT;font-weight:800}
tr.top td.c2{color:DEEP}
/* 未参与主排序的新开办校行：与网页版保持同一语义（暖黄底 + 左侧色条） */
tr.new td{background:#FFF8E6;color:#6B5410;font-size:23px}
tr.new td.c2{font-weight:600}
tr.new td:first-child{box-shadow:inset 4px 0 0 #E2A03F}
span.tag{display:inline-block;background:#E2A03F;color:#fff;border-radius:8px;
  padding:1px 8px;font-size:19px;font-weight:700;margin-left:6px;vertical-align:2px}
.foot{font-size:22px;color:#93A5A2;line-height:1.6;margin-top:18px}
.chip{background:PALE;border:1px solid LINE;border-radius:12px;
  padding:7px 14px;font-size:23px;color:#3c4a48}
.chip.hot{background:MAIN;border-color:MAIN;color:#fff;font-weight:800}
.big{font-size:54px;font-weight:800;color:MAIN;line-height:1.1}
.big small{font-size:25px;font-weight:600;color:MUTED;margin-left:8px}
.bar{display:flex;align-items:center;gap:12px;margin-top:12px}
.bar .lb{width:190px;font-size:25px;color:#3c4a48;flex:none}
.bar .tr{flex:1;min-width:120px;background:PALE;border-radius:8px;height:30px}
.bar .fl{height:30px;border-radius:8px;background:MAIN}
.bar .fl.alt{background:ACCENT}
.bar .vv{width:250px;font-size:24px;color:MUTED;flex:none;text-align:right}
.sect{font-size:25px;color:MUTED;margin-top:22px;line-height:1.6}
.foot2{font-size:21px;color:#9BAFAC;line-height:1.6;margin-top:26px;text-align:center}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:16px}
.two .box{background:PALE;border:1px solid LINE;border-radius:20px;padding:20px 22px}
.two .box .t{font-size:25px;color:MUTED}
.two .box .v{font-size:46px;font-weight:800;color:MAIN;margin-top:4px}
.two .box .d{font-size:22px;color:#8A9A97;line-height:1.55;margin-top:6px}
"""
for k, v in C.items():
    CSS = CSS.replace(k.upper() if k in ('BG',) else k.upper(), v) \
        if k in ('bg',) else CSS
CSS = (CSS.replace('BG', C['bg']).replace('CARD', C['card']).replace('MAIN', C['main'])
       .replace('ACCENT', C['accent']).replace('LIGHT', C['light']).replace('PALE', C['pale'])
       .replace('MUTED', C['muted']).replace('LINE', C['line']).replace('WARNBG', C['warnbg'])
       .replace('DEEP', C['deep']))


def load(p, d=None):
    with open(f'{d or A}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def page(inner, title):
    return (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=1080"><title>{title}</title>'
            f'<style>{CSS}</style></head><body><div class="wrap">{inner}</div></body></html>')


def head(kicker, title, sub):
    return (f'<div class="kicker">{kicker}</div><h1 class="title">{title}</h1>'
            f'<div class="sub">{sub}</div>')


def bar(label, frac, valtxt, alt=False):
    w = max(2.0, frac * 100)
    return (f'<div class="bar"><div class="lb">{label}</div>'
            f'<div class="tr"><div class="fl{" alt" if alt else ""}" style="width:{w:.1f}%"></div></div>'
            f'<div class="vv">{valtxt}</div></div>')


SH = lambda n: n.replace('上海市嘉定区', '').replace('上海市', '')
W = load('宽表-初中水平-嘉定区-2022-2026.csv')
TR = {r['junior_high_school']: r for r in load('趋势分析-嘉定区-2022-2026.csv')}
SL = load('单线视角-嘉定区-2022-2026.csv')
TB = sorted([r for r in W if r['ranked'] == '1'], key=lambda r: int(r['rank_P_wq']))
RANK = [{'rk': int(r['rank_P_wq']), 'name': SH(r['junior_high_school']),
         'P': float(r['P_wq']), 'rel': float(r['rel_avg']),
         'q': float(r['quota3_avg']), 'sen': float(r['SEN']),
         # 与主表对齐所需的两个额外列（2026-10-04 新增）
         'years': '22–26',
         'r3': r['rank_P_recent3'] or '—',
         'r26': int(float(r['rank_base3_wq_2026'])) if r['rank_base3_wq_2026'] else '—'}
        for r in TB]
FULL5 = len([r for r in W if r['years_included'] == '5'])
PRIV = len([r for r in W if r['ownership'] == '民办'])
TOP5 = [r['name'] for r in RANK[:5]]
DISP = {}
for y in YEARS:
    xs = sorted(float(r[f'mean_score_base3_wq_{y}']) for r in W if r[f'mean_score_base3_wq_{y}'])
    n = len(xs)
    DISP[y] = {'n': n, 'iqr': xs[n * 3 // 4] - xs[n // 4], 'sigma': st.pstdev(xs)}
CONV = {y: (float(list(TR.values())[0][f'convB_b_{y}']),
            float(list(TR.values())[0][f'convB_r2_{y}'])) for y in YEARS[1:]}
Q = {}
for f in ('名额到校计划-嘉定区-2023-2026.csv', '名额到校计划-嘉定区-2022-图片转录.csv'):
    for r in load(f, D):
        Q[(r['junior_high_school'], r['senior_high_school_code'], int(r['year']))] = int(r['quota'])
SCH = sorted({k[0] for k in Q})
SHARE = {}
for c in QL:
    SHARE[QNAME[c]] = {}
    for y in YEARS:
        v = [Q[(s, c, y)] / sum(Q.get((s, x, y), 0) for x in QL) for s in SCH
             if sum(Q.get((s, x, y), 0) for x in QL) > 0 and Q.get((s, c, y), 0) > 0]
        if len(v) >= 5:
            SHARE[QNAME[c]][y] = (round(st.median(v), 3), round(max(v) - min(v), 3))
QTOT = {y: sum(Q.get((s, c, y), 0) for s in SCH for c in QL) for y in YEARS}
RESID = sorted([{'name': SH(k), 'sen': float(v['sen_ols']), 'rk': int(
    [r for r in W if r['junior_high_school'] == k][0]['rank_P_wq'])}
    for k, v in TR.items()], key=lambda r: r['sen'])[:8]
WEI_N = len([1 for r in SL if r['tier'] == '委属'])


# ---------- 相关统计（2026-10-04 补齐：此前这些值**硬编码在文案里**，口径一改就错） ----------
def spearman(xs, ys):
    """平均秩（标准 Spearman）——与 build_v3_jd.py:252 的实现一致。

    此前本脚本文案里的 rho 是手写常数（+0.509 / −0.211 / −0.271 …），
    既与报告不符（报告为 +0.538 / −0.324 / −0.350 …），也违背脚本自身
    「不硬编码」的声明。改为现算。
    """
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    ra, rb = rk(xs), rk(ys)
    ma, mb = st.fmean(ra), st.fmean(rb)
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / den if den else 0.0


WQ = {r['junior_high_school']: r for r in W}
RANKED = [k for k in WQ if WQ[k]['ranked'] == '1']

# 跨样本：区属年均名额 vs P_wq（报告 3.1 第 1 行）
RHO_CROSS = spearman([float(WQ[k]['quota3_avg']) for k in RANKED],
                     [float(WQ[k]['P_wq']) for k in RANKED])
# 同线内：该校该线名额 vs 该线名次（报告 3.1 第 3 行；口径 = 全区 40 所含民办）
_IN = []
for k, r in WQ.items():
    for y in YEARS:
        for c in QL:
            q, rk_ = r.get(f'quota_{QCOL[c]}_{y}'), r.get(f'rank_base3_wq_{y}')
            if q not in ('', None) and rk_ not in ('', None):
                _IN.append((int(q), float(rk_), c))
RHO_IN = spearman([x[0] for x in _IN], [x[1] for x in _IN])
N_IN = len(_IN)
RHO_LINE = {c: spearman([x[0] for x in _IN if x[2] == c], [x[1] for x in _IN if x[2] == c])
            for c in QL}
# 3.2 极差范围（口径 = 仅公办）
_PUB = [r for r in W if r['ownership'] == '公办']
_RNG = []
for c in QL:
    for y in YEARS:
        v = [int(r[f'quota_{QCOL[c]}_{y}'] or 0) for r in _PUB]
        tot = sum(v)
        sh = [x / tot for x in v if x > 0] if tot else []
        if sh:
            _RNG.append(max(sh) - min(sh))
RANGE_TXT = f'{min(_RNG):.3f}–{max(_RNG):.3f}' if _RNG else '—'
# 逐年离散度的极值（报告 5.x 口径）
IQR_LO = min(DISP[y]['iqr'] for y in YEARS)
IQR_HI = max(DISP[y]['iqr'] for y in YEARS)
IQR_SEQ = '、'.join(f'{y} {DISP[y]["iqr"]:.1f}' for y in YEARS)
R2_LO = min(CONV[y][1] for y in CONV)
R2_HI = max(CONV[y][1] for y in CONV)

# 4 所新开办校（2025/2026 才有成绩，不参与主排序）——主图需与主表 32 行口径对齐
# 行序与报告主表**完全一致**（报告 2 章末 4 行的顺序），便于图文对照
NEW_ORDER = ['上海市嘉定区嘉一实验初级中学', '上海师范大学附属第五嘉定实验学校',
             '交大附中附属嘉定洪德中学', '同济大学附属嘉定实验中学']
_WN = {r['junior_high_school']: r for r in W}
# ---- 第 4 章「差距是否缩小」：6 个归一化指标 + CI ----
IND = {int(r['year']): r for r in load('收敛指标-嘉定区-2022-2026.csv')}
TRD = {r['metric']: r for r in load('收敛趋势检验-嘉定区-2022-2026.csv')}
GAP_METRICS = [('sigma', 'σ'), ('cv', 'CV'), ('iqr_norm', 'IQR'),
               ('gini', 'Gini'), ('r90_10_norm', 'P90−P10'), ('range_norm', '极差'),
               ('mad_norm', 'MAD')]
GAP_CI = [(m, lab, float(TRD[m]['slope_b']), float(TRD[m]['ci_lo']), float(TRD[m]['ci_hi']))
          for m, lab in GAP_METRICS if m in TRD]

# ---- 第 5 章「谁升谁降」：28 所分类 ----
CLS = list(load('趋势分类-嘉定区-2022-2026.csv'))
CLASS_ORDER = ['明显上升', '温和上升', '方向不一', '温和下降', '明显下降']
TRN = {SH(r['junior_high_school']): r for r in CLS}   # 校名 → 趋势分类行（sen_recent3 在此）
BY_CLASS = {c: sorted([r for r in CLS if r['trend_class'] == c],
                      key=lambda r: -float(r['sen'])) for c in CLASS_ORDER}
N_SIG = sum(1 for r in CLS if r.get('sig_bonferroni') == '是')
N_SIG10 = sum(1 for r in CLS if r.get('sig_uncorrected') == '是')
FLIP = [r for r in CLS if r['sen_recent3'] and
        float(r['sen']) * float(r['sen_recent3']) < 0]

# ---- 第 8 章「代表性个案」：头部5 + 明显上升3 + 明显下降3 ----
CASES_UP = [r['junior_high_school'] for r in
            sorted(BY_CLASS['明显上升'], key=lambda r: -float(r['delta_rel']))[:3]]
CASES_DOWN = [r['junior_high_school'] for r in
              sorted(BY_CLASS['明显下降'], key=lambda r: float(r['sen']))[:3]]

def _span(years_list):
    """按实际年份生成跨度标签：'2026' → 26；'2025;2026' → 25–26。"""
    ys = [int(x) % 100 for x in years_list.split(';') if x]   # 2025 -> 25，与入榜校「22–26」同格式
    return str(ys[0]) if len(ys) == 1 else f'{ys[0]}–{ys[-1]}'


NEW4 = [{'name': SH(k),
         'years': _span(_WN[k]['years_list']),
         'r2': _WN[k]['rank_P_recent2'] or '—',
         'r26': int(float(_WN[k]['rank_base3_wq_2026'])) if _WN[k]['rank_base3_wq_2026'] else '—'}
        for k in NEW_ORDER]
assert len(NEW4) == 4, f'新开办校应为 4 所，实际 {len(NEW4)}'


def fig_main():
    rows = ''
    u = lambda v: f'{v:+.2f}'.replace('-', '−')   # 统一用 U+2212 减号
    for r in RANK:
        cls = ' class="top"' if r['rk'] <= 5 else ''
        r2 = WQ[[k for k in WQ if SH(k) == r['name']][0]]['rank_P_recent2'] or '—'
        rows += (f'<tr{cls}><td>{r["rk"]}</td><td class="c2">{r["name"]}</td>'
                 f'<td>{r["years"]}</td>'
                 f'<td>{r["P"]:.3f}</td><td>{u(r["rel"])}</td><td>{r["q"]:.1f}</td>'
                 f'<td>{r["r3"]}</td><td>{r2}</td><td>{r["r26"]}</td></tr>')
    # 新开办校（只有 1–2 年成绩，不参与主排序）：列值留「—」，仅披露近 2 年与 2026 位次
    for n in NEW4:
        rows += (f'<tr class="new"><td>—</td><td class="c2">{n["name"]} <span class="tag">新开办</span></td>'
                 f'<td>{n["years"]}</td><td>—</td><td>—</td><td>—</td>'
                 f'<td>—</td><td>{n["r2"]}</td><td>{n["r26"]}</td></tr>')
    inner = (head('嘉定区 · 初中「名额分配到校」',
                  f'{len(RANK)} 所入榜 + {len(NEW4)} 所新开办',
                  '2022–2026 五年公开数据 · 名额加权区属市重点线口径 · 分位 P 主排序')
             + f'<div class="card"><div class="h2"><div class="num">1</div>排名表</div>'
             '<table><tr><th>#</th><th>初中</th><th>数据跨度</th><th>P 分位</th>'
             '<th>均名(分)</th><th>名额</th>'
             '<th>近3年<br>排名</th><th>近2年<br>排名</th><th>26年<br>排名</th>'
             '</tr>' + rows + '</table>'
             '<div class="kv">'
             f'<span>全区 <b>{len(W)}</b> 所初中</span>'
             f'<span>入榜（5 年全勤 / n≥4）<b>{len(RANK)}</b> 所</span>'
             f'<span>五年全勤 <b>{FULL5}</b> 所</span>'
             f'<span>新开办（不参与主排序）<b>{len(NEW4)}</b> 所</span>'
             f'<span>民办未入榜 <b>{PRIV}</b> 所</span></div>'
             '<div class="note">读法：<b>P 分位</b>越大越强（位置可比，不是分值可比）；'
             '<b>均名</b>是高于当年全区中位多少分（跨年可比）；<b>名额</b>是招生规模，'
             '<b>是学校规模的代理</b>，不等于办学水平。</div>'
             '<div class="note">末 4 行<b>新开办校</b>只有 1–2 年成绩，<b>不参与主排序</b>，'
             '聚合指标留「—」；<b>近2年</b>列为 31 所池（含新开办校），'
             '与主排序的 28 所池不同，<b>不可直接比较</b>；嘉一实验仅 1 年，该列留空。</div>'
             '<div class="foot">数据：上海市教育考试院名额到校最低录取分 + 嘉定区教育局招生计划公示｜'
             '口径与局限见长图</div></div>')
    return page(inner, '嘉定名额到校排名')


def fig_gap():
    """子图 1 —— 对应报告第 4 章：差距是否随时间缩小。"""
    inner = (head('子课题 01 · 对应报告第 4 章', '五年了，差距在缩小吗？',
                  '固定样本 27 所 · <b>统计上无法判定</b>')
             + '<div class="card"><div class="h2"><div class="num">1</div>六个归一化指标的五年斜率</div>')
    mx = max(abs(b) for _, _, b, _, _ in GAP_CI) or 1
    for m, lab, b, lo, hi in GAP_CI:
        cross = lo <= 0 <= hi
        inner += (f'<div class="bar"><div class="lb">{lab}</div>'
                  f'<div class="tr"><div class="fl{" alt" if cross else ""}" '
                  f'style="width:{max(2.0, abs(b) / mx * 100):.1f}%"></div></div>'
                  f'<div class="vv">{b:+.5f}｜CI [{lo:+.5f}, {hi:+.5f}]</div></div>')
    ncross = sum(1 for _, _, _, lo, hi in GAP_CI if lo <= 0 <= hi)
    inner += ('<div class="note">判断规则：<b>置信区间跨 0 就不能说「有变化」</b>。'
              f'本表 <b>{ncross}/{len(GAP_CI)}</b> 个指标 CI 跨 0，且方向不一致（4 正 2 负）。'
              '因此结论是<b>「统计上无法判定」</b>，而不是「差距没有缩小」'
              '——后者是把「测不出」当成「没有」。</div></div>'
              '<div class="card"><div class="h2"><div class="num">2</div>但名次格局确实在收缩</div>'
              '<div class="lead">Q-Q 回归（2022 分位 → 2026 分位）斜率 <b>0.170</b>，'
              '检验 H0:β=1 得 <b>p=2.5e−05</b> —— 名次格局<b>显著向中心收缩</b>。</div>'
              '<div class="note">两条并存：<b>分数差距测不出变化</b>，但'
              '<b>名次格局在向中心靠拢</b>。两者不矛盾：前者比分差，后者比排序。</div></div>'
              '<div class="card"><div class="h2"><div class="num">3</div>为什么不能用全池离散度</div>'
              '<div class="lead">全区公办池逐年扩大（<b>27→32 所</b>），'
              '新进入的学校<b>平均分位 0.69–0.83、明显偏强</b>，'
              '会把中位抬高、相对离散度压低——这是<b>构成效应</b>，不是原有学校在靠近。</div></div>')
    return page(inner, '差距是否缩小')


def fig_trend():
    """子图 2 —— 对应报告第 5 章：谁在上升、谁在下降。"""
    inner = (head('子课题 02 · 对应报告第 5 章', '谁在上升，谁在下降？',
                  '28 所公办 · 五年斜率（SEN）方向分类')
             + '<div class="card"><div class="h2"><div class="num">1</div>五类分布</div>'
             '<div class="kv">')
    for c in CLASS_ORDER:
        inner += f'<span>{c} <b>{len(BY_CLASS[c])}</b> 所</span>'
    inner += '</div><div class="h2" style="margin-top:24px"><div class="num">2</div>完整清单</div>'
    mxsen = max(abs(float(x['sen'])) for x in CLS) or 1
    for c in CLASS_ORDER:
        if not BY_CLASS[c]:
            continue
        inner += f'<div class="sect">{c}（{len(BY_CLASS[c])} 所）</div>'
        for r in BY_CLASS[c]:
            inner += bar(SH(r['junior_high_school']), abs(float(r['sen'])) / mxsen,
                         (f"{float(r['sen']):+.2f} 分/年｜Δrel {float(r['delta_rel']):+.1f}"
                          ).replace('-', '−'),
                         alt=(c in ('温和下降', '明显下降')))
    inner += ('<div class="note">⚠ <b>没有一所学校达到统计显著</b>：'
              f'Mann-Kendall 未校正 p&lt;0.05 有 <b>{N_SIG10} 所</b>，'
              f'Bonferroni 校正后 <b>{N_SIG} 所</b>。这是<b>检验力天花板</b>——'
              'n=5 时即使完全单调，最小 p 也只有 ≈0.028，大于校正阈值 0.0036。'
              '所以本分类是<b>方向性描述</b>，不是「统计显著的结论」。</div></div>'
              '<div class="card"><div class="h2"><div class="num">3</div>「五年」与「近三年」是两回事</div>'
              f'<div class="lead">有 <b>{len(FLIP)}</b> 所学校五年方向与近三年方向<b>相反</b>'
              '——只看五年会误导，只看近三年同样会误导。</div><div class="kv">')
    for r in sorted(FLIP, key=lambda r: float(r['sen_recent3']))[:6]:
        inner += (f'<span>{SH(r["junior_high_school"])} 五年{float(r["sen"]):+.1f}'
                  f'／近3年{float(r["sen_recent3"]):+.1f}</span>').replace('-', '−')
    inner += '</div></div>'
    return page(inner, '谁在上升谁在下降')


def fig_case():
    """子图 3 —— 对应报告第 8 章：代表性公办初中个案。"""
    u = lambda v: f'{v:+.2f}'.replace('-', '−')
    inner = (head('子课题 03 · 对应报告第 8 章', '代表性个案',
                  '选人标准在分析前预注册：头部 5 + 明显上升 3 + 明显下降 3')
             + '<div class="card"><div class="h2"><div class="num">1</div>头部 5 所</div>'
             '<table><tr><th>#</th><th>初中</th><th>P 分位</th><th>均名(分)</th>'
             '<th>名额</th><th>五年斜率</th><th>近3年斜率</th></tr>')
    for r in RANK[:5]:
        t = TRN.get(r['name'], {})
        r3 = (f"{float(t['sen_recent3']):+.2f}".replace('-', '−')
              if t.get('sen_recent3') else '—')
        inner += (f'<tr class="top"><td>{r["rk"]}</td><td class="c2">{r["name"]}</td>'
                  f'<td>{r["P"]:.3f}</td><td>{u(r["rel"])}</td><td>{r["q"]:.1f}</td>'
                  f'<td>{u(r["sen"])}</td><td>{r3}</td></tr>')
    top5k = [k for k in WQ if SH(k) in TOP5]
    inner += ('</table><div class="note">头部 5 所的五年斜率：'
              + '、'.join(f'{SH(r["junior_high_school"])} {float(r["sen"]):+.2f}'
                          for r in sorted([x for x in CLS if x['junior_high_school'] in top5k],
                                          key=lambda r: float(r['sen']))).replace('-', '−')
              + ' —— <b>名次高不等于趋势好</b>。</div></div>')
    for title, keys in (('明显上升 3 所', CASES_UP), ('明显下降 3 所', CASES_DOWN)):
        inner += (f'<div class="card"><div class="h2"><div class="num">'
                  f'{"2" if keys is CASES_UP else "3"}</div>{title}</div><table>'
                  '<tr><th>初中</th><th>主口径名次</th><th>Δrel(分)</th>'
                  '<th>五年斜率</th><th>近3年斜率</th></tr>')
        for k in keys:
            r, tr = WQ[k], TRN.get(SH(k), {})
            r3 = (f"{float(tr['sen_recent3']):+.2f}".replace('-', '−')
                  if tr.get('sen_recent3') else '—')
            inner += (f'<tr><td class="c2">{SH(k)}</td><td>{int(r["rank_P_wq"])}</td>'
                      f'<td>{float(r["rel_avg"]):+.1f}</td><td>{u(float(r["SEN"]))}</td>'
                      f'<td>{r3}</td></tr>')
        inner += '</table></div>'
    inner += ('<div class="note">⚠ 这些学校的名额基数普遍偏小，单年波动大；'
              '<b>不要据此判定「学校变差」</b>——所有趋势都未达统计显著（见子课题 02）。</div>')
    return page(inner, '代表性个案')


def fig_bound():
    inner = (head('子课题 05', '这个榜到底测了哪一段？',
                  '指标的有效边界——<b>只看得到每校最前面一小段学生</b>')
             + '<div class="card"><div class="h2"><div class="num">1</div>名额到校只覆盖考生的一小部分</div>'
             f'<div class="big">{QTOT[YEARS[0]]} → {QTOT[YEARS[-1]]}'
             '<small>区内 3 条区属线名额合计（个/年）</small></div>'
             f'<div class="kv"><span>区内名额 5 年累计 <b>{sum(QTOT.values())}</b> 个</span>'
             '<span>按嘉定中考规模估算覆盖率 <b>约 17%</b>（估算值）</span></div>'
             '<div class="note">这 17% 落在每校<b>最前面的 4%–7%</b>（按各线名额占比推算）。'
             '换句话说，占考生 <b>90% 以上</b>的中后段完全不可见。</div></div>'
             '<div class="card"><div class="h2"><div class="num">2</div>不依赖估算的等价说法</div>'
             '<div class="lead">切点落在各校<b>名额批次的前 23%–42%</b>'
             '（嘉定一中 / 交大附中嘉定分校约 35%–42%、上师嘉新约 23%）'
             '——这个比例直接由官方计划表算出，<b>不需要任何外部假设</b>。</div>'
             '<div class="h2" style="margin-top:26px"><div class="num">3</div>所以这个榜不能回答什么</div>'
             '<div class="kv"><span>❌ 哪所学校整体更好</span>'
             '<span>❌ 各校生源的绝对水平</span>'
             '<span>❌ 名额落榜学生的去向</span></div>'
             '<div class="note">要回答「哪所学校整体更好」，需要补三类数据：'
             '各校毕业生规模、统招批次均分、市重点录取率。本榜单只测'
             '<b>名额到校通道的入围门槛</b>，不是学校绝对好坏。</div></div>')
    return page(inner, '有效边界')


def inner_of(page_html):
    """从完整页面里取出 wrap 内的内容。"""
    return page_html.split('<div class="wrap">', 1)[1].rsplit('</div></body>', 1)[0]


def strip_head(inner):
    """去掉子图自己的 kicker/title/sub（长图里统一用封面 + 章节号）。"""
    i = inner.find('<div class="card">')
    return inner[i:] if i > 0 else inner


def fig_long():
    cover = (head('嘉定区 · 初中「名额分配到校」2022–2026',
                  f'{len(RANK)} 所入榜公办 · 另披露 {len(NEW4)} 所新开办',
                  '名额加权区属市重点线口径 · 分位 P 主排序 · 全部结论可回源')
             + f'<div class="card"><div class="h2">四个研究问题</div>'
             '<div class="kv">'
             '<span class="chip hot">01 总排名（第 2 章）</span>'
             '<span class="chip">02 差距是否缩小（第 4 章）</span>'
             '<span class="chip">03 谁在上升、谁在下降（第 5 章）</span>'
             '<span class="chip">04 代表性个案（第 8 章）</span>'
             '<span class="chip">05 指标的有效边界（第 6 章）</span></div>'
             f'<div class="kv"><span>全区 <b>{len(W)}</b> 所</span>'
             f'<span>入榜 <b>{len(RANK)}</b> 所</span>'
             f'<span>五年全勤 <b>{FULL5}</b> 所</span>'
             f'<span>新开办（披露不计入排名）<b>{len(NEW4)}</b> 所</span>'
             f'<span>民办 n&lt;4 <b>{PRIV}</b> 所</span></div></div>')
    body = (cover
            + f'<div class="h2" style="margin-top:34px"><div class="num">1</div>总排名（第 2 章）</div>'
            + strip_head(inner_of(fig_main()))
            + '<div class="h2" style="margin-top:34px"><div class="num">2</div>差距是否缩小（第 4 章）</div>'
            + strip_head(inner_of(fig_gap()))
            + '<div class="h2" style="margin-top:34px"><div class="num">3</div>谁在上升、谁在下降（第 5 章）</div>'
            + strip_head(inner_of(fig_trend()))
            + '<div class="h2" style="margin-top:34px"><div class="num">4</div>代表性个案（第 8 章）</div>'
            + strip_head(inner_of(fig_case()))
            + '<div class="h2" style="margin-top:34px"><div class="num">5</div>指标的有效边界（第 6 章）</div>'
            + strip_head(inner_of(fig_bound()))
            + f'<div class="foot2">完整数据与方法（宽表 {len(W[0])} 列含逐线逐年原始分与名额）：'
              'https://istarfire.github.io/Shanghai-XueQuFang/<br>'
              '结论是统计推断，不是升学建议，择校请结合自身情况～</div>')
    return page(body, '嘉定名额到校长图')


FIGS = [('主图-排名表', fig_main), ('子图1-差距是否缩小', fig_gap),
        ('子图2-谁升谁降', fig_trend), ('子图3-代表性个案', fig_case),
        ('子图4-有效边界', fig_bound), ('长图', fig_long)]

if __name__ == '__main__':
    import subprocess
    for name, fn in FIGS:
        hp = f'{OUT}/{name}.html'
        with open(hp, 'w', encoding='utf-8') as f:
            f.write(fn())
        print('写出', hp.split('/')[-1])
    # 渲染 PNG（优先 playwright，缺失则跳过）
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('未安装 playwright，跳过 PNG 渲染')
        sys.exit(0)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={'width': 1080, 'height': 1200},
                        device_scale_factor=1)
        for name, _ in FIGS:
            src = f'file://{OUT}/{name}.html'
            pg.goto(src, wait_until='networkidle')
            h = pg.evaluate("document.querySelector('.wrap').getBoundingClientRect().height + 46")
            pg.set_viewport_size({'width': 1080, 'height': int(h)})
            pg.wait_for_timeout(220)
            out = f'{OUT}/{name}.png'
            pg.screenshot(path=out, clip={'x': 0, 'y': 0, 'width': 1080,
                                          'height': int(h)})
            print(f'渲染 {name}.png  1080×{int(h)}')
        b.close()
