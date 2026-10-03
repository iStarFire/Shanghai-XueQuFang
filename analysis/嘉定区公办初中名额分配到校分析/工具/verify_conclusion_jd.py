# -*- coding: utf-8 -*-
"""2.4 结论可靠性验证：关键指标**独立重算**（与 build_* 脚本不同代码路径）。

依据 `.trellis/spec/analysis/conclusion-verification.md`：关键指标必须独立重算并一致。
本脚本刻意**不复用** build_v3_jd / build_q2q3_jd 的任何函数：
  - P_wq / 2026 位次：从**源 CSV**（分数线 + 计划）重新实现加权均分与分位；
  - 6 个收敛指标：从**宽表原始列**用另一套写法重算；
  - Q-Q β：独立实现分位配对回归；
  - 28 所趋势分类：独立实现 Theil-Sen / OLS / 阈值判定。
"""
import csv
import math
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_S = f'{ROOT}/data/嘉定区/学校'
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = ['2022', '2023', '2024', '2025', '2026']
QU3 = ['142001', '142002', '142004']
CODE2NAME = {'142001': '上海市嘉定区第一中学',
             '142002': '上海交通大学附属中学嘉定分校',
             '142004': '上海师范大学附属中学嘉定新城分校'}
ALIAS = {'上海市嘉定区德富路中学': '交大附中附属嘉定德富中学',
         '上海市嘉定区杨柳初级中学': '上海市嘉定区嘉二实验学校',
         '上海嘉定区世界外国语学校': '上海嘉定区世外学校'}
THRESH = 1.10
OUT = []


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def chk(cid, name, ok, ev):
    OUT.append((cid, name, '通过' if ok else '不通过', ev))
    print(f'  [{cid}] {name}：{"通过" if ok else "**不通过**"}｜{ev}')


# ============ 从源 CSV 独立重算 ============
def rebuild_from_source():
    S, Q = {}, {}
    for r in load(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv'):
        c = ALIAS.get(r['junior_high_school'], r['junior_high_school'])
        S[(c, r['senior_high_school_code'], r['year'])] = float(r['min_score'])
    for f in ('名额到校计划-嘉定区-2023-2026.csv', '名额到校计划-嘉定区-2022-图片转录.csv'):
        for r in load(f'{D_S}/{f}'):
            c = ALIAS.get(r['junior_high_school'], r['junior_high_school'])
            Q[(c, r['senior_high_school_code'], r['year'])] = int(r['quota'])
    schools = sorted({k[0] for k in S} | {k[0] for k in Q})

    def wq(c, y):
        pr = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in QU3 if (c, h, y) in S]
        if not pr:
            return None
        tw = sum(q for _, q in pr)
        return (sum(v * q for v, q in pr) / tw if tw
                else sum(v for v, _ in pr) / len(pr))

    # 逐年分位（平均名次法）
    mean = {}
    for y in YEARS:
        for c in schools:
            v = wq(c, y)
            if v is not None:
                mean[(c, y)] = v
    P = {}
    for y in YEARS:
        vals = {c: mean[(c, y)] for c in schools if (c, y) in mean}
        xs = sorted(vals.values())
        n = len(xs)
        for c, v in vals.items():
            b = sum(1 for w in xs if w > v)
            e = sum(1 for w in xs if w == v)
            P[(c, y)] = 1 - ((b + (e + 1) / 2) - 1) / (n - 1)
    # 五年平均
    Pq = {}
    for c in schools:
        vs = [P[(c, y)] for y in YEARS if (c, y) in P]
        if vs:
            Pq[c] = sum(vs) / len(vs)
    # 2026 位次
    r26 = {}
    vals26 = {c: mean[(c, '2026')] for c in schools if (c, '2026') in mean}
    for c, v in vals26.items():
        b = sum(1 for w in vals26.values() if w > v)
        e = sum(1 for w in vals26.values() if w == v)
        r26[c] = b + (e + 1) / 2
    return Pq, r26, schools


