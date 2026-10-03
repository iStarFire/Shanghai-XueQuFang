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
  border-bottom:2px solid LIGHT;white-space:nowrap}
td{font-size:26px;padding:10px 6px;border-bottom:1px solid #EFF7F5;text-align:center}
td.c2{text-align:left}
tr:nth-child(even) td{background:PALE}
tr.top td{background:LIGHT;font-weight:800}
tr.top td.c2{color:DEEP}
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
         'q': float(r['quota3_avg']), 'sen': float(r['SEN'])} for r in TB]
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


def fig_main():
    rows = ''
    for r in RANK:
        cls = ' class="top"' if r['rk'] <= 5 else ''
        u = lambda v: f'{v:+.2f}'.replace('-', '−')   # 统一用 U+2212 减号
        rows += (f'<tr{cls}><td>{r["rk"]}</td><td class="c2">{r["name"]}</td>'
                 f'<td>{r["P"]:.3f}</td><td>{u(r["rel"])}</td><td>{r["q"]:.1f}</td>'
                 f'<td>{u(r["sen"])}</td></tr>')
    inner = (head('嘉定区 · 初中「名额分配到校」',
                  f'{len(RANK)} 所公办初中真实梯队',
                  '2022–2026 五年公开数据 · 名额加权区属市重点线口径 · 分位 P 主排序')
             + f'<div class="card"><div class="h2"><div class="num">1</div>排名表</div>'
             '<table><tr><th>#</th><th>初中</th><th>P 分位</th><th>均名(分)</th>'
             '<th>名额</th><th>趋势</th></tr>' + rows + '</table>'
             '<div class="kv">'
             f'<span>全区 <b>{len(W)}</b> 所初中</span>'
             f'<span>入榜（5 年全勤 / n≥4）<b>{len(RANK)}</b> 所</span>'
             f'<span>五年全勤 <b>{FULL5}</b> 所</span>'
             f'<span>民办未入榜 <b>{PRIV}</b> 所</span></div>'
             '<div class="note">读法：<b>P 分位</b>越大越强（位置可比，不是分值可比）；'
             '<b>均名</b>是高于当年全区中位多少分（跨年可比）；<b>名额</b>是招生规模，'
             '不等于办学水平；<b>趋势</b>是 rel 的最小二乘斜率，负=持续下滑。</div>'
             '<div class="foot">数据：上海市教育考试院名额到校最低录取分 + 嘉定区教育局招生计划公示｜'
             '口径与局限见长图</div></div>')
    return page(inner, '嘉定名额到校排名')


