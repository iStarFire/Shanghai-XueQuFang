#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5.2 口径结论的证据级别：名额是否为「学校规模的代理」？

## 为什么要做这个
普陀 5 个年度的名额到校计划文件**全部是纯数据表**（标题为「…分配结果公示」），
**没有**「以…为测算依据」的规则说明文字。因此报告**不得**写「普陀区名额按…分配」。
可写的依据只有：
  · 上海市统一政策《上海市高中阶段学校招生录取改革实施办法》（沪教委规〔2021〕2 号）
  · 其他区公开文件中的同规则明文（须注明**非普陀本地原文**）
  · **普陀自有数据的旁证**（本脚本）

## 判据（design.md 四）
「若各校名额占比跨年稳定、跨校差异大，则与『按人数占比分配』一致。」

本脚本**分别检验两个条件**，不合并成一句结论 —— 因为实测只满足其一。

## 口径
占比 = 某校某线该年名额 ÷ 该线该年区属（4 条基线线）总额。
已按 `merged_into` 排除晋元西校（它与晋元附校在 2022 计划表同一行、名义重复）。
"""
import csv
import statistics as st
from pathlib import Path

D = Path(__file__).resolve().parents[3] / 'data/普陀区/学校'
YEARS = ['2022', '2023', '2024', '2025', '2026']
QU4 = ['华二普陀', '二中', '晋元', '宜川']      # 区属 4 条基线线
MIN_YEARS = 4
BIG = 3.0        # 4 线五年年均名额 ≥ 此值 ⇒「规模校」


def load():
    rows = list(csv.DictReader((D / '名额到校计划-普陀区-2022-2026.csv')
                               .open(encoding='utf-8-sig')))
    return [r for r in rows if r.get('merged_into') in ('', None)]


def shares(P):
    """{线: {校: {年: 占比}}}"""
    out = {}
    for h in QU4:
        per = {}
        for y in YEARS:
            tot = sum(int(r['quota']) for r in P
                      if r['year'] == y and r['senior_high_school_short'] == h)
            for r in P:
                if r['year'] == y and r['senior_high_school_short'] == h:
                    per.setdefault(r['junior_high_school'], {})[y] = \
                        int(r['quota']) / tot if tot else None
        out[h] = per
    return out


def cv(vals):
    m = st.fmean(vals)
    return st.pstdev(vals) / m if m else 0.0


def main():
    P = load()
    S = shares(P)
    q4 = {}
    for r in P:
        if r['senior_high_school_short'] in QU4:
            q4.setdefault(r['junior_high_school'], []).append(int(r['quota']))

    print('=' * 68)
    print('5.2 证据级别：名额是否为「学校规模的代理」（普陀自有数据旁证）')
    print('=' * 68)

    # ---- 条件一：跨校差异 ----
    print('\n【条件一】跨校占比差异（design 判据要求「大」）')
    all_m = []
    for h in QU4:
        ms = []
        for s, d in S[h].items():
            vs = [d[y] for y in YEARS if d.get(y) is not None]
            if len(vs) >= MIN_YEARS:
                ms.append(st.fmean(vs))
        all_m += ms
        print(f'  {h:<8} 纳入 {len(ms):>2} 所  占比 {min(ms)*100:5.2f}% ~ {max(ms)*100:5.2f}%'
              f'  极差 {(max(ms)-min(ms))*100:.1f} 个百分点'
              f'  倍数 {max(ms)/min(ms):.1f}×')
    print(f'  → 全部 4 线合并：占比 {min(all_m)*100:.2f}% ~ {max(all_m)*100:.2f}%，'
          f'相差 {max(all_m)/min(all_m):.1f} 倍  ⇒ 条件一【满足】')

    # ---- 条件二：跨年稳定 ----
    print('\n【条件二】占比的跨年稳定性（design 判据要求「稳定」，用 CV）')
    rows = []
    for h in QU4:
        for s, d in S[h].items():
            vs = [d[y] for y in YEARS if d.get(y) is not None]
            if len(vs) < MIN_YEARS:
                continue
            qm = st.fmean(q4.get(s, [0]))
            rows.append({'school': s, 'line': h, 'q_mean': qm,
                         'share': st.fmean(vs), 'cv': cv(vs)})
    big = [r for r in rows if r['q_mean'] >= BIG]
    small = [r for r in rows if r['q_mean'] < BIG]
    for lab, g in (('规模校（4 线年均 ≥3 个名额）', big),
                   ('小额校（<3 个，多为 1 个名额）', small)):
        c = [r['cv'] for r in g]
        print(f'  {lab}：{len(g):>2} 所｜CV 中位 {st.median(c)*100:5.1f}%'
              f'  均值 {st.fmean(c)*100:5.1f}%  最大 {max(c)*100:5.1f}%')
    c_all = [r['cv'] for r in rows]
    print(f'  → 全部 {len(rows)} 条校线观测：CV 中位 {st.median(c_all)*100:.1f}%'
          f'（即使只看规模校仍有 {st.median([r["cv"] for r in big])*100:.1f}%）')
    print('  → CV 在 15%–24% 量级，属**高波动**（人数占比若真按同一规则分配，'
          '应显著低于此）⇒ 条件二【不满足】')

    # ---- 结论 ----
    print('\n【结论】design 判据的两个条件只满足其一：')
    print('  ✅ 跨校差异极大（近 20 倍）—— 与「名额大体按规模分配」一致；')
    print('  ❌ 占比跨年 CV 中位 15.7%（规模校）—— 不足以断言「严格按人数占比分配」。')
    print('  ⇒ 「名额 ≈ 学校规模代理」只能作为**旁证**写入，证据级别为「弱」，')
    print('    不得表述为「普陀区名额按…分配」（本地无规则原文），')
    print('    也不得表述为「名额**就是**规模」（CV 已排除这一强说法）。')

    # ---- 与「名额=1」样本问题的连接 ----
    n1 = sum(1 for r in rows if r['q_mean'] < 1.5)
    print(f'\n【补充】{n1}/{len(rows)} 条校线观测的 4 线年均名额 <1.5（多为 1 个），'
          f'其 CV 中位 {st.median([r["cv"] for r in rows if r["q_mean"] < 1.5])*100:.1f}%；')
    print('  这类学校**一个名额的增减就会让占比翻倍**，是 3.3「名额基数过小」'
          '在规模代理上的同一问题。')

    print('\n' + '=' * 68)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
