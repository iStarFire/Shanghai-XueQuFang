"""第 5 章补充：5.4 用户指定专题 —— 梅陇中学为何综合第 6。

独立脚本（不改 build_ch5_pt.py）：生成 5.4 并插入到第 5 章末尾（附录 A 之前）。

⚠️ 方法论声明：梅陇主口径第 6 名，**不在预注册的 11 所之内**。本节应读者要求补充，
**不改变 5.1–5.3 的预注册选人标准** —— 这一点必须写在节首，否则就成了事后挑人。

分析内容：
  5.4.1 三口径分项定位失分点（尾部）+ 四条线均名对比
  5.4.2 排除宜川线的三线敏感性，并说明名次变化是**双向**的
"""
import csv
import re
import statistics as st
from pathlib import Path

D = Path('.')
YEARS = ['2022', '2023', '2024', '2025', '2026']
L4 = ['华二普陀', '二中', '晋元', '宜川']
L3 = ['华二普陀', '二中', '晋元']
ML = '上海市梅陇中学'


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


W = {r['junior_high_school']: r for r in load(D / '宽表-初中水平-普陀区-2022-2026.csv')}
T = {r['junior_high_school']: r for r in load(D / '趋势分类-普陀区-2022-2026.csv')}
RANKED = sorted((r for r in W.values() if r['row_type'] == 'ranked'),
                key=lambda r: int(r['rank_P_wq_comb']))
NAMES = [r['junior_high_school'] for r in RANKED]


def sh(n):
    return n.replace('上海市', '').replace('上海', '')


def wm(c, y, lines):
    """名额加权均分（只取有分数的线）。"""
    pr = [(float(W[c][f'score_{l}_{y}']), int(W[c][f'quota_{l}_{y}'] or 0))
          for l in lines if W[c].get(f'score_{l}_{y}') not in ('', None)]
    if not pr:
        return None
    tw = sum(q for _, q in pr)
    return sum(v * q for v, q in pr) / tw if tw > 0 else st.fmean([v for v, _ in pr])


def pct_rank(vals, v):
    """平均秩：比它强的个数 + (并列数+1)/2。"""
    return sum(1 for w in vals if w > v) + (sum(1 for w in vals if w == v) + 1) / 2


def rank_tie(pairs):
    xs = sorted(v for _, v in pairs)
    return {c: sum(1 for w in xs if w > v) + (sum(1 for w in xs if w == v) + 1) / 2
            for c, v in pairs}


# ---- 三线口径的 P 与名次 ----
P3 = {}
for c in NAMES:
    ps = []
    for y in YEARS:
        pool = {k: v for k, v in ((c2, wm(c2, y, L3)) for c2 in NAMES) if v is not None}
        v = wm(c, y, L3)
        if v is None or len(pool) < 2:
            continue
        ps.append(1 - (pct_rank(list(pool.values()), v) - 1) / (len(pool) - 1))
    if len(ps) >= 4:
        P3[c] = st.fmean(ps)
S3 = sorted(P3, key=lambda k: -P3[k])
r4 = {r['junior_high_school']: int(r['rank_P_wq_comb']) for r in RANKED}

# ---- 断言（专题叙述依赖这些事实，不符即显式失败）----
assert len(S3) == 32, f'三线池应 32 所，实际 {len(S3)}'
assert ML in P3, '梅陇无三线 P'
_ml3 = S3.index(ML) + 1
assert _ml3 == 5, f'梅陇三线名次为 {_ml3}，专题叙述按第 5 撰写，需同步更新文案'
assert r4[ML] == 6, f'梅陇四线名次为 {r4[ML]}，专题叙述按第 6 撰写'
_rb = RANKED[4]['junior_high_school']
assert _rb == '上海市真北中学', f'第 5 名已变为 {_rb}，专题对比对象需更新'
_gap = float(RANKED[4]['P_wq_comb']) - float(W[ML]['P_wq_comb'])
assert abs(_gap - 0.0067) < 5e-4, f'梅陇与真北综合差为 {_gap:.4f}，文案写 0.0067'
_tgap = float(RANKED[4]['P_wq_tail']) - float(W[ML]['P_wq_tail'])
assert abs(_tgap - 0.0638) < 5e-4, f'P尾部差为 {_tgap:.4f}，文案写 0.0638'

# ---- 各线均名（用于断言文案里的 9.3/8.8/12.2/22.3）----
per4 = {l: {y: rank_tie([(c, float(W[c][f'score_{l}_{y}'])) for c in W
                          if W[c].get(f'score_{l}_{y}') not in ('', None)])
            for y in YEARS} for l in L4}
ML_RANK = {l: st.fmean([per4[l][y][ML] for y in YEARS]) for l in L4}
for l, v in (('华二普陀', 9.3), ('二中', 8.8), ('晋元', 12.2), ('宜川', 22.3)):
    assert abs(ML_RANK[l] - v) < 0.06, f'梅陇 {l} 均名 {ML_RANK[l]:.1f}，文案写 {v}'
_top5_宜川 = [st.fmean([per4['宜川'][y][c] for y in YEARS])
              for c in NAMES[:5]]