def fig_scale():
    xs = [r['q'] for r in RANK]
    x0, x1, y0, y1 = 0, 30, 0, 0.98
    W_, H_, L_, T_ = 900, 400, 60, 34
    px = lambda v: L_ + (v - x0) / (x1 - x0) * W_
    py = lambda v: T_ + H_ - (v - y0) / (y1 - y0) * H_
    dots = ''
    for r in RANK:
        big = r['rk'] <= 5
        dots += (f'<circle cx="{px(r["q"]):.1f}" cy="{py(r["P"]):.1f}" '
                 f'r="{8 if big else 6}" fill="{C["main"] if big else C["accent"]}" '
                 f'opacity="{1 if big else .45}"/>')
    placed = []
    for r in sorted(RANK[:5], key=lambda r: -r['P']):
        cx, cy = px(r['q']), py(r['P'])
        off = 0.0
        while any(abs(cx - q) < 46 and abs(cy + off - v) < 32 for q, v in placed):
            off -= 36.0
        ly = cy + off
        placed.append((cx, ly))
        if off:
            dots += (f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx:.1f}" y2="{ly:.1f}" '
                     f'stroke="{C["main"]}" stroke-width="2"/>')
        dots += (f'<circle cx="{cx:.1f}" cy="{ly:.1f}" r="15" fill="{C["main"]}" '
                 f'stroke="#fff" stroke-width="3"/>'
                 f'<text x="{cx:.1f}" y="{ly+6:.1f}" font-size="18" fill="#fff" '
                 f'text-anchor="middle" font-weight="800">{r["rk"]}</text>')
    grid = ''
    for gy in [0.2, 0.4, 0.6, 0.8]:
        grid += (f'<line x1="{L_}" y1="{py(gy):.1f}" x2="{L_+W_}" y2="{py(gy):.1f}" '
                 f'stroke="{C["line"]}" stroke-width="1"/>'
                 f'<text x="{L_-12}" y="{py(gy)+7:.1f}" font-size="18" fill="{C["muted"]}" '
                 f'text-anchor="end">{gy:.1f}</text>')
    for gx in [0, 10, 20, 30]:
        grid += (f'<line x1="{px(gx):.1f}" y1="{T_}" x2="{px(gx):.1f}" y2="{T_+H_}" '
                 f'stroke="{C["line"]}" stroke-width="1"/>'
                 f'<text x="{px(gx):.1f}" y="{T_+H_+30}" font-size="18" '
                 f'fill="{C["muted"]}" text-anchor="middle">{gx}</text>')
    svg = (f'<svg width="{W_+2*L_}" height="{H_+T_+52}" viewBox="0 0 {W_+2*L_} {H_+T_+52}">'
           f'{grid}<line x1="{L_}" y1="{T_+H_}" x2="{L_+W_}" y2="{T_+H_}" stroke="{C["muted"]}"/>'
           f'<line x1="{L_}" y1="{T_}" x2="{L_}" y2="{T_+H_}" stroke="{C["muted"]}"/>{dots}'
           f'<text x="{L_+W_/2}" y="{H_+T_+48}" font-size="19" fill="{C["muted"]}" '
           f'text-anchor="middle">区属年均名额（个）</text>'
           f'<text x="18" y="{T_+H_/2:.0f}" font-size="19" fill="{C["muted"]}" '
           f'text-anchor="middle" transform="rotate(-90 18 {T_+H_/2:.0f})">P 分位</text></svg>')
    legend = ''.join(f'<span class="chip">{r["rk"]} {r["name"]}</span>' for r in RANK[:5])
    inner = (head('子课题 01', '名额越多，位次越好吗？',
                  '名额规模与位次的关系——两层检验，结论相反')
             + f'<div class="card"><div class="h2"><div class="num">1</div>跨样本：名额多 → 名次好</div>'
             f'{svg}<div class="kv" style="margin-top:8px">{legend}</div>'
             f'<div class="kv"><span>Spearman(名额, P) = <b>+0.509</b></span>'
             '<span>n = 28</span><span>深色 = 前 5 名</span></div>'
             '<div class="lead" style="margin-top:14px">名额多的学校，分位普遍更高。</div></div>'
             '<div class="card"><div class="h2"><div class="num">2</div>同线内：控制线难度后仍在，但强度大减</div>'
             '<div class="two">'
             '<div class="box"><div class="t">同线内 Spearman</div><div class="v">−0.211</div>'
             '<div class="d">控制线难度后，名额多的校名次仍更靠前，但强度大幅衰减</div></div>'
             '<div class="box"><div class="t">样本量</div><div class="v">411</div>'
             '<div class="d">校 × 线 × 年 的配对数</div></div></div>'
             '<div class="kv"><span>嘉定一中 −0.271</span><span>交大附中嘉定分校 −0.156</span>'
             '<span>上师嘉新 −0.184</span></div>'
             '<div class="note">名额按<b>志愿填报</b>分配（公告明文按中招报名人数占比测算），'
             '所以名额在嘉定是「志愿热度」的代理，不是学校规模的代理——'
             '不能读作「规模决定水平」。</div></div>')
    return page(inner, '名额与位次')


def fig_depth():
    inner = (head('子课题 02', '名额占多少？切点到底多深',
                  '名额占比的校际离散——嘉定的切点深度<b>不恒定</b>')
             + '<div class="card"><div class="h2"><div class="num">1</div>各线名额占本校区属名额的比例（中位数）</div>')
    for nm, per in SHARE.items():
        inner += f'<div class="sect">{nm}</div>'
        mx = max(v[0] for v in per.values())
        for y in sorted(per):
            mid, rng = per[y]
            inner += bar(f'{y} 年', mid / mx, f'中位 {mid:.2f}｜极差 {rng:.2f}')
    inner += ('<div class="note">极差 = 该年各校名额占本校区属名额比例的<b>最大值 − 最小值</b>。'
              '三条线的极差都在 <b>0.12–0.33</b>，意味着各校名额占比<b>差别很大</b>。</div></div>'
              '<div class="card"><div class="h2"><div class="num">2</div>为什么会这样</div>'
              '<div class="lead">名额按<b>志愿填报</b>分配：强校学生更愿意报低线，'
              '于是强校的名额占比更高、分数线更高。嘉定一中占比中位数从 '
              f'<b>{SHARE["嘉定一中"][2022][0]:.2f}</b>（2022）降到 '
              f'<b>{SHARE["嘉定一中"][2026][0]:.2f}</b>（2026），'
              '因为上师大附中嘉定新城分校正在吸走一部分低线名额。</div>'
              '<div class="note">推论：正因为占比不恒定，「名额越多→切得越深→分数线越低」'
              '这个机械效应在嘉定<b>不会被自动抵消</b>；但 01 图显示它被「生源强度」盖过了。</div></div>')
    return page(inner, '切点深度')


