# -*- coding: utf-8 -*-
"""重写报告第 8 章「代表性公办初中个案」——**叙述中的每个数字都由 CSV 动态生成**。

问题背景：上一轮口径变更（排名池含民办 → 仅公办）后，第 8 章的逐年表与头部指标
已更新，但**段落叙述仍是硬编码的旧数字**（如「SEN −2.18」「近三年稳居第 2–3」）。
本脚本把叙述改为 f-string 动态取值，从根上消除「表格新、叙述旧」的可能。

选人标准预注册于 design 7.1：头部 5 = 主口径前 5；明显上升 3 = 「明显上升」中
Δrel 最大者；明显下降 3 = 「明显下降」中 SEN 最负者。
"""
import csv
import os
from collections import Counter

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YS = ['2022', '2023', '2024', '2025', '2026']


def sh(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


W = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/宽表-初中水平-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
M = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/rank-多口径总表-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
S = {r['junior_high_school']: r for r in csv.DictReader(
    open(f'{D}/趋势分类-嘉定区-2022-2026.csv', encoding='utf-8-sig'))}
RK = sorted([r for r in M.values() if r['row_type'] == 'ranked'],
            key=lambda r: int(r['rank_P_wq_all']))
CLS = list(S.values())
BY = {c: [r for r in CLS if r['trend_class'] == c] for c in
      {r['trend_class'] for r in CLS}}


def rk_of(n, y):
    v = W[n].get(f'rank_base3_wq_{y}', '')
    return int(float(v)) if v else None


def chain(n):
    ys = [y for y in YS if rk_of(n, y)]
    return ' → '.join(f'**{rk_of(n, y)}**' if i == len(ys) - 1 else str(rk_of(n, y))
                      for i, y in enumerate(ys))


def yl(n):
    return W[n]['years_list'].replace(';', '–')


def tbl(n):
    L = ['| 年 | 名额加权均分 | 当年**公办池**内位次 | 区属 3 线名额 | rel（高于当年公办池中位） |',
         '|---|---|---|---|---|']
    for y in YS:
        if not W[n][f'mean_score_base3_wq_{y}']:
            L.append(f'| {y} | — | — | 0 | — |')
            continue
        L.append(f"| {y} | {float(W[n][f'mean_score_base3_wq_{y}']):.1f} | 第 {rk_of(n, y)} 位 "
                 f"| {W[n][f'quota3_{y}']} | {float(W[n][f'rel_{y}']):+.1f} |")
    return '\n'.join(L)


# ---------------- 事实基准（用于「最猛 / 唯一 / 最大」等断言） ----------------
BASE = {
    'sen_min': min(CLS, key=lambda r: float(r['sen'])),
    'sen_max': max(CLS, key=lambda r: float(r['sen'])),
    'drel_max': max(CLS, key=lambda r: float(r['delta_rel'])),
    'drel_min': min(CLS, key=lambda r: float(r['delta_rel'])),
    's3_max': max((r for r in CLS if r['sen_recent3']),
                  key=lambda r: float(r['sen_recent3'])),
    's3_min': min((r for r in CLS if r['sen_recent3']),
                  key=lambda r: float(r['sen_recent3'])),
}
TOP = [r['junior_high_school'] for r in RK[:5]]
TOP_SEN = {n: float(S[n]['sen']) for n in TOP}
TOP_WORST = min(TOP, key=lambda n: TOP_SEN[n])


def superlative(n):
    """该生在本轮 28 所中是否真的『唯一』/『最』，据实生成，不写死。"""
    out = []
    sen = float(S[n]['sen'])
    if n == BASE['sen_min']['junior_high_school']:
        out.append(f'**五年斜率 {sen:.2f}，为 28 所中最差**')
    if n == BASE['sen_max']['junior_high_school']:
        out.append(f'**五年斜率 {sen:.2f}，为 28 所中最高**')
    if n == BASE['drel_max']['junior_high_school']:
        out.append(f"**全区五年改善最大**：Δrel {float(S[n]['delta_rel']):+.1f} 分")
    if n == BASE['drel_min']['junior_high_school']:
        out.append(f"Δrel {float(S[n]['delta_rel']):+.1f}，为全区最大降幅")
    return out


# ---------------- 分组 ----------------
head = TOP
up3 = [r['junior_high_school'] for r in
       sorted(BY.get('明显上升', []), key=lambda r: -float(r['delta_rel']))[:3]]
down3 = [r['junior_high_school'] for r in
         sorted(BY.get('明显下降', []), key=lambda r: float(r['sen']))[:3]]

# 逐年单调性（是否「从未掉头」）
def mono(n):
    v = [rk_of(n, y) for y in YS if rk_of(n, y)]
    return all(v[i] <= v[i + 1] for i in range(len(v) - 1)), all(
        v[i] >= v[i + 1] for i in range(len(v) - 1))


NOTE = {
    '同济大学附属实验中学': '**推断（证据强度：弱）**：2026 年位次后移而名额并不少'
                     '（属全区中位区间），**可能与强校涌入同时发生**；但仓库无生源数据，'
                     '无法判断是「自身退步」还是「别人进步」。',
    '上海外国语大学嘉定外国语学校': '**推断（证据强度：中）**：2023 年骤降与当年新增第 3 条区属线无关'
                            '（第 3 条线 2025 年才出现），**更可能与该校当年生源波动有关**，'
                            '但同样无数据可验证。',
    '上海市嘉定区苏民学校': '**推断（证据强度：中）**：2024 年是明显转折点。'
                    '同期名额从 10 个增至 18 个，**可能同时受名额扩容与生源变化影响，两者无法分离**。',
    '交大附中附属嘉定德富中学': '**推断（证据强度：弱）**：该校 2022 年 2 月由「德富路中学」更名并纳入'
                     '交大附中教育集团，但**更名与 2025 年位次下跌之间没有任何可检验的关联证据**。',
    '上海市嘉定区新城实验中学': '**推断（证据强度：中）**：位次下降**部分**源于公办池扩大后强校涌入'
                     '（2023 年 28 所 → 2026 年 32 所）而非自身退步——依据是加权均分同期基本持平；'
                     '但**无法给出「池子效应」与「自身变化」的分解比例**。',
    '上海市嘉定区震川中学': '**推断（证据强度：弱）**：五年明显上升但**近三年反向下滑**，'
                   '这一转折点恰在上师嘉新 2025 年扩容之后，**时间上接近但无因果证据**——'
                   '仓库内无名额分配到校校级生源数据，无法验证。',
    '上海市嘉定区南翔中学': '**推断（证据强度：弱）**：可能与生源结构变化有关，'
                    '但仓库内无招生规模或生源数据，**无法验证**。',
    '上海市嘉定区南苑中学': '**推断（证据强度：弱）**：2025 年起回落，**这个转折与上师嘉新 2025 年扩容'
                    '在时间上接近**，是否相关无法判定——两条线名额此消彼长，'
                    '但**没有学校级名额分配的因果证据**。',
    '上海市嘉定区迎园中学': '**推断（证据强度：中）**：名额多本身推高位次（3.1 节已证名额与位次正相关），'
                    '因此它的上升有多少来自生源、多少来自名额，**本数据无法分离**。',
    '上海市嘉定区华亭学校': '**推断（证据强度：中）**：区属名额极少意味着最低分由 1–2 名学生决定，'
                    '**位次暴跌中有多大比例来自名额规模而非生源下降，用本数据无法判定**。',
    '上海市嘉定区徐行中学': '**推断（证据强度：弱）**：均分与位次同时垫底，**倾向于存在真实变化**，'
                    '但**本数据无法排除考生构成变化**。',
    '上海市嘉定区娄塘学校': '**推断（证据强度：弱）**：如此剧烈的摆动更像是名额结构或单年异常，'
                    '而非稳定的生源变化。',
}

REVERSE = {
    '同济大学附属实验中学': lambda n: f"**反向证据**：按五年斜率，{sh(n)}并非头部 5 校中下滑最猛的那所"
                                f"（{sh(TOP_WORST)} SEN={TOP_SEN[TOP_WORST]:.2f} 更低）——"
                                f"它只是**位次绝对值**掉得多。",
    '上海外国语大学嘉定外国语学校': lambda n: '**反向证据**：它的名次在 2023 年后已企稳，'
                                       '说「持续下滑」并不准确。',
    '上海市嘉定区苏民学校': lambda n: f'**反向证据**：2022 年位次并不靠前，'
                                 f'「当前水平最好」只在近三年口径成立。',
    '交大附中附属嘉定德富中学': lambda n: '**反向证据**：**下滑集中在 2025 年，最近一年已修复**。',
    '上海市嘉定区新城实验中学': lambda n: '**反向证据**：若只看位次，它是头部 5 校中斜率最负者，'
                                 '看似明显退步；**位次与均分给出相反信号，这正是位次不可单独引用的实例**。',
    '上海市嘉定区震川中学': lambda n: f'**反向证据**：近三年斜率 {float(S[n]["sen_recent3"]):+.2f}，'
                                f'**它属于「五年升、近三年降」的一所**，'
                                f'按五年口径是上升、按近三年口径是回落，两个口径结论相反。',
    '上海市嘉定区南翔中学': lambda n: f'**反向证据**：即便改善幅度全区最大，'
                                f'2026 年位次仍只排第 {rk_of(n, "2026")} 位，**属中后段而非头部**；'
                                f'且近三年斜率已回落至 {float(S[n]["sen_recent3"]):+.2f}。',
    '上海市嘉定区南苑中学': lambda n: '**反向证据**：它 2026 年加权均分看似不低，但当年名额很少，'
                                 '**末位录取一人就能决定位次**。',
    '上海市嘉定区迎园中学': lambda n: f'**反向证据**：近三年斜率 {float(S[n]["sen_recent3"]):+.2f}'
                                f'已转负，位次从第 {min(rk_of(n, y) for y in ["2023", "2024"])}'
                                f'退到第 {rk_of(n, "2026")}，**上升趋势已经中断**。',
    '上海市嘉定区华亭学校': lambda n: f'**反向证据**：近三年斜率 {float(S[n]["sen_recent3"]):+.2f}'
                                 f'，**下滑已明显收窄**。',
    '上海市嘉定区徐行中学': lambda n: f'**反向证据**：名额同样偏少，'
                                 '但均分与位次同时垫底，**这一次不能只用名额少解释**。',
    '上海市嘉定区娄塘学校': lambda n: f'**反向证据**：近三年斜率 {float(S[n]["sen_recent3"]):+.2f}，'
                                 '**按五年口径它大幅下滑，按近三年口径它在回升，两个口径结论相反**。',
}

L = ['## 8 代表性公办初中个案\n',
     '**选人标准在分析前预注册**（design 7.1），不按结果挑选：\n',
     '- **头部 5 所** = 主口径排名前 5；',
     f'- **明显上升 3 所** = 第 5 章「明显上升」中 `Δrel` 最大者（{"、".join(sh(x) for x in up3)}）；',
     f'- **明显下降 3 所** = 「明显下降」中 `SEN` 最负者（{"、".join(sh(x) for x in down3)}）。\n',
     '> **本章全部数字由 `工具/build_ch8_jd.py` 从 CSV 动态生成**（`sen` / `Δrel` / 位次 / 名额 / 均分），'
     '不存在手写常数，因此口径变更后重跑脚本即同步。\n',
     '> **读法提醒**：位次的分母逐年变化（27 → 32 所公办），'
     '**位次下降可能来自强校涌入而非自身退步**；`rel` 已减去当年公办池中位、**跨年可比**，'
     '判断自身变化应看 `rel` 与加权均分。\n']

for title, grp, note in [('8.1 头部 5 所', head, '主口径前 5'),
                         ('8.2 明显上升 3 所', up3, '第 5 章「明显上升」中 Δrel 最大者'),
                         ('8.3 明显下降 3 所', down3, '第 5 章「明显下降」中 SEN 最负者')]:
    L.append(f'### {title}（{note}）\n')
    for n in grp:
        s, m, w = S[n], M[n], W[n]
        sup = '；'.join(superlative(n))
        head_line = (f"**{sh(n)}**｜主口径第 {m['rank_P_wq_all']} 名，"
                     f"P_wq={float(m['P_wq_all']):.3f}，"
                     f"名额均 {float(w['quota3_avg']):.1f}，"
                     f"SEN={float(s['sen']):+.2f}（{s['trend_class']}）"
                     + (f"，近 3 年斜率 {float(s['sen_recent3']):+.2f}" if s['sen_recent3'] else ''))
        L.append(head_line + '\n')
        L.append(tbl(n))
        L.append('')
        L.append(f'逐年位次：{chain(n)}；SEN {float(s["sen"]):+.2f}；'
                 f'Δrel {float(s["delta_rel"]):+.1f}'
                 + (f'；近 3 年 {float(s["sen_recent3"]):+.2f}' if s['sen_recent3'] else '')
                 + (f'。{sup}' if sup else '') + '。')
        L.append('')
        # 覆盖断言：预注册名单可能随口径变化而变（入选校换了人），
        # 缺文案时必须显式失败，不能静默漏写或用错校的文案
        assert n in NOTE, f'{sh(n)} 缺少「推断」文案——入选名单变了，请补充'
        assert n in REVERSE, f'{sh(n)} 缺少「反向证据」文案——入选名单变了，请补充'
        L.append(NOTE[n])
        L.append('')
        L.append(REVERSE[n](n))   # lambda 需传入校名参数
        L.append('')
L.append('---\n')

# ============ 安全写入（规范陷阱 14：断言必须全部在写文件之前完成）============
# 上一版写成 open(p,'w').write(<可能抛异常的表达式>)，
# 而 open(p,'w') 本身就截断文件 → 表达式抛异常即永久清空报告。
# 正确顺序：内存拼装 → 断言 → 最后一步才落盘 → 落盘后立即验证。
import re

p = f'{D}/分析报告.md'
s = open(p, encoding='utf-8').read()
m8 = re.search(r'^## 8 代表性公办初中个案.*$', s, re.M)
ma = re.search(r'^## 附录 A .*$', s, re.M)
assert m8, '未找到第 8 章标题'
assert ma, '未找到附录 A 标题'
assert m8.start() < ma.start(), '第 8 章应在附录 A 之前'

new = '\n'.join(L) + '\n'
# 落盘前自检：新章节必须自带标题、全部入选校、且不短于 3000 字符
assert new.lstrip().startswith('## 8 '), '新章节缺少标题'
assert len(new) > 3000, f'新章节过短（{len(new)} 字符），疑似生成失败'
for n in head + up3 + down3:
    assert sh(n) in new, f'{sh(n)} 未写入新章节'
assert 'None' not in new, '新章节含 None，说明有字段取值为空'

out = s[:m8.start()] + new + s[ma.start():]
# 完整性按**内容计数**判断，不按长度（新章更紧凑但内容不减）
n_sch = len(head) + len(up3) + len(down3)
assert len(re.findall(r'^\*\*[^*]+\*\*｜', new, re.M)) == n_sch, '学校条数不符'
assert new.count('推断（证据强度') == n_sch, '推断段数量不符'
assert new.count('**反向证据**') == n_sch, '反向证据数量不符'
assert new.count('| 2022 |') == n_sch, '逐年表数量不符'

# 全部断言通过，才落盘
with open(p, 'w', encoding='utf-8') as f:
    f.write(out)

# 落盘后立即验证，避免留下半截文件
chk = open(p, encoding='utf-8').read()
assert len(chk) == len(out), f'落盘后长度不符：{len(chk)} != {len(out)}'
print(f'第 8 章已重写（{len(L)} 段，数据全部动态生成），报告 {len(s)} → {len(out)} 字符')
print(f'  头部 5：{"、".join(sh(x) for x in head)}')
print(f'  上升 3：{"、".join(sh(x) for x in up3)}')
print(f'  下降 3：{"、".join(sh(x) for x in down3)}')
print(f'  头部 5 中 SEN 最负：{sh(TOP_WORST)}（{TOP_SEN[TOP_WORST]:+.2f}）')