assert min(_top5_宜川) >= 8.0 and max(_top5_宜川) <= 15.1, \
    f'前 5 强宜川均名区间 {min(_top5_宜川):.1f}–{max(_top5_宜川):.1f}，文案写 8.1–15.0'
assert ML_RANK['宜川'] > max(_top5_宜川), '梅陇宜川均名并非前 6 名中最差'

L = []
L.append('### 5.4 用户指定专题：梅陇中学（为何综合第 6，而非第 1 梯队）')
L.append('')
L.append('> ⚠️ **本节不是预注册入选**。梅陇主口径第 6 名，不在 5.1–5.3 的 11 所之内；')
L.append('> 本节应读者要求补充，**不改变预注册的选人标准** —— 写明这一点是为了避免「事后挑人」。')
L.append('')
w = W[ML]
q5 = st.fmean([float(w[f'quota4_{y}']) for y in YEARS])
L.append(f"**{sh(ML)}**｜主口径第 {r4[ML]} 名｜`{T[ML]['trend_class']}`｜"
         f"区属 4 线名额五年均 **{q5:.1f} 个（全区第 1）**")
L.append('')

L.append('#### 5.4.1 三口径分项：失分点完全在「尾部」')
L.append('')
L.append('综合口径 = (P全身 + P头部 + P尾部) / 3。头部 6 名的分项：')
L.append('')
L.append('| 学校 | P全身 | 全身名 | P头部 | 头名 | P尾部 | **尾名** | 综合 |')
L.append('|---|---|---|---|---|---|---|---|')
for r in RANKED[:6]:
    n = r['junior_high_school']
    mk = ' ←' if n == ML else ''
    L.append(f"| {sh(n)}{mk} | {float(r['P_wq_all']):.4f} | {r['rank_P_wq_all']} "
             f"| {float(r['P_wq_head']):.4f} | {r['rank_P_wq_head']} "
             f"| {float(r['P_wq_tail']):.4f} | {r['rank_P_wq_tail']} "
             f"| {float(r['P_wq_comb']):.4f} |")
L.append('')
L.append(f"- **事实**：梅陇与真北的综合差仅 **{_gap:.4f}**"
         f"（{float(w['P_wq_comb']):.4f} vs {float(RANKED[4]['P_wq_comb']):.4f}），"
         f"而两者 **P尾部 差 {_tgap:.4f}**（{float(w['P_wq_tail']):.4f} vs "
         f"{float(RANKED[4]['P_wq_tail']):.4f}）。"
         f"P全身 梅陇 {float(w['P_wq_all']):.4f} 与真北 {float(RANKED[4]['P_wq_all']):.4f} "
         f"几乎并列，**P头部 梅陇第 {w['rank_P_wq_head']} 明显强于真北第 "
         f"{RANKED[4]['rank_P_wq_head']}**。")
L.append('')
L.append('**四条线的五年均名（当年线内位次，跨年平均）**：')
L.append('')
L.append('| 学校 | 华二普陀 | 二中 | 晋元 | **宜川** |')
L.append('|---|---|---|---|---|')
for n in NAMES[:5] + [ML]:
    cells = ' | '.join(f"{st.fmean([per4[l][y][n] for y in YEARS]):.1f}" for l in L4)
    mk = ' ←' if n == ML else ''
    L.append(f"| {sh(n)}{mk} | {cells} |")
L.append('')
L.append(f'- **事实**：梅陇在**华二普陀、二中、晋元三线均位居前列**'
         f"（{ML_RANK['华二普陀']:.1f} / {ML_RANK['二中']:.1f} / {ML_RANK['晋元']:.1f}），"
         f"**唯独宜川线 {ML_RANK['宜川']:.1f}，是前 6 名中最差**"
         f"（其余 5 校为 {min(_top5_宜川):.1f}–{max(_top5_宜川):.1f}）。"
         f"「尾部口径」主要由**门槛最低的宜川线**构成 ⇒ P尾部 被直接拉低。")
_q = {l: sum(int(w[f'quota_{l}_{y}'] or 0) for y in YEARS) for l in L4}
_tot = sum(_q.values())
L.append('')
L.append('**各线名额（梅陇，五年合计）**：' + '、'.join(
    f"{l} {_q[l]} 个（占本校批次 {_q[l] / _tot * 100:.1f}%）" for l in L4)
    + f'；四线合计 {_tot} 个。')
L.append('')
L.append('> 注意：宜川线给梅陇的名额（93）与二中、晋元几乎一样多，'
         '**但那条线上的录取分最低** —— 名额多不必然带来更高的分数。')
L.append('')

L.append('#### 5.4.2 口径敏感性：排除宜川线后梅陇升至第 5')
L.append('')
L.append('用 **华二普陀 + 二中 + 晋元** 三线重算（当年三线有分数的公办校池内排名，跨年等权）：')
L.append('')
L.append('| 名次 | 学校 | 三线 P | 四线综合名次 | 变化 |')
L.append('|---|---|---|---|---|')
for i, c in enumerate(S3[:6], 1):
    d = r4[c] - i
    mk = ' ←' if c == ML else ''
    L.append(f"| {i} | {sh(c)}{mk} | {P3[c]:.4f} | {r4[c]} | {d:+d} |")