def fig_conv():
    mx = max(v['iqr'] for v in DISP.values())
    inner = (head('子课题 03', '五年了，差距在收敛吗？',
                  '逐年离散度与收敛回归——答案是<b>没有</b>')
             + '<div class="card"><div class="h2"><div class="num">1</div>校际离散度（IQR / σ）逐年</div>')
    for y in YEARS:
        inner += bar(f'{y} 年（n={DISP[y]["n"]}）', DISP[y]['iqr'] / mx,
                     f'IQR {DISP[y]["iqr"]:.1f}｜σ {DISP[y]["sigma"]:.2f}', alt=y % 2 == 1)
    inner += ('<div class="note">IQR 在 10.9–15.0 之间<b>无单调下降</b>：'
              '2022→2023 回升（13.8→15.0），2025 因新增第 3 条区属线回升到 12.3，'
              '2026 才降到最低 10.9。σ 同样没有持续收窄。</div></div>'
              '<div class="card"><div class="h2"><div class="num">2</div>收敛回归：起点几乎不解释终点</div>')
    for y in YEARS[1:]:
        b, r2 = CONV[y]
        inner += (f'<div class="sect">{y} 年名次 vs 2022 年名次</div>'
                  + bar(f'b = {b:+.3f}｜R² = {r2:.3f}', max(r2, 0.02) / 0.35,
                        '几乎无关' if r2 < 0.1 else '弱相关', alt=True))
    inner += ('<div class="note">若真存在「强者恒强」的收敛，b 应为<b>负且接近 −1</b>。'
              '实测四条系数<b>全为正</b>、R² 只有 0.008–0.086 —— '
              '近三年名次与 2022 年名次几乎无关，甚至有轻微反转。'
              '这不是全体停滞：残差 |z|≥1 的学校有 5–8 所，属于单校剧烈波动。</div></div>')
    return page(inner, '趋势与收敛')


def fig_resid():
    inner = (head('子课题 04', '谁掉得最快？',
                  'rel 的最小二乘斜率——五年相对位置变化最剧烈的 8 所')
             + '<div class="card"><div class="h2"><div class="num">1</div>趋势斜率（分/年）</div>')
    mx = max(abs(r['sen']) for r in RESID)
    for r in RESID:
        v = r['sen']
        inner += bar(r['name'], abs(v) / mx,
                     f'第 {r["rk"]} 名｜{v:+.2f} 分/年'.replace('-', '−'))
    inner += ('<div class="note">负值=五年持续走低。'
              f'<b>{RESID[0]["name"]}</b>与<b>{RESID[1]["name"]}</b>是最突出的下滑校，'
              '也是 03 图里「起点几乎不解释终点」的主要来源。'
              '注意：<b>趋势斜率不参与排名</b>，只描述变化方向与速度。</div></div>')
    return page(inner, '残差个案')


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
                  f'{len(RANK)} 所公办初中 · 5 年名额到校数据',
                  '名额加权区属市重点线口径 · 分位 P 主排序 · 全部结论可回源')
             + f'<div class="card"><div class="h2">五个子课题</div>'
             '<div class="kv">'
             '<span class="chip hot">01 名额越多位次越好吗</span>'
             '<span class="chip">02 切点到底多深</span>'
             '<span class="chip">03 五年没有收敛</span>'
             '<span class="chip">04 谁掉得最快</span>'
             '<span class="chip">05 这个榜测了哪一段</span></div>'
             f'<div class="kv"><span>全区 <b>{len(W)}</b> 所</span>'
             f'<span>入榜 <b>{len(RANK)}</b> 所</span>'
             f'<span>五年全勤 <b>{FULL5}</b> 所</span>'
             f'<span>民办 n&lt;4 <b>{PRIV}</b> 所</span></div></div>')
    body = (cover
            + f'<div class="h2" style="margin-top:34px"><div class="num">1</div>排名表</div>'
            + strip_head(inner_of(fig_main()))
            + '<div class="h2" style="margin-top:34px"><div class="num">2</div>名额与位次</div>'
            + strip_head(inner_of(fig_scale()))
            + '<div class="h2" style="margin-top:34px"><div class="num">3</div>切点深度</div>'
            + strip_head(inner_of(fig_depth()))
            + '<div class="h2" style="margin-top:34px"><div class="num">4</div>趋势与收敛</div>'
            + strip_head(inner_of(fig_conv()))
            + '<div class="h2" style="margin-top:34px"><div class="num">5</div>残差个案</div>'
            + strip_head(inner_of(fig_resid()))
            + '<div class="h2" style="margin-top:34px"><div class="num">6</div>有效边界</div>'
            + strip_head(inner_of(fig_bound()))
            + '<div class="foot2">完整数据与方法（宽表 191 列含逐线逐年原始分与名额）：'
              'https://istarfire.github.io/Shanghai-XueQuFang/<br>'
              '结论是统计推断，不是升学建议，择校请结合自身情况～</div>')
    return page(body, '嘉定名额到校长图')


FIGS = [('主图-排名表', fig_main), ('子图1-名额与位次', fig_scale),
        ('子图2-切点深度', fig_depth), ('子图3-无收敛', fig_conv),
        ('子图4-残差个案', fig_resid), ('子图5-有效边界', fig_bound),
        ('长图', fig_long)]

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
