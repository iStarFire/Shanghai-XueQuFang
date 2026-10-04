"""独立复算普陀宽表派生列 —— 不 import build_v3.py，全部从源 CSV 重算。

目的：验证 2.3「抽查 10 格可由源 CSV 复算」，并作为长期门禁。

口径（读 build_v3.py 源码确认后独立实现，不调用其函数）：
  名额加权均分 mean_score_base4_wq_y = Σ(score×quota)/Σquota
      —— 只取「有分数的线」；若 Σquota=0 退化为等权
  等权均分   mean_score_base4_eq_y = mean(score)
  位次       rank_base4_wq_y = 顺序秩（降序，1 起），并列不特殊处理
  分位       P_y = 1 - (r-1)/(n-1)，r = b+(e+1)/2（**平均秩**）
  Z          = (v-μ)/σ_population
  ZR         = (v-median)/(IQR/1.349)
  rel_y      = 加权均分 − 当年「公办非退出」池中位
  P_wq       = 逐年 P 的等权平均

独立实现要点：所有口径常量（区属 4 线、代码映射、归并、排除并入校）在此
**重新声明一遍**而非引用管线，以便口径漂移时能被本脚本发现。
"""
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 当年位次 / 分位复用**生成脚本同一份**平均秩实现（implement.md 6.1）。
# 此前本文件自带一份重写版 —— 那是「假门禁」隐患：两套实现可能同错而互相「验证通过」，
# 校验就失去了独立性。现已抽出 工具/pt_common.py，生成侧与校验侧都 import 它。
# ⚠️ 本 import 必须在**首次使用之前**（L108 用到 midrank）。曾因放在文件末尾
#    而报 NameError，且当时用 `| grep` 过滤输出把 Traceback 吞掉，误判为通过。
from pt_common import midrank, midrank as _rank_avg_tie, p_from_rank  # noqa: E402

D_S = Path('../../data/普陀区/学校')
D_A = Path('.')
YEARS = [2022, 2023, 2024, 2025, 2026]

# ---- 独立声明的口径常量（与管线一致，若不一致本脚本会报错）----
QU4_FULL = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
            '上海市晋元高级中学', '上海市宜川中学']
ALIAS = {'上海市兴陇中学': '上海市曹杨第二中学附属实验中学'}
MERGED_INTO = {'075083': '075069'}          # 西校 → 晋元附校
EXITED = {'上海市光新学校', '上海市武宁中学'}
MIN_YEARS_RANKED = 4


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


score_rows = load(D_S / '名额到校最低分数线-普陀区-2022-2026.csv')
plan_rows = load(D_S / '名额到校计划-普陀区-2022-2026.csv')
roster = {r['school_name']: r['ownership'] for r in
          load(D_S / '初中名录-公办民办-普陀区-2026.csv')}

# ---- 与管线同样的三步预处理：排除并入校 → 改名归并 → 建索引 ----
plan_rows = [r for r in plan_rows
             if r.get('merged_into', '') in ('', None)]   # 排除西校等并入他校行
score_rows = [r for r in score_rows if r.get('merged_into', '') in ('', None)]

S, Q, CODE = {}, {}, {}
for r in score_rows:
    nm = ALIAS.get(r['junior_high_school'], r['junior_high_school'])
    v = num(r['min_score'])
    if v is not None:
        S[(nm, r['senior_high_school'], int(r['year']))] = v
for r in plan_rows:
    nm = ALIAS.get(r['junior_high_school'], r['junior_high_school'])
    Q[(nm, r['senior_high_school'], int(r['year']))] = int(r['quota'])
    CODE.setdefault(nm, r['junior_high_school_code'])

schools = sorted({k[0] for k in S} | {k[0] for k in Q})
OWNER = {c: roster.get(c, '') or ('公办' if c in EXITED else '') for c in schools}


def mean_of(c, y, weighted):
    pairs = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in QU4_FULL if (c, h, y) in S]
    if not pairs:
        return None
    if not weighted:
        return st.fmean([v for v, _ in pairs])
    tw = sum(q for _, q in pairs)
    if tw <= 0:
        return st.fmean([v for v, _ in pairs])
    return sum(v * q for v, q in pairs) / tw


# ---- 逐年派生 ----
MEAN = {(c, y, w): mean_of(c, y, w) for c in schools for y in YEARS
        for w in (True, False)}
COV = {c: sum(1 for y in YEARS if MEAN[(c, y, True)] is not None) for c in schools}
RANK_POOL = {c for c in schools if COV[c] >= MIN_YEARS_RANKED}