L.append('')
_rz5 = NAMES[4]
L.append(f'- **事实**：**梅陇由第 {r4[ML]} 升至第 {_ml3}**，是前 {_ml3} 中唯一「上升」的学校；'
         f'{sh(_rz5)}由第 {r4[_rz5]} 降至第 {S3.index(_rz5) + 1}。'
         f'梅陇三线 P = **{P3[ML]:.4f}**。')
L.append('')
L.append('**逐年位次（当年池内）**：')
L.append('')
L.append('| 年 | 三线均分 | 三线位次 | 四线均分 | 四线位次 |')
L.append('|---|---|---|---|---|')
for y in YEARS:
    p3, p4 = wm(ML, y, L3), wm(ML, y, L4)
    pool3 = {k: v for k, v in ((c, wm(c, y, L3)) for c in NAMES) if v is not None}
    pool4 = {k: v for k, v in ((c, wm(c, y, L4)) for c in NAMES) if v is not None}
    L.append(f"| {y} | {p3:.1f} | {pct_rank(list(pool3.values()), p3):.0f}/{len(pool3)} "
             f"| {p4:.1f} | {pct_rank(list(pool4.values()), p4):.0f}/{len(pool4)} |")
L.append('')
L.append('⚠️ **但这不是「排除宜川就更公平」**：口径切换同时改变所有人的分数与池子，'
         '名次变化是**双向**的 ——')
L.append('')
ch = sorted(((c, r4[c] - (S3.index(c) + 1)) for c in S3), key=lambda t: -t[1])
L.append('| 上升最多 | 位次 | 下降最多 | 位次 |')
L.append('|---|---|---|---|')
for i in range(3):
    a, da = ch[i]
    b, db = ch[-(i + 1)]
    L.append(f"| {sh(a)} | {r4[a]} → {S3.index(a) + 1}（{da:+d}） "
             f"| {sh(b)} | {r4[b]} → {S3.index(b) + 1}（{db:+d}） |")
L.append('')
_moved = abs(ch[0][1])
L.append(f'- **推断（证据强度：高）**：「谁是第一梯队」在四线 / 三线之间**并不稳健**。'
         f'梅陇与真北的综合差仅 {_gap:.4f}，**小于口径切换带来的最大扰动'
         f'（{_moved} 位）**。因此**不能把「第 {r4[ML]} 名」或「第 {_ml3} 名」当作确定结论**；'
         f'能确定的只有结构性事实 —— 梅陇**顶端厚、底端薄**'
         f'（头名 {w["rank_P_wq_head"]}、尾名 {w["rank_P_wq_tail"]}，跨度 '
         f'{int(w["rank_P_wq_tail"]) - int(w["rank_P_wq_head"])} 位），'
         f'在任何含低门槛线的等权综合口径下都会被压低。')
L.append('')
L.append('**反向证据**：即便按三线口径，梅陇也只到第 5，'
         '且 2024 年三线位次仅 15（三线均分 737.3，低于 2022 年的 9）。'
         '**「排除一条线就进第一梯队」本身说明该结论对口径过于敏感**，'
         '不足以支撑「梅陇属于第一梯队」的强主张。')
L.append('')
L.append('---')
L.append('')

NEW = '\n'.join(L)
assert 'None' not in NEW and 'nan' not in NEW
assert NEW.count('| 2022 |') == 1, '专题逐年表应 1 个'
assert NEW.count('**反向证据**：') == 1
assert NEW.count('**推断（证据强度：') == 1

# ---- 插入到第 5 章末尾（附录 A 之前）----
REPORT = D / '分析报告.md'
s = REPORT.read_text(encoding='utf-8')
# 幂等：若 5.4 已存在（由 build_ch5_pt.py 保留），**先摘除再插入**，而不是拒绝重跑。
_m54 = re.search(r'^### 5\.4 .*$', s, re.M)
if _m54:
    _sep = chr(10) + '---' + chr(10)
    _end = s.index(_sep, _m54.start()) + len(_sep)
    s = s[:_m54.start()] + s[_end:]
    s = re.sub(r'\n{3,}', chr(10) * 2, s)
m6 = re.search(r'^## 附录 A .*$', s, re.M)
assert m6, '未找到附录 A 标题'
assert '### 5.4 用户指定专题' not in s, '摘除后 5.4 仍存在'
out = s[:m6.start()] + NEW + '\n' + s[m6.start():]
assert len(out) > len(s)
REPORT.write_text(out, encoding='utf-8')
print('5.4 用户指定专题（梅陇）已' + ('更新' if _m54 else '插入'))
print(f'  四线综合第 {r4[ML]} → 三线第 {_ml3}（P3={P3[ML]:.4f}，真北第 {S3.index(_rz5) + 1}）')
print(f'  与真北综合差 {_gap:.4f}，P尾部差 {_tgap:.4f}')
print(f'  报告 {len(s)} → {len(out)} 字符')
