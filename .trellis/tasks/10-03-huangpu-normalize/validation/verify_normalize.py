#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦计划表校名归一 2.2 数据正确性门禁。

对应 prd.md 验收标准 1–7。用法：python3 verify_normalize.py
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
D = f'{ROOT}/data/黄浦区/学校'
PL = f'{D}/名额到校计划-黄浦区-2022-2026.csv'
SC = f'{D}/名额到校最低分数线-黄浦区-2022-2026.csv'
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'baseline_before_normalize.csv')
TOOL = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/工具'
sys.path.insert(0, TOOL)
from normalize_plan_hp import (parse_2024_header, plan_normalize,  # noqa: E402
                               load, PDF2024)

FAILS = []
N = 0


def ck(name, got, want):
    global N
    N += 1
    ok = got == want
    if not ok:
        FAILS.append(name)
    print(f"  [{'过' if ok else '不过'}] {name}: {got}" + ('' if ok else f'（应 {want}）'))


def main():
    with open(PL, encoding='utf-8-sig') as f:
        PLAN = list(csv.DictReader(f))
    with open(SC, encoding='utf-8-sig') as f:
        SCORE = list(csv.DictReader(f))
    rows, _ = load()

    # ---------- [1] 占位归零 ----------
    print('\n=== [1] 占位标记与临时代码已清除 ===')
    ck('is_placeholder_code=1 行数',
       sum(1 for r in PLAN if r['is_placeholder_code'] == '1'), 0)
    ck('临时代码 017777 残留行数',
       sum(1 for r in PLAN if r['junior_high_school_code'] == '017777'), 0)
    ck('已写入 note 列的行数（13 行同时发生两处替换）',
       sum(1 for r in PLAN if r.get('note', '').strip()), 13)
    ck('每行 note 同时含「简称归一」与「临时代码归一」两条说明',
       sum(1 for r in PLAN if '原为简称' in r.get('note', '')
           and '原为临时代码' in r.get('note', '')), 13)

    # ---------- [2] 一码一名 ----------
    print('\n=== [2] 名称与代码一一对应 ===')
    for nk, ck_, want_n in (('senior_high_school', 'senior_high_school_code', 15),
                            ('junior_high_school', 'junior_high_school_code', 23)):
        d = defaultdict(set)
        for r in PLAN:
            d[r[ck_]].add(r[nk])
        multi = {c: v for c, v in d.items() if len(v) > 1}
        ck(f'{nk} 去重数', len({r[nk] for r in PLAN}), want_n)
        ck(f'{nk} 一码一名（冲突代码数）', len(multi), 0)
        for c, v in list(multi.items())[:3]:
            print(f'      {c}: {sorted(v)}')

    # ---------- [3] 独立交叉验证 + 幂等性 ----------
    print('\n=== [3] 独立交叉验证与幂等性 ===')
    hdr = parse_2024_header(PDF2024)
    ck('PDF 头部对照表条数', len(hdr), 13)
    ck('对照表代码集合 == 已归一的简称行代码集合',
       sorted(hdr.values()),
       sorted({r['senior_high_school_code'] for r in PLAN
               if '原为简称' in r.get('note', '')}))
    _, again = plan_normalize(rows)
    ck('幂等性：再次归一无高中简称替换项',
       sum(1 for c in again if c['kind'] == '高中简称'), 0)
    ck('幂等性：再次归无一关键码替换项',
       sum(1 for c in again if c['kind'] == '初中临时代码'), 0)

    # ---------- [4] 归一无副作用 ----------
    print('\n=== [4] 归一前后逐行等价（只改名称）===')
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding='utf-8-sig') as f:
            OLD = list(csv.DictReader(f))
        ck('行数不变', len(PLAN), len(OLD))
        ck('名额总和不变', sum(int(r['quota']) for r in PLAN),
           sum(int(r['quota']) for r in OLD))
        quota_seq_ok = all(a['quota'] == b['quota'] for a, b in zip(OLD, PLAN))
        ck('quota 序列逐行一致', quota_seq_ok, True)
        diff_other = sum(1 for a, b in zip(OLD, PLAN)
                         for k in ('year', 'quota', 'source_doc', 'source_page')
                         if a.get(k, '') != b.get(k, ''))
        ck('year/quota/source_* 差异数', diff_other, 0)
        ck('归一前高中去重名（应为 28）',
           len({r['senior_high_school'] for r in OLD}), 28)
        ck('归一前初中去重名（应为 24）',
           len({r['junior_high_school'] for r in OLD}), 24)
    else:
        print('  [跳过] 基线不存在')

    # ---------- [5] 双源 join ----------
    print('\n=== [5] 计划表 × 分数线 双源 join ===')
    pl = {(r['year'], r['junior_high_school'], r['senior_high_school'])
          for r in PLAN if int(r['quota']) > 0}
    sc = {(r['year'], r['junior_high_school'], r['senior_high_school'])
          for r in SCORE}
    qm = {k: int(r['quota']) for k, r in
          {(r['year'], r['junior_high_school'], r['senior_high_school']): r
           for r in PLAN}.items()}
    miss, extra = pl - sc, sc - pl
    ck('分数线有但计划表无名额（冗余，应 0）', len(extra), 0)
    ck('计划有名额但分数线无行（缺口）', len(miss), 18)
    ck('缺口名额均为 1（≥2 才可能是抽取遗漏）',
       sum(1 for k in miss if qm[k] != 1), 0)
    ck('缺口名额最大值', max((qm[k] for k in miss), default=0), 1)
    for k in sorted(miss):
        print(f'      缺: {k[0]} {k[1]} | {k[2]}（计划 {qm[k]} 名额）')

    # ---------- [6] 与分数线侧归一结论一致 ----------
    print('\n=== [6] 双源对「黄浦学校」的归一一致 ===')
    ck('计划表 2024 已无「原黄浦学校」',
       sum(1 for r in PLAN if '原黄浦学校' in r['junior_high_school']), 0)
    n = lambda y, rs: sum(1 for r in rs if r['year'] == y
                          and r['junior_high_school'] == '上海市黄浦学校')
    ck('计划表黄浦学校 2022/2023/2024 行数', [n(y, PLAN) for y in ('2022', '2023', '2024')],
       [14, 14, 13])
    ck('计划表黄浦学校 2025/2026 无行', [n(y, PLAN) for y in ('2025', '2026')], [0, 0])
    ck('分数线黄浦学校 2022/2023/2024 条数', [n(y, SCORE) for y in ('2022', '2023', '2024')],
       [9, 9, 9])
    ck('计划表 2024 黄浦学校名额合计（并入规模）',
       sum(int(r['quota']) for r in PLAN
           if r['year'] == '2024' and r['junior_high_school'] == '上海市黄浦学校'), 20)

    # ---------- [7] 下游无失效产物 ----------
    print('\n=== [7] 下游产物 ===')
    ad = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析'
    # 归一后的下游分析产物由 10-03-huangpu-analysis 产出并由 verify_analysis.py 校验。
    # 本门禁在此只确认「归一后分析产物已重新生成」——若为空说明归一后未重跑分析。
    dl = sorted(f for f in os.listdir(ad) if f.endswith(('.csv', '.html', '.md')))
    ck('归一后分析产物已生成（≥7 个 CSV）',
       len([f for f in dl if f.endswith('.csv')]) >= 7, True)
    ck('分析报告已生成', int(os.path.exists(f'{ad}/分析报告.md')), 1)
    print(f'      产物: {dl}')

    print('\n' + '=' * 62)
    print(f'总计 {N} 项检查，不通过 {len(FAILS)} 项')
    for f in FAILS:
        print('  不过：', f)
    return 1 if FAILS else 0


if __name__ == '__main__':
    raise SystemExit(main())