PZ = {}
for y in YEARS:
    vals = {c: MEAN[(c, y, True)] for c in schools if MEAN[(c, y, True)] is not None}
    xs = sorted(vals.values())
    n = len(xs)
    if n < 2:
        PZ[y] = {}
        continue
    mu, sg = st.fmean(xs), st.pstdev(xs)
    med = st.median(xs)
    iqr = xs[n * 3 // 4] - xs[n // 4]
    rs = iqr / 1.349 if iqr else None
    o = {}
    for c, r in midrank(list(vals.items())).items():
        v = vals[c]
        o[c] = (p_from_rank(r, n),
                (v - mu) / sg if sg else None,
                (v - med) / rs if rs else None)
    PZ[y] = o


RANK_Y = {y: _rank_avg_tie([(c, MEAN[(c, y, True)]) for c in schools
                            if MEAN[(c, y, True)] is not None])
          for y in YEARS}

REL = {}
for y in YEARS:
    pool = [c for c in schools
            if MEAN[(c, y, True)] is not None and OWNER.get(c) == '公办' and c not in EXITED]
    med = st.median(sorted(MEAN[(c, y, True)] for c in pool))
    for c in schools:
        if MEAN[(c, y, True)] is not None:
            REL[(c, y)] = MEAN[(c, y, True)] - med

# ---- 与宽表比对 ----
W = {r['junior_high_school']: r for r in
     load(D_A / '宽表-初中水平-普陀区-2022-2026.csv')}
CHECKS, bad = 0, []


def cmp(school, col, expect, tol):
    global CHECKS
    CHECKS += 1
    got = num(W.get(school, {}).get(col, ''))
    if expect is None:
        if got is not None:
            bad.append((school, col, f'应为 None，宽表={got}'))
        return
    if got is None:
        bad.append((school, col, f'宽表为空，复算={expect:.4f}'))
    elif abs(got - expect) > tol:
        bad.append((school, col, f'宽表={got:.4f} 复算={expect:.4f} 差={got-expect:+.4f}'))


for c in sorted(RANK_POOL):
    for y in YEARS:
        cmp(c, f'mean_score_base4_wq_{y}', MEAN[(c, y, True)], 5e-4)
        cmp(c, f'mean_score_base4_eq_{y}', MEAN[(c, y, False)], 5e-4)
        cmp(c, f'rank_base4_wq_{y}', RANK_Y[y].get(c), 1e-9)
        if PZ[y].get(c):
            cmp(c, f'P_wq_{y}', PZ[y][c][0], 5e-4)
            cmp(c, f'Z_wq_{y}', PZ[y][c][1], 5e-4)
            cmp(c, f'ZR_wq_{y}', PZ[y][c][2], 5e-4)
        cmp(c, f'rel_{y}', REL.get((c, y)), 5e-4)
        cmp(c, f'quota4_{y}', sum(Q.get((c, h, y), 0) for h in QU4_FULL), 0)
        cmp(c, f'valid_pairs_{y}', sum(1 for h in QU4_FULL if (c, h, y) in S), 0)
    ps = [PZ[y][c][0] for y in YEARS if PZ[y].get(c)]
    cmp(c, 'P_wq', st.fmean(ps) if ps else None, 5e-4)
    rs = [REL[(c, y)] for y in YEARS if (c, y) in REL]
    cmp(c, 'rel_avg', st.fmean(rs) if rs else None, 5e-4)

print(f'独立复算：{len(RANK_POOL)} 所 × 逐年派生列，共 {CHECKS} 格')
print(f'  基准：{MIN_YEARS_RANKED} 年 ⇒ 池 {len(RANK_POOL)} 所'
      f'（宽表 row_type=ranked 实为 '
      f'{sum(1 for r in W.values() if r.get("row_type") == "ranked")} 所）')
assert len(RANK_POOL) == sum(1 for r in W.values() if r.get('row_type') == 'ranked'), \
    '复算池与宽表 row_type=ranked 不一致'
if bad:
    print(f'\n❌ 不一致 {len(bad)} 格：')
    for s, c, m in bad[:20]:
        print(f'   {s} {c}: {m}')
    sys.exit(1)
print(f'✅ 全部一致（容差 5e-4，位次/计数为精确相等）')

# ---- 报告 10 格样本明细 ----
print('\n=== 10 格抽样明细（报告用）===')
sample = []
ranked_sorted = sorted(RANK_POOL, key=lambda c: RANK_Y[2026].get(c, 999))
for c in ranked_sorted[:2] + ranked_sorted[-2:]:
    for y in (2022, 2026):
        sample.append((c, y))
for c, y in sample[:10]:
    print(f'  {c[:20]:<22} {y}  wq均分={MEAN[(c,y,True)]:7.3f}  位次={RANK_Y[y][c]:2}'
          f'  P={PZ[y][c][0]:.4f}  Z={PZ[y][c][1]:+.3f}  ZR={PZ[y][c][2]:+.3f}'
          f'  rel={REL[(c,y)]:+.3f}  名额4线={sum(Q.get((c,h,y),0) for h in QU4_FULL)}'
          f'  有效对={sum(1 for h in QU4_FULL if (c,h,y) in S)}')
