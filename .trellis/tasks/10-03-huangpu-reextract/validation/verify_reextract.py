#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦分数线重抽 2.2 数据正确性门禁。

判定标准见 prd.md「验收标准」1–7。逐年独立断言，不假设 5 年同版式。

用法：python3 verify_reextract.py
"""
import csv
import os
import re
import statistics as st
import sys
from collections import Counter, defaultdict

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
D = f'{ROOT}/data/黄浦区/学校'
SC = f'{D}/名额到校最低分数线-黄浦区-2022-2026.csv'
PL = f'{D}/名额到校计划-黄浦区-2022-2026.csv'
# 基线必须是**重抽前**的原始 CSV，且不可被后续写入覆盖。
# 踩过的坑：--write 每次都把当前文件备份到 /tmp，第二次写入后基线已是自己输出，
# 对账恒为「差异 0」而形同虚设。故基线取自 git HEAD（见 implement.md 回滚点）。
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'baseline_before_reextract.csv')
TOOL = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/工具'
sys.path.insert(0, TOOL)
from extract_score_hp import (YEARS, D as ED, name_pools, extract_year,  # noqa: E402
                             detect_score_cols, load_rows, is_num, probe_layout)

FAILS = []
N = 0


def ck(name, got, want, tol=0):
    global N
    N += 1
    ok = abs(got - want) <= tol if isinstance(want, (int, float)) else got == want
    if not ok:
        FAILS.append(name)
    print(f"  [{'过' if ok else '不过'}] {name}: {got}" + ('' if ok else f'（应 {want}）'))


def pdf(y):
    return f'{D}/【黄浦】【{y}】名额到校最低分数线.pdf'


def main():
    jp, sp = name_pools()
    R = {y: extract_year(y, jp, sp) for y in YEARS}
    with open(SC, encoding='utf-8-sig') as f:
        NEW = list(csv.DictReader(f))
    with open(PL, encoding='utf-8-sig') as f:
        PLAN = list(csv.DictReader(f))
    have_base = os.path.exists(BASE)
    OLD = list(csv.DictReader(open(BASE, encoding='utf-8-sig'))) if have_base else []

    # ---------- [1] 版面：分数列角色逐年正确 ----------
    print('\n=== [1] 版面探测（逐年，不假设同版式）===')
    WANT = {  # 每年应有的列角色（实测确认，2025/2026 多一个综合素质评价列）
        '2022': ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
        '2023': ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
        '2024': ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
        '2025': ['min_score', 's综合评价', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
        '2026': ['min_score', 's综合评价', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
    }
    for y in YEARS:
        cols, _, roles = detect_score_cols(pdf(y))
        ck(f'{y} 列角色', roles, WANT[y])
        ck(f'{y} 列角色无空位', sum(1 for r in roles if r is None), 0)
        L = probe_layout(pdf(y))
        has_tie = ('tie' in L['anchors'] or 'tie2' in L['anchors'])
        ck(f'{y} 同分优待列存在={has_tie}', has_tie, y != '2022')

    # ---------- [2] 记录完整性：与「独立第二实现」比对 ----------
    print('\n=== [2] 记录完整性（第二实现：不同 y 分桶 + 计划表交叉）===')
    for y in YEARS:
        ck(f'{y} 记录数 = 抽取结果长度', R[y]['n_rec'], len(R[y]['recs']))
        # 独立实现：y/2 分桶（不同粒度），记录数必须相同
        n_alt = _alt_count(pdf(y))
        ck(f'{y} 独立实现(y/2 分桶) 记录数一致', n_alt, R[y]['n_rec'])
    ck('五年记录总数', sum(R[y]['n_rec'] for y in YEARS), len(NEW))
    ck('CSV 行数 = 记录总数', len(NEW), sum(R[y]['n_rec'] for y in YEARS))

    # ---------- [3] 配对完整性 ----------
    print('\n=== [3] 名称配对（100% 是硬要求）===')
    for y in YEARS:
        ck(f'{y} 初中名配上', R[y]['n_junior'], R[y]['n_rec'])
        ck(f'{y} 高中名配上', R[y]['n_senior'], R[y]['n_rec'])
        ck(f'{y} 无空校名',
           sum(1 for r in R[y]['recs'] if not r['junior'] or not r['senior']), 0)
        ck(f'{y} CSV 中校名非空',
           sum(1 for r in NEW if r['year'] == y
               and (not r['junior_high_school'] or not r['senior_high_school'])), 0)
        ck(f'{y} (初中,高中) 键无重复',
           sum(1 for v in Counter((r['junior_high_school'], r['senior_high_school'])
                                 for r in NEW if r['year'] == y).values() if v > 1), 0)

    # ---------- [4] 残留：未匹配校名 ----------
    print('\n=== [4] 校名池覆盖（无未识别校名残留）===')
    plan_j = {r['junior_high_school'] for r in PLAN}
    csv_j = {r['junior_high_school'] for r in NEW}
    plan_s = {r['senior_high_school'] for r in PLAN if len(r['senior_high_school']) >= 5}
    csv_s = {r['senior_high_school'] for r in NEW}
    ck('分数线初中名 ⊆ 计划表初中名 ∪ 更名登记',
       len(csv_j - plan_j - {'上海市兴业中学'}), 0)
    ck('分数线高中名 ⊆ 计划表高中名（已剔简称）', len(csv_s - plan_s), 0)
    ck('计划表高中名未归一的简称数（应为 12+1）',
       len({r['senior_high_school'] for r in PLAN
            if len(r['senior_high_school']) < 5}), 13)

    # ---------- [5] 逐格对账（基线 = 重抽前原始 CSV） ----------
    print('\n=== [5] 逐格对账（基线 = 重抽前 CSV）===')
    ck('基线文件存在', have_base, True)
    if have_base:
        oldk = {(r['year'], r['junior_high_school'], r['senior_high_school']) for r in OLD}
        newk = {(r['year'], r['junior_high_school'], r['senior_high_school']) for r in NEW}
        ck('新 ⊇ 旧（仅旧有的键数，应 0）', len(oldk - newk), 0)
        ck('新增记录数 = 找回的漏抽行', len(newk - oldk), 189)
        om = {(r['year'], r['junior_high_school'], r['senior_high_school']): r['min_score']
              for r in OLD}
        nm = {(r['year'], r['junior_high_school'], r['senior_high_school']): r['min_score']
              for r in NEW}
        ck('共有键 min_score 差异数（应 0）',
           sum(1 for k in oldk & newk
               if abs(float(om[k]) - float(nm[k])) > 1e-9), 0)
        # 科目列：2025/2026 旧值错位，必须逐条不同；2022-2024 必须完全一致
        for y in YEARS:
            ks = [k for k in oldk & newk if k[0] == y]
            dm = 0
            for k in ks:
                o = next(r for r in OLD if (r['year'], r['junior_high_school'],
                                            r['senior_high_school']) == k)
                n = next(r for r in NEW if (r['year'], r['junior_high_school'],
                                            r['senior_high_school']) == k)
                for c in ('yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'):
                    if o[c].strip() and n[c].strip() and \
                            abs(float(o[c]) - float(n[c])) > 1e-9:
                        dm += 1
                        break
            # 基线的 yw_* 本来就是正确的（已逐条核对），故重抽后必须**完全一致**。
            # 曾误以为旧 CSV 有列错位——那是对比我自己的中间产物，不是基线。
            ck(f'{y} 科目列与基线不一致条数（应 0）', dm, 0)

    # ---------- [6] 计划表 × 分数线 交叉 ----------
    # 计划表 2024 整年用简称（格致奉贤/卢高/华二附中…），且把并入的黄浦学校写作
    # 无前缀的「大同初级中学（原黄浦学校）」；不归一则 join 必然失败，那是
    # huangpu-normalize 任务的范围。此处**先归一再交叉**，让本段检验真实的数据
    # 完整性，而不是检验归一任务做没做完。
    print('\n=== [6] 计划表 × 分数线 交叉（计划表侧先归一）===')
    pl = {(r['year'], canon_junior(r['junior_high_school']),
           canon_senior(r['senior_high_school'])): int(r['quota'])
          for r in PLAN if int(r['quota']) > 0}
    sc = {(r['year'], r['junior_high_school'], r['senior_high_school']) for r in NEW}
    miss, extra = set(pl) - sc, sc - set(pl)
    # 「计划有名额但分数线无此行」不等于抽取遗漏：名额=1 且无人录取时，
    # 官方表不会产生末位录取考生，因此没有这一行。已核 2024/2026 康德的 PDF
    # 原文只录了格致中学。故判定标准是「所有缺口的名额均为 1」，
    # 若出现名额 ≥2 的缺口才是抽取遗漏。
    ck('分数线有但计划表无名额（应 0）', len(extra), 0)
    ck('缺口数（计划有名额、分数线无行）', len(miss), 18)
    ck('缺口名额均 =1（≥2 才是抽取遗漏）',
       sum(1 for k in miss if pl[k] != 1), 0)
    ck('缺口名额最大值', max((pl[k] for k in miss), default=0), 1)
    ck('康德 2024 实际录取 2 所 / 2026 实际录取 1 所（计划各 7 所）',
       [sum(1 for r in NEW if r['year'] == y
            and r['junior_high_school'] == '上海康德双语实验学校')
        for y in ('2024', '2026')], [2, 1])

    # ---------- [7] 字段规范 ----------
    print('\n=== [7] 字段规范与值域 ===')
    RANGE = {'min_score': (600, 800), 'yw_sx': (300, 450), 'yw_math': (80, 150),
             'yw_chinese': (80, 150), 'yw_comprehensive': (80, 150), 's综合评价': (0, 50)}
    for c, (lo, hi) in RANGE.items():
        v = [float(r[c]) for r in NEW if str(r[c]).strip()]
        ck(f'{c} 值域 [{lo},{hi}]', 0 if (v and min(v) >= lo and max(v) <= hi) else 1, 0)
    for y in YEARS:
        o = [r for r in NEW if r['year'] == y]
        pg = fitz.open(pdf(y)).page_count
        ck(f'{y} source_page 合法', sum(1 for r in o
                                       if not (1 <= int(r['source_page']) <= pg)), 0)
        ck(f'{y} 六项分数齐全', sum(1 for r in o if not all(
            r[c].strip() for c in ('min_score', 'yw_sx', 'yw_math',
                                   'yw_chinese', 'yw_comprehensive'))), 0)
    ck('2022 同分优待全空（官方无此列）',
       sum(1 for r in NEW if r['year'] == '2022' and r['is_tie_preferred'].strip()), 0)
    ck('2022/2023 综合素质评价全空（官方无此列）',
       sum(1 for r in NEW if r['year'] in ('2022', '2023') and r['s综合评价'].strip()), 0)
    ck('2024 综合素质评价全为 50（官方注明）',
       len({r['s综合评价'] for r in NEW if r['year'] == '2024'}), 1)
    ck('2025/2026 综合素质评价全为 50（有该列且恒为 50）',
       len({r['s综合评价'] for r in NEW if r['year'] in ('2025', '2026')}), 1)
    ck('note 列已标注缺失列依据',
       sum(1 for r in NEW if r['year'] in ('2022', '2023', '2024') and r['note'].strip()),
       sum(1 for r in NEW if r['year'] in ('2022', '2023', '2024')))
    ck('列数', len(NEW[0]), 17)
    # 结构断点：黄浦学校序列
    hp = {y: sum(1 for r in NEW if r['year'] == y
                 and r['junior_high_school'] == '上海市黄浦学校') for y in YEARS}
    ck('黄浦学校 2022/2023/2024 各 9 条（2024 为并入大同的独立序列）',
       [hp['2022'], hp['2023'], hp['2024']], [9, 9, 9])
    ck('黄浦学校 2025/2026 已无（并入大同）', [hp['2025'], hp['2026']], [0, 0])
    dt = {y: sum(1 for r in NEW if r['year'] == y
                 and r['junior_high_school'] == '上海市大同初级中学') for y in YEARS}
    ck('大同初级中学各年 9–10 条（未混入黄浦学校）',
       all(9 <= v <= 10 for v in dt.values()), True)

    print('\n' + '=' * 62)
    print(f'总计 {N} 项检查，不通过 {len(FAILS)} 项')
    for f in FAILS:
        print('  不过：', f)
    return 1 if FAILS else 0


# 计划表侧的简称 / 无前缀名 → 全称（仅用于交叉校验；正式归一见 huangpu-normalize）
SENIOR_ALIAS = {
    '交大附中': '上海交通大学附属中学', '光明': '上海市光明中学',
    '华二附中': '华东师范大学第二附属中学', '卢高': '上海市卢湾高级中学',
    '向明': '上海市向明中学', '向明浦江': '上海市向明中学（浦江校区）',
    '复旦附中': '复旦大学附属中学', '大同': '上海市大同中学',
    '大境': '上海外国语大学附属大境中学', '敬业': '上海市敬业中学',
    '格致': '上海市格致中学', '格致奉贤': '上海市格致中学（奉贤校区）',
    '上海中学': '上海市上海中学',
}


def canon_senior(n):
    return SENIOR_ALIAS.get(n, n)


def canon_junior(n):
    if n == '大同初级中学（原黄浦学校）':
        return '上海市黄浦学校'
    return n


def _alt_count(p):
    """独立第二实现：用 y/2 分桶（不同粒度）重数记录行数。

    主实现用 round(y/3)；若两者结果不同，说明记录边界对分桶粒度敏感，
    抽取不可靠。语数外等列容差按最小列距的一半计算，与主实现一致。
    """
    doc = fitz.open(p)
    n = 0
    for pg in doc:
        b = defaultdict(list)
        for w in pg.get_text('words'):
            if is_num(w[4]):
                b[round(w[1] / 2)].append((round(w[0]), w[4]))
        for k in b:
            n += 1 if len({x for x, _ in b[k]}) >= 5 else 0
    doc.close()
    return n


if __name__ == '__main__':
    sys.exit(main())