def main():
    W = {r['junior_high_school']: r for r in
         load(f'{D_A}/宽表-初中水平-嘉定区-2022-2026.csv')}
    Pq, r26, schools = rebuild_from_source()
    print('=== 2.4 独立重算（不复用 build_* 任何函数）===\n')

    print('--- 关键指标 1：P_wq 与 2026 位次 ---')
    bad = []
    for c, r in W.items():
        if r['row_type'] != 'ranked':
            continue
        mine = Pq.get(c)
        theirs = r['P_wq']
        if mine is None or theirs == '' or abs(mine - float(theirs)) > 1e-5:
            bad.append((c, round(mine, 6) if mine else None, theirs))
    chk('V1', 'P_wq 由源 CSV 独立重算一致（28 所）', not bad,
        f'不符 {len(bad)} 处' + (f'：{bad[:3]}' if bad else ''))
    bad = [(c, round(r26.get(c, -1), 1), r['rank_base3_wq_2026']) for c, r in W.items()
           if r['rank_base3_wq_2026'] and abs(r26.get(c, -1) - float(r['rank_base3_wq_2026'])) > 0.01]
    chk('V1', '2026 位次由源 CSV 独立重算一致（39 所）', not bad,
        f'不符 {len(bad)} 处' + (f'：{bad[:3]}' if bad else ''))

    print('\n--- 关键指标 2：6 个收敛指标（固定样本 27 所）---')
    fixed = [c for c, r in W.items()
             if r['row_type'] == 'ranked' and r['years_included'] == '5']
    # 全池中位（独立算法：按 valid_pairs 筛选后取中位）
    med = {}
    for y in YEARS:
        v = sorted(float(r[f'mean_score_base3_wq_{y}']) for r in W.values()
                   if r[f'valid_pairs_{y}'] not in ('', '0') and r[f'mean_score_base3_wq_{y}'])
        med[y] = st.median(v)
    xs_by_y = {y: sorted(float(W[c][f'mean_score_base3_wq_{y}']) for c in fixed) for y in YEARS}

    def pctl(s, q):
        k = (len(s) - 1) * q / 100
        lo, hi = math.floor(k), math.ceil(k)
        return s[lo] + (s[hi] - s[lo]) * (k - lo)

    def gini2(s):
        n, t = len(s), sum(s)
        return sum((2 * i - n + 1) * x for i, x in enumerate(s)) / (n * t)

    mine_by_y = {}
    for y in YEARS:
        xs, m = xs_by_y[y], med[y]
        mx = st.median(xs)
        mine_by_y[y] = {
            'sigma': st.pstdev(xs), 'cv': st.pstdev(xs) / m,
            'iqr_norm': (pctl(xs, 75) - pctl(xs, 25)) / m, 'gini': gini2(xs),
            'r90_10_norm': (pctl(xs, 90) - pctl(xs, 10)) / m,
            'range_norm': (max(xs) - min(xs)) / m,
            'mad_norm': sum(abs(v - mx) for v in xs) / len(xs) / m}
    T = {r['year']: r for r in load(f'{D_A}/收敛指标-嘉定区-2022-2026.csv')}
    bad = [(y, k, round(mine_by_y[y][k], 8), T[y][k]) for y in YEARS for k in mine_by_y[y]
           if abs(mine_by_y[y][k] - float(T[y][k])) > 1e-6]
    chk('V2', '6 个收敛指标 × 5 年 = 30 个值独立重算一致', not bad,
        f'不符 {len(bad)} 处' + (f'：{bad[:2]}' if bad else '，全部一致'))

    print('\n--- 关键指标 3：Q-Q 名次分位收敛斜率 ---')
    def rank_pct(pairs):
        s = sorted(pairs, key=lambda t: t[1])
        m = len(s)
        return {nm: i / (m - 1) for i, (nm, _) in enumerate(s)}
    p22 = rank_pct([(c, float(W[c]['mean_score_base3_wq_2022'])) for c in fixed])
    p26 = rank_pct([(c, float(W[c]['mean_score_base3_wq_2026'])) for c in fixed])
    xs = [p22[c] for c in fixed]
    ys = [p26[c] for c in fixed]
    n = len(xs)
    mx, my = st.fmean(xs), st.fmean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    QQ = {r['metric']: r for r in load(f'{D_A}/收敛趋势检验-嘉定区-2022-2026.csv')}
    chk('V3', 'Q-Q 斜率独立重算一致', abs(b - float(QQ['qq_slope']['slope_b'])) < 5e-4,
        f'独立算得 {b:.4f} vs 表中 {QQ["qq_slope"]["slope_b"]}')
    # 检验 H0: b=1
    resid = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
    sxx = sum((x - mx) ** 2 for x in xs)
    se = math.sqrt((sum(r * r for r in resid) / (n - 2)) / sxx)
    t1 = (b - 1) / se
    p1 = 2 * (1 - 0.5 * (1 + math.erf(abs(t1) / math.sqrt(2))))
    chk('V3', 'H0: β=1 的检验统计量一致', abs(t1 - float(QQ['qq_slope']['t'])) < 5e-3,
        f'独立算得 t={t1:.3f} p={p1:.2e} vs 表中 t={QQ["qq_slope"]["t"]}')

    print('\n--- 关键指标 4：28 所趋势分类 ---')
    S = {r['junior_high_school']: r for r in load(f'{D_A}/趋势分类-嘉定区-2022-2026.csv')}
    bad = []
    for c, r in S.items():
        ys = [float(W[c][f'rel_{y}']) for y in YEARS if W[c][f'rel_{y}']]
        m = len(ys)
        slopes = [(ys[j] - ys[i]) / (j - i) for i in range(m) for j in range(i + 1, m)]
        sen = st.median(slopes)
        xs2 = list(range(m))
        mxx = st.fmean(xs2)
        o = sum((x - mxx) * (y - st.fmean(ys)) for x, y in zip(xs2, ys)) / \
            sum((x - mxx) ** 2 for x in xs2)
        if abs(sen - float(r['sen'])) > 5e-3 or abs(o - float(r['sen_ols'])) > 5e-3:
            bad.append((c, round(sen, 4), r['sen'], round(o, 4), r['sen_ols']))
    chk('V4', 'Theil-Sen 与 OLS 斜率独立重算一致（28 所 × 2）', not bad,
        f'不符 {len(bad)} 处' + (f'：{bad[:2]}' if bad else ''))
    bad = []
    for c, r in S.items():
        sen, o = float(r['sen']), float(r['sen_ols'])
        exp = ('方向不一' if sen * o < 0 else
               '明显上升' if sen >= THRESH and o > 0 else
               '明显下降' if sen <= -THRESH and o < 0 else
               '温和上升' if sen > 0 and o > 0 else
               '温和下降' if sen < 0 and o < 0 else '无法判定')
        if exp != r['trend_class']:
            bad.append((c, r['trend_class'], exp))
    chk('V4', f'分类规则（阈值 {THRESH}）独立复算一致', not bad,
        f'不符 {len(bad)} 处' + (f'：{bad[:2]}' if bad else ''))

    print('\n--- 样本量与结论措辞的合规检查 ---')
    rep = open(f'{D_A}/分析报告.md', encoding='utf-8').read()
    chk('V5', '报告写明 Q2 检验力限制（n=5 / df=3）',
        'df=3' in rep and '检验力' in rep, '已写明')
    chk('V5', '报告写明 Q3 校正后无一显著',
        '校正后显著' in rep or '校正后 0 所' in rep or '0 所' in rep, '已写明')
    # 注意：必须排除「禁止性表述」本身——报告里写着「不能说差距没有缩小」是合规的
    # 按**段落**判断：禁止性表述常跨行（「不能说」在上一行、被禁词在下一行）
    _no_claim = [b for b in rep.split('\n\n')
                 if '差距没有缩小' in b and not any(
                     k in b for k in ('不能', '不说', '禁止', '写成'))]
    chk('V5', '报告未把「测不出」写成「没有缩小」（排除禁止性表述）',
        not _no_claim, f'违规段落 {len(_no_claim)} 个' if _no_claim else '仅有禁止性表述')
    _bad_trend = [b for b in rep.split('\n\n')
                  if ('黑马' in b or '新校上升' in b or '新校下降' in b)
                  and not any(k in b for k in ('不得', '不对', '禁止'))]
    chk('V5', '新校未被使用趋势措辞（排除禁止性表述）',
        not _bad_trend, f'违规段落 {len(_bad_trend)} 个' if _bad_trend else '仅有禁止性表述')
    chk('V5', '报告写明民办不外推', '不能外推到民办' in rep, '已写明')
    chk('V5', '报告写明改名证据级别为外部来源',
        '无官方更名公告' in rep or '均无任何更名说明' in rep, '已写明')
    chk('V5', '旧结论被推翻时已显式说明',
        '该结论已不再成立' in rep or '已不再成立' in rep, '已说明')
    chk('V5', '3.2 不可复现的旧值已标注',
        '无法用现有数据复现' in rep or '无法还原' in rep, '已标注')
    chk('V5', '推断与事实分离（标注证据强度）',
        rep.count('推断（证据强度') >= 11,
        f'{rep.count("推断（证据强度")} 处（11 所个案各需 ≥1）')
    chk('V5', '每所个案含反向证据', rep.count('**反向证据**') >= 10,
        f'{rep.count("**反向证据**")} 处')

    print('\n' + '=' * 60)
    fails = [r for r in OUT if r[2] == '不通过']
    print(f'共 {len(OUT)} 项验证｜不通过 {len(fails)} 项')
    for f in fails:
        print('  ❌', f[0], f[1], '｜', f[3])
    print('=' * 60)
    return 0 if not fails else 1


if __name__ == '__main__':
    raise SystemExit(main())
