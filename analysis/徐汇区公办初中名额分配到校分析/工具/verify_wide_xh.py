#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.1 门禁：宽表派生列**独立复算**（逐格）。

与生成脚本共用 `xh_common.midrank`（implement 6.1 要求）。
⛔ 不得自己重写平均秩 —— 普陀曾因三套实现导致「假门禁」。
"""
import csv
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D_S = ROOT / 'data/徐汇区/学校'
D_A = ROOT / 'analysis/徐汇区公办初中名额分配到校分析'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xh_common import midrank, weighted_mean, p_from_rank  # noqa: E402

YEARS = [2022, 2023, 2024, 2025, 2026]
QU6 = ['042001', '042002', '042008', '042035', '042036', '043015']
BASE_N = {2022: 4, 2023: 5, 2024: 5, 2025: 5, 2026: 6}
COMM = ['042032', '102056', '102057', '152003', '152006']
TOL = 5e-4


def load(p):
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


plan = load(D_S / '名额到校计划-徐汇区-2022-2026.csv')
score = load(D_S / '名额到校最低分数线-徐汇区-2022-2026.csv')
W = load(D_A / '宽表-初中水平-徐汇区-2022-2026.csv')
bym = {r['junior_high_school_code']: r for r in W}
SH = {r['junior_high_school_code']: r['junior_high_school'] for r in plan}

Q = {(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code']):
     int(r['quota_plan']) for r in plan if r['quota_plan'] not in ('', None)}
SC = {(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code']):
      float(r['min_score']) for r in score if r['min_score'].strip()}
SCHOOLS = {r['junior_high_school_code'] for r in plan}
ACT = {y: [h for h in QU6 if any(SC.get((y, c, h)) is not None for c in SCHOOLS)]
       for y in YEARS}
MEAN = {}
for y in YEARS:
    for c in SCHOOLS:
        pr = [(SC.get((y, c, h)), Q.get((y, c, h), 0)) for h in ACT[y]]
        MEAN[(c, y)] = weighted_mean([(s, n) for s, n in pr if s is not None and n])

bad = []
n_checked = 0
for y in YEARS:
    assert len(ACT[y]) == BASE_N[y], f'{y} 线数 {len(ACT[y])} ≠ {BASE_N[y]}'
    for c in sorted(SCHOOLS):
        w = bym[c]
        # base_n
        if w.get('base_n_%d' % y) != str(len(ACT[y])):
            bad.append((c, y, 'base_n', w.get('base_n_%d' % y), len(ACT[y])))
        n_checked += 1
        # quota6
        exp = sum(Q.get((y, c, h), 0) for h in ACT[y])
        got = w.get('quota6_%d' % y, '')
        if got not in ('', None) and abs(float(got) - exp) >= TOL:
            bad.append((c, y, 'quota6', got, exp))
        n_checked += 1
        # mean_score_base
        m = MEAN[(c, y)]
        got = w.get('mean_score_base_%d' % y, '')
        if m is None:
            if got not in ('', None):
                bad.append((c, y, 'mean', got, '空'))
        else:
            if got in ('', None) or abs(float(got) - m) > 1e-3:
                bad.append((c, y, 'mean', got, '%.3f' % m))
        n_checked += 1
print('逐年派生列复算：%d 校 × %d 年，%d 格' % (len(SCHOOLS), len(YEARS), n_checked))

# 位次 / 分位（池 = 当年公办非退出，用 xh_common.midrank）
RANKED = [c for c in sorted(SCHOOLS) if bym[c]['row_type'] == 'ranked']
EXITED = {c for c in SCHOOLS if bym[c]['row_type'] == 'exited'}
MINBAN = {c for c in SCHOOLS if bym[c]['ownership'] == '民办'}
n2 = 0
for y in YEARS:
    pool = [c for c in RANKED if MEAN.get((c, y)) is not None]
    # 注意：非 ranked 的公办（短样本）也在 rel 池里，但位次池只算 ranked
    rel_pool = [c for c in sorted(SCHOOLS) if MEAN.get((c, y)) is not None
                and bym[c]['ownership'] == '公办' and c not in EXITED]
    rk = midrank([(c, MEAN[(c, y)]) for c in rel_pool])
    xs = [MEAN[(c, y)] for c in rel_pool]
    mu = st.fmean(xs)
    sg = st.pstdev(xs)
    med = st.median(xs)
    sxs = sorted(xs)
    iqr = sxs[len(sxs) * 3 // 4] - sxs[len(sxs) // 4]
    rs = iqr / 1.349 if iqr else None
    for c in SCHOOLS:
        w = bym[c]
        v = MEAN.get((c, y))
        # rank_base（平均秩，仅池内有值）
        g = w.get('rank_base_%d' % y, '')
        if c in rk:
            if g in ('', None) or abs(float(g) - rk[c]) > 1e-9:
                bad.append((c, y, 'rank', g, rk[c]))
        elif g not in ('', None):
            bad.append((c, y, 'rank', g, '空'))
        n2 += 1
        # P_base
        g = w.get('P_base_%d' % y, '')
        if c in rk:
            e = p_from_rank(rk[c], len(rel_pool))
            if g in ('', None) or abs(float(g) - e) > 1e-6:
                bad.append((c, y, 'P', g, '%.6f' % e))
        n2 += 1
        # Z / ZR
        if v is not None and c in rel_pool:
            for col, e in (('Z_base', (v - mu) / sg if sg else None),
                           ('ZR_base', (v - med) / rs if rs else None)):
                g = w.get('%s_%d' % (col, y), '')
                if e is None:
                    if g not in ('', None):
                        bad.append((c, y, col, g, '空'))
                elif g in ('', None) or abs(float(g) - e) > 1e-6:
                    bad.append((c, y, col, g, '%.6f' % e))
                n2 += 1
        # rel —— 基准池 = 当年公办非退出，但**赋值范围 = 所有当年有数据的校**
        # （含民办与退出校，口径与普陀一致；见 build_v3_xh.py 的注释）。
        # ⇒ 民办/退出校的 rel 含义是「相对公办池中位」，不是「在其同类中的位置」。
        g = w.get('rel_%d' % y, '')
        if v is not None:
            if g in ('', None) or abs(float(g) - (v - med)) > 1e-4:
                bad.append((c, y, 'rel', g, '%.4f' % (v - med)))
        elif g not in ('', None):
            bad.append((c, y, 'rel', g, '空'))
        n2 += 1
print('位次/分位/z/rel 复算：%d 格（池 = 当年公办非退出）' % n2)

# 聚合列
n3 = 0
for c in RANKED:
    w = bym[c]
    cov = [y for y in YEARS if MEAN.get((c, y)) is not None]
    if w['years_included'] != str(len(cov)):
        bad.append((c, 0, 'cov', w['years_included'], len(cov)))
    rels = [float(w['rel_%d' % y]) for y in cov if w.get('rel_%d' % y) not in ('', None)]
    if abs(float(w['rel_avg']) - st.fmean(rels)) > 1e-4:
        bad.append((c, 0, 'rel_avg', w['rel_avg'], '%.4f' % st.fmean(rels)))
    n3 += 2
print('聚合列复算：%d 格' % n3)

if bad:
    print('\n❌ 不一致 %d 处（前 15）:' % len(bad))
    for c, y, k, g, e in bad[:15]:
        print('   %s %s %s: 表=%s 复算=%s' % (SH.get(c, c)[:18], y or '-', k, g, e))
    sys.exit(1)
print('\n✅ 宽表派生列逐格复算一致（共 %d 格，容差 %g）' % (n_checked + n2 + n3, TOL))
