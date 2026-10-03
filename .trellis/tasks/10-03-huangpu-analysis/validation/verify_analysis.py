#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦分析 2.4 结论可靠性门禁（9 段）。用法：python3 verify_analysis.py"""
import csv
import os
import statistics as st
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/工具')
from hp_core import (A, YEARS, PRIV, compute, dispersion, ols_slope,
                     pct_rank, load, build_pairs, wmean)

WIDE = f'{A}/宽表-初中水平-黄浦区-2022-2026.csv'
RPT = f'{A}/分析报告.md'
FILES = {'排序表': '排序表-名额分配到校-黄浦区-2022-2026.csv',
         '多口径': 'rank-多口径总表-黄浦区-2022-2026.csv',
         '加权敏感性': 'rank-加权敏感性-黄浦区-2022-2026.csv',
         '趋势': '趋势分析-黄浦区-2022-2026.csv',
         '收敛': '收敛分析-黄浦区-2022-2026.csv',
         '单线': '单线视角-黄浦区-2022-2026.csv'}
PRIV5 = ['上海市民办明珠中学', '上海市民办立达中学', '上海市震旦外国语中学',
         '上海康德双语实验学校', '上海民办永昌学校']
BAN = ['普陀', '徐汇', '其他区', '异地']
FAILS, N = [], 0


def ck(name, got, want):
    global N
    N += 1
    ok = got == want
    if not ok:
        FAILS.append(name)
    print(f"  [{'过' if ok else '不过'}] {name}: {got}" + ('' if ok else f'（应 {want}）'))


def main():
    R = compute()
    P5, POOL_Y, WQ = R['P5'], R['POOL_Y'], R['WQ']
    with open(WIDE, encoding='utf-8-sig') as f:
        W = list(csv.DictReader(f))
    Wd = {r['junior_high_school']: r for r in W}
    xs = [float(y) for y in YEARS]

    print('\n=== [1] 池正确性 ===')
    ck('逐年池 n', [len(POOL_Y[y]) for y in YEARS], [18, 18, 18, 17, 17])
    ck('民办行数（须 0）', sum(1 for r in W if PRIV(r['junior_high_school'])), 0)
    ck('ownership 全为公办', sorted({r['ownership'] for r in W}), ['公办'])
    ck('五年池 n', len(P5), 17)
    ck('三年池 n', len(R['P3']), 18)
    ck('仅三年学校', R['HIST'], ['上海市黄浦学校'])
    ck('黄浦学校 in_pool5=0', Wd['上海市黄浦学校']['in_pool5'], '0')
    ck('黄浦学校 n_years=3', Wd['上海市黄浦学校']['n_years'], '3')
    ck('大同断点标记=1', Wd['上海市大同初级中学']['structural_break_2024'], '1')
    ck('五年全勤校 n_years 均为 5', sum(1 for c in P5 if Wd[c]['n_years'] == '5'), 17)

    print('\n=== [2] 宽表自洽（从原始 CSV 独立重算）===')
    S, Q = load()
    pairs, _ = build_pairs(S, Q)
    mx = 0.0
    for c in R['gov']:
        for y in YEARS:
            w = wmean(pairs, y, c, True)[0]
            got = Wd[c][f'wq_{y}']
            if w is None:
                if got != '':
                    FAILS.append(f'{c} {y} 应为空')
            else:
                mx = max(mx, abs(w - float(got)))
    # 宽表数值列统一保留 4 位小数 → 舍入误差上限 5e-5，容差取 1e-4
    ck('wq_y 独立重算最大偏差 ≤ 1e-4（4 位小数舍入）', mx <= 1e-4, True)
    ck('P_y 越界数', sum(1 for c in R['gov'] for y in YEARS
                        if Wd[c][f'P_{y}'] and not 0 <= float(Wd[c][f'P_{y}']) <= 1), 0)
    for y in YEARS:
        rk = sorted(int(Wd[c][f'rank_P_{y}']) for c in POOL_Y[y] if Wd[c][f'rank_P_{y}'])
        ck(f'{y} 名次 1..n 连续无重', rk, list(range(1, len(POOL_Y[y]) + 1)))
    ck('rank_P_wq 1..17 连续', sorted(int(Wd[c]['rank_P_wq']) for c in P5),
       list(range(1, 18)))

    print('\n=== [3] SEN 独立复算（嘉定教训：分母不得多乘 n）===')
    dmax, bmind = 0.0, 1e9
    for c in P5:
        ys = [R['REL'][(c, y)] for y in YEARS]
        n = len(xs)
        mxx, myy = st.fmean(xs), st.fmean(ys)
        num = sum((x - mxx) * (y - myy) for x, y in zip(xs, ys))
        den = sum((x - mxx) ** 2 for x in xs)
        dmax = max(dmax, abs(num / den - float(Wd[c]['SEN'])))
        bmind = min(bmind, abs(num / (n * den) - float(Wd[c]['SEN'])))
    ck('SEN 独立复算最大偏差 ≤ 1e-4（4 位小数舍入）', dmax <= 1e-4, True)
    # 判定「未多乘 n」：SEN 绝对值较大的学校，其值与 b/n 的差异应显著。
    # 不能用「最小距离 > 阈值」——SEN 接近 0 的学校两种算法都接近 0（嘉定亦如此）。
    big = [c for c in P5 if abs(float(Wd[c]['SEN'])) > 0.5]
    ck('SEN 绝对值 > 0.5 的学校数（用于判据）', len(big) >= 8, True)
    gap = 0.0
    for c in big:
        ys = [R['REL'][(c, y)] for y in YEARS]
        mxx, myy = st.fmean(xs), st.fmean(ys)
        num2 = sum((x - mxx) * (y - myy) for x, y in zip(xs, ys))
        den2 = sum((x - mxx) ** 2 for x in xs)
        gap = max(gap, abs(float(Wd[c]['SEN']) - num2 / (len(xs) * den2)))
    ck('SEN 与「多乘 n」错误值的最大差异 > 0.1（≥8 校）', round(gap, 3) > 0.1, True)
    ck('sen_ex2024 已产出', sum(1 for c in P5 if Wd[c]['sen_ex2024'] != ''), 17)
    ck('大同断点未翻转 SEN 符号',
       (float(Wd['上海市大同初级中学']['SEN']) > 0)
       == (float(Wd['上海市大同初级中学']['sen_ex2024']) > 0), True)

    print('\n=== [4] 逐年排名独立复算（分位 P 用当年池）===')
    for y in YEARS:
        pool = POOL_Y[y]
        # P 保留 4 位小数，容差 1e-4
        bad = sum(1 for c in pool
                  if abs(pct_rank(WQ[(c, y)], [WQ[(x, y)] for x in pool])
                         - float(Wd[c][f'P_{y}'])) > 1e-4)
        ck(f'{y} 分位 P 不符数', bad, 0)
    ck('2022 当年池含黄浦学校', int('上海市黄浦学校' in POOL_Y['2022']), 1)
    ck('2025 当年池不含黄浦学校', int('上海市黄浦学校' in POOL_Y['2025']), 0)

    print('\n=== [5] 离散度双口径 ===')
    with open(f'{A}/收敛分析-黄浦区-2022-2026.csv', encoding='utf-8-sig') as f:
        CV = list(csv.DictReader(f))
    ck('收敛表行数', len(CV), 5)
    for r in CV:
        y = r['year']
        d = dispersion([WQ[(x, y)] for x in POOL_Y[y]])
        ck(f'{y} IQR 偏差', round(abs(d['iqr'] - float(r['iqr'])), 9), 0.0)
        ck(f'{y} CV 偏差', round(abs(d['cv'] - float(r['cv'])), 9), 0.0)
    by = ols_slope(xs, [float(r['iqr']) for r in CV])
    bf = ols_slope(xs, [float(r['iqr_f']) for r in CV])
    ck('主辅 IQR 斜率同号', (by > 0) == (bf > 0), True)
    ck('主辅斜率均为负（离散度下降）', (by < 0) and (bf < 0), True)
    lo = min(float(r['iqr']) for r in CV)
    ck('2025 是 IQR 最低年', [r['year'] for r in CV if float(r['iqr']) == lo], ['2025'])

    print('\n=== [6] 趋势分类 ===')
    cnt = Counter(Wd[c]['trend_class'] for c in P5)
    ck('三类合计 = 17', sum(cnt.values()), 17)
    bad = [c for c in P5
           if (float(Wd[c]['sen_z']) >= 1) != (Wd[c]['trend_class'] == '明显上升')
           or (float(Wd[c]['sen_z']) <= -1) != (Wd[c]['trend_class'] == '明显下降')]
    ck('sen_z 与分类不一致数', len(bad), 0)
    ck('明显上升+下降 所数', cnt['明显上升'] + cnt['明显下降'], 6)

    print('\n=== [7] 交付物完整性 ===')
    for k, fn in FILES.items():
        ck(f'{k} 存在', int(os.path.exists(f'{A}/{fn}')), 1)
    with open(f'{A}/单线视角-黄浦区-2022-2026.csv', encoding='utf-8-sig') as f:
        sl = list(csv.DictReader(f))
    ck('单线视角覆盖招生学校数', len({r['senior_high_school'] for r in sl}), 15)
    ck('单线视角行数', len(sl), 202)
    ck('单线视角只含公办', sum(1 for r in sl if PRIV(r['junior_high_school'])), 0)

    print('\n=== [8] 报告 ===')
    if not os.path.exists(RPT):
        print('  [跳过] 分析报告.md 尚未生成')
    else:
        t = open(RPT, encoding='utf-8').read()
        ck('跨区禁词', [k for k in BAN if k in t], [])
        ck('含 2.0 逐指标解释表', int('怎么读' in t), 1)
        for kw in ('当年在办学校', '名额未用满', '结构断点', '异常',
                   '不可由本报告回答', '民办', '黄浦学校', '大同'):
            ck(f'报告含「{kw}」', int(kw in t), 1)
        for m in PRIV5:
            ck(f'排除民办已列名 {m[2:9]}', int(m in t), 1)
        # 主表 = 2.1 节（趋势表也是 17 行，须按节限定，否则重复计数）
        seg = t.split('### 2.1')[1].split('### 2.2')[0] if '### 2.1' in t else ''
        ck('报告含 2.1 主表节', int(bool(seg)), 1)
        # 目录编号：H2 标题须自带连续编号（0..N-1），且 TOC 不得再自动编号（否则双重序号）
        import re as _r2
        h2 = _r2.findall(r'^## (.+)$', t, _r2.M)
        ck('H2 标题数 = 10', len(h2), 10)
        nums = []
        for h in h2:
            m = _r2.match(r'^(\d+)[.、 ]?\s*\S', h)
            nums.append(int(m.group(1)) if m else None)
        ck('H2 编号连续 0..9 且无重复', nums, list(range(10)))
        ck('首个 H2 为「0 摘要」', h2[0], '0 摘要')
        hp = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/工具/build_html_hp.py'
        htm = open(hp, encoding='utf-8').read()
        ck('生成器已关闭 TOC 自动编号（list-style:none）',
           int('list-style:none' in htm), 1)
        if os.path.exists(f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/index.html'):
            ih = open(f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/index.html',
                      encoding='utf-8').read()
            blk = _r2.search(r'<nav class="toc">.*?</nav>', ih, _r2.S)
            ck('网页存在 TOC 区块', int(bool(blk)), 1)
            if blk:
                ck('TOC 条目数 = H2 标题数',
                   len(_r2.findall(r'<li><a', blk.group(0))), len(h2))
                ck('TOC 已渲染为无自动编号（无 list-style 覆盖遗漏）',
                   int('list-style:none' in ih), 1)
                # 目录文字不应出现「数字. 数字」双重序号
                dbl = [x for x in _r2.findall(r'<a[^>]*>([^<]+)</a>', blk.group(0))
                       if _r2.match(r'^\d+\.\s*\d+', x.strip())]
                ck('TOC 无「N. N」双重序号', dbl, [])
        short = [c.replace('上海市', '') for c in P5]
        rows = [l for l in seg.split('\n') if l.startswith('| ')
                and any(c in l for c in short) and l.count('|') >= 12]
        ck('2.1 主表 17 行齐备', len(rows), 17)
        miss = [c for c in short if not any(c in l for l in rows)]
        ck('2.1 主表遗漏的校', miss, [])
        # 近3年 / 2026 两列为合并格式「名次（变化）」，须与宽表逐格一致
        import re as _re
        bad_tc, bad_d3, bad_d26, bad_d2y = [], [], [], []
        for l in rows:
            cs = [c.strip() for c in l.strip('|').split('|')]
            if len(cs) != 14:
                bad_tc.append((cs[1], f'列数={len(cs)}'))
                continue
            nm = cs[1]
            hit = [c for c in P5 if c.replace('上海市', '') == nm]
            if not hit:
                continue
            w = Wd[hit[0]]
            r5 = int(w['rank_P_wq'])
            # 列序：…10=近3年 11=近2年 12=2026（窗口 3→2→1 年递减）
            for col, key, acc in ((cs[10], 'rank_P_recent3', bad_d3),
                                  (cs[11], 'rank_P_2y', bad_d2y),
                                  (cs[12], 'rank_P_2026', bad_d26)):
                m = _re.fullmatch(r'\*\*(\d+)\*\*（([+−-]?\d+)）', col)
                if not m:
                    acc.append((nm, col, '格式'))
                    continue
                rk, d = int(m.group(1)), int(m.group(2).replace('−', '-'))
                if rk != int(w[key]) or d != r5 - int(w[key]):
                    acc.append((nm, col, w[key], r5 - int(w[key])))
        ck('主表列数 = 14', bad_tc, [])
        # 列序断言：取**表头行**（rows 是数据行），窗口长度须递减 3→2→1
        hdr_row = [l for l in seg.split('\n')
                   if l.startswith('| 名 | 初中 |')]
        ck('报告 2.1 含表头行', len(hdr_row), 1)
        if hdr_row:
            ck('主表时间窗口列序 = 近3年→近2年→2026',
               [c.strip() for c in hdr_row[0].strip('|').split('|')][10:13],
               ['**近 3 年（名次·变化）**', '**近 2 年（名次·变化）**',
                '**2026（名次·变化）**'])
        ck('近 3 年 名次与变化与宽表一致', bad_d3, [])
        ck('2026 名次与变化与宽表一致', bad_d26, [])
        ck('近 2 年 名次与变化与宽表一致', bad_d2y, [])
        ck('2026 当年池与五年全勤池同一批学校',
           sorted(POOL_Y['2026']), sorted(P5))
        # 两套独立口径互证：近 3 年升幅前 3 应与 SEN「明显上升」组**完全重合**
        # （实测 3/3：金陵 +5、比乐 +5、尚文 +4）——名次窗口与回归斜率互相印证
        up3 = sorted(P5, key=lambda c: -(int(Wd[c]['rank_P_wq'])
                                        - int(Wd[c]['rank_P_recent3'])))[:3]
        cls_up = {c for c in P5 if Wd[c]['trend_class'] == '明显上升'}
        ck('近 3 年升幅前 3 与 SEN「明显上升」组完全重合', len(set(up3) & cls_up), 3)
        ck('SEN「明显上升」组恰为 3 所', len(cls_up), 3)
        # 卢湾案例：五年 −3.75（明显下降）但近两年 +7.72（已反转）——
        # 该案例是「单看五年分类会误判当前状态」的标准反例，固定其数值
        ck('卢湾 五年 SEN = −3.749', round(float(Wd['上海市卢湾中学']['SEN']), 3),
           -3.749)
        ck('卢湾 近两年 SEN = +7.72（已反转）',
           round(float(Wd['上海市卢湾中学']['sen_2y']), 2), 7.72)
        ck('卢湾 分类=明显下降 且 近两年=已反转',
           [Wd['上海市卢湾中学']['trend_class'],
            Wd['上海市卢湾中学']['reversed_2y']], ['明显下降', '已反转'])
        ck('三所明显下降中仅市南近两年续降',
           [c for c in P5 if Wd[c]['trend_class'] == '明显下降'
            and Wd[c]['reversed_2y'] == '近两年续降'], ['上海市市南中学'])
        ck('报告已说明卢湾案例', int('卢湾中学为什么' in t), 1)
        # 「下滑最快」这类表述必须限定窗口：卢湾五年降幅第 1，但近两年是上升第 2
        top5_dec = sorted(P5, key=lambda c: R['SEN'][c])[:1]
        ck('五年 SEN 最低者 = 卢湾（降幅第 1）', top5_dec, ['上海市卢湾中学'])
        top5_rise = sorted(P5, key=lambda c: -R['SEN_2Y'][c])[:2]
        ck('近两年 SEN 最高前 2 含卢湾（上升第 2）',
           int('上海市卢湾中学' in top5_rise), 1)
        # 报告里出现的「近 N 年 SEN」数字必须与宽表一致（防编造数值）
        import re as _r
        seg = t.split('### 5.1')[1].split('### 5.2')[0] if '### 5.1' in t else ''
        bad_num = []
        for nm, val in _r.findall(r'([一-鿿]{2,6}?)(?:中学|学校)?\s*\+(\d+\.\d{2})', seg):
            hit = [c for c in P5 if c.startswith(nm)]
            if hit and abs(float(Wd[hit[0]]['sen_2y']) - float(val)) > 0.005:
                bad_num.append((nm, val, Wd[hit[0]]['sen_2y']))
        ck('5.1 节引用的近两年 SEN 数值与宽表一致', bad_num, [])

    print('\n' + '=' * 62)
    print(f'总计 {N} 项检查，不通过 {len(FAILS)} 项')
    for f in FAILS:
        print('  不过：', f)
    return 1 if FAILS else 0


if __name__ == '__main__':
    raise SystemExit(main())
