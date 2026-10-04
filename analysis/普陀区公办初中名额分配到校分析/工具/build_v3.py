# -*- coding: utf-8 -*-
"""普陀区计算管线 v3：名额加权主口径 + 宽表扩容（单一事实源）。

口径变更（v3）：
- **主口径**：当年到校均分 = 计划名额加权平均  `Σ(score×quota)/Σ(quota)`（只取当年该校有分数的线）
- **对照口径**：等权算术平均（v2 口径），全部保留为 `_eq` 列
- 其余步骤（逐年名次 → 分位 P / Z / ZR → 三组结构口径 → 综合口径 → 时间权重）两链完全一致

输出（覆盖式重写）：
  宽表-初中水平-普陀区-2022-2026.csv        （≈170 列：逐年逐线原始分数/名额 + 全部派生）
  趋势分析-普陀区-2022-2026.csv             （基于加权主口径）
  rank-标准化-普陀区-2022-2026.csv          （P_wq 主 / P_eq 对照 / Z,ZR 两链）
  rank-多口径总表-普陀区-2022-2026.csv       （三组 × (eq,wq) + 综合 + 时间权重）
  rank-加权敏感性-普陀区-2022-2026.csv       （加权主口径下的时间权重敏感性）
"""
import csv, statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 共用算法实现：生成侧与校验侧同一份代码（implement.md 6.1，避免假门禁）
from pt_common import midrank, p_from_rank  # noqa: E402

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
# 简称 → 全名（宽表原始列用简称命名）；tier 决定是否区属基线
HS = [('华二普陀', '华东师范大学第二附属中学（普陀校区）', '区属'),
      ('二中', '上海市曹杨第二中学', '区属'),
      ('晋元', '上海市晋元高级中学', '区属'),
      ('宜川', '上海市宜川中学', '区属'),
      ('华二', '华东师范大学第二附属中学', '委属'),
      ('上中', '上海市上海中学', '委属'),
      ('复附', '复旦大学附属中学', '委属'),
      ('交附', '上海交通大学附属中学', '委属'),
      ('上师大', '上海师范大学附属中学', '委属')]
SHORT2FULL = {s: f for s, f, _ in HS}
FULL2SHORT = {f: s for s, f, _ in HS}
QU4 = [f for s, f, t in HS if t == '区属']
HEAD2 = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学']
TAIL2 = ['上海市晋元高级中学', '上海市宜川中学']
GROUPS = {'all': QU4, 'head': HEAD2, 'tail': TAIL2}
ALL9 = [f for _, f, _ in HS]
W_TIME = {'lin': {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
          'exp': {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
          'recent3': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1},
          # 3.1 新增：近 2 年（与嘉定口径一致，权重 0/0/0/1/1）
          'recent2': {2022: 0, 2023: 0, 2024: 0, 2025: 1, 2026: 1}}



def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


def num(v, nd=4):
    return '' if v is None else round(v, nd)


score_rows = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
plan_rows = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')
roster = {r['school_name']: r for r in load(f'{D_S}/初中名录-公办民办-普陀区-2026.csv')}

# ---- 排除「已并入他校」的行（1.1）：晋元西校 = 晋元附校（075069），2022 计划表同一行 ----
# 依据：【普陀】【2022】名额到校计划.pdf 第 2 页文本层 L52-L65 —— 该行含
# 075069 与 075083 **两个代码、两个校名，但只有一组名额（总计 49）**。
# 原 CSV 把这组数字各写了一遍给两个 code，使 2022 名额合计 660 = PDF 权威 611 + 49。
# 分数线表 2022 年 35 所计划校中唯独缺西校，佐证其不独立计量。
# 计划表已加 `merged_into` 列标注；此处排除，避免重复计入名额。
MERGED = {(r['junior_high_school_code'], r['year'])
          for r in plan_rows if r.get('merged_into')}
_before = sum(int(r['quota']) for r in plan_rows if r['year'] == '2022')
plan_rows = [r for r in plan_rows
             if (r['junior_high_school_code'], r['year']) not in MERGED]
score_rows = [r for r in score_rows
              if (r['junior_high_school_code'], r['year']) not in MERGED
              or not r.get('junior_high_school_code')]
_after = sum(int(r['quota']) for r in plan_rows if r['year'] == '2022')
assert _after == 611, f'排除并入校后 2022 名额合计={_after}，应为 PDF 权威值 611'
assert _before - _after == 49, f'排除量应为 49，实际 {_before - _after}'
print(f'已排除并入他校行 {len(MERGED)} 组；2022 名额 {_before} → {_after}（= PDF 611）')

# ---- 同一性归并（1.2）：兴陇中学 = 曹杨二中附属实验中学（同一官方代码 071048）----
# 依据：计划表中 071048 的年份**不重叠**（兴陇仅 2022、曹二实验 2023-2026），
# 属改名而非代码复用错误（后者会同年出现两次）。在**读取阶段**改写校名，
# 使两校合并为一行 5 年数据，避免同一所学校被拆成两行分别参与排名。
ALIAS = {'上海市兴陇中学': '上海市曹杨第二中学附属实验中学'}
for _rows in (score_rows, plan_rows):
    for _r in _rows:
        _n = _r['junior_high_school']
        if _n in ALIAS:
            _r['junior_high_school'] = ALIAS[_n]
            _r['alias_of'] = _n
# 断言：归并后同一代码不得再对应两个校名，否则说明判断有误
_names_by_code = {}
for _r in plan_rows:
    _names_by_code.setdefault(_r['junior_high_school_code'], set()).add(_r['junior_high_school'])
_dup = {k: v for k, v in _names_by_code.items() if len(v) > 1}
assert not _dup, f'归并后仍有代码对应多校名，归并判断有误：{_dup}'
assert len([r for r in plan_rows if r['junior_high_school'] == '上海市曹杨第二中学附属实验中学']) > 0, \
    '归并目标校名未出现在计划表中'

S = {}   # (校, 高中, 年) -> 分数
for r in score_rows:
    v = F(r['min_score'])
    if v is not None:
        S[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = v
Q = {}   # (校, 高中, 年) -> 名额
for r in plan_rows:
    Q[(r['junior_high_school'], r['senior_high_school'], int(r['year']))] = int(r['quota'])
CODE = {}
for r in plan_rows:
    CODE.setdefault(r['junior_high_school'], r['junior_high_school_code'])
schools = sorted({k[0] for k in S} | {k[0] for k in Q})


def group_mean(c, y, lines, chain):
    """链式均分：eq = 算术平均；wq = 计划名额加权（仅取有分数的线）。"""
    pairs = [(S[(c, h, y)], Q.get((c, h, y), 0)) for h in lines if (c, h, y) in S]
    if not pairs:
        return None
    if chain == 'eq':
        return st.fmean([v for v, _ in pairs])
    tw = sum(q for _, q in pairs)
    if tw <= 0:                       # 有分数但无名额（不该出现）→ 退化为等权
        return st.fmean([v for v, _ in pairs])
    return sum(v * q for v, q in pairs) / tw


def year_stats(mean_map, y):
    """当年池（该链有数据的全部初中）的 μ/σ/中位/IQR，并返回 {校: (P, Z, ZR)}。"""
    vals = {c: mean_map[(c, y)] for c in schools if (c, y) in mean_map}
    xs = sorted(vals.values())
    n = len(xs)
    if n < 2:
        return vals, n, {}
    mu, sg = st.fmean(xs), st.pstdev(xs)
    med = st.median(xs)
    iqr = xs[n * 3 // 4] - xs[n // 4]
    rs = iqr / 1.349 if iqr else None
    # 平均秩与分位均**共用** 工具/pt_common.py（implement.md 6.1）：
    # 生成侧与校验侧必须是同一份代码，否则校验属于「用同一种错误验证自己」。
    out = {}
    for c, r in midrank(list(vals.items())).items():
        v = vals[c]
        out[c] = (p_from_rank(r, n), (v - mu) / sg if sg else None,
                  (v - med) / rs if rs else None)
    return vals, n, out


# ---------- 逐年链：三组 × 两链 ----------
YEAR_MEAN = {}    # (group, chain) -> {(c,y): mean}
YEAR_PZR = {}     # (group, chain) -> {(c,y): (P, Z, ZR)}
YEAR_RANK = {}    # (group, chain) -> {(c,y): rank}
YEAR_N = {}       # (group, chain, y) -> pool n
for g, lines in GROUPS.items():
    for chain in ('eq', 'wq'):
        mm = {}
        for c in schools:
            for y in YEARS:
                v = group_mean(c, y, lines, chain)
                if v is not None:
                    mm[(c, y)] = v
        YEAR_MEAN[(g, chain)] = mm
        for y in YEARS:
            vals, n, pzr = year_stats(mm, y)
            YEAR_N[(g, chain, y)] = n
        # 名次
        rk = {}
        for y in YEARS:
            rk.update(midrank([((c, y), mm[(c, y)]) for c in schools if (c, y) in mm]))
        YEAR_RANK[(g, chain)] = rk

# 逐年 P / Z / ZR（两链 × 三组）
YEAR_PZR = {}
for g, lines in GROUPS.items():
    for chain in ('eq', 'wq'):
        mm = YEAR_MEAN[(g, chain)]
        d = {}
        for y in YEARS:
            vals, n, pzr = year_stats(mm, y)
            for c, t in pzr.items():
                d[(c, y)] = t
        YEAR_PZR[(g, chain)] = d


def agg(d, c):
    v = [d[(c, y)] for y in YEARS if (c, y) in d]
    return st.fmean(v) if v else None


def agg_tuple(d, c, i):
    v = [d[(c, y)][i] for y in YEARS if (c, y) in d]
    return st.fmean(v) if v else None


COV = lambda c: len([y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]])
RANKED = [c for c in schools if COV(c) == 5]        # 五年全勤（加权链）
FOUR_YEAR = [c for c in schools if COV(c) == 4]     # 恰好 4 年（与 v2 一致，仅曹杨二中附属实验中学）
TABLE = RANKED + FOUR_YEAR
assert COV  # 保留引用

# ---------- 趋势链（加权主口径） ----------
WIDE_SCHOOLS = [c for c in schools if COV(c) >= 1]
ROWS_BY_NAME = {}

EXITED = {
    '上海市光新学校': '暂停招生（2024 年起初中部停招，2025 年起无毕业生；学校仍存在）',
    '上海市武宁中学': '已并入同济大学第二附属中学（普陀区发改委 2022-08-22）；学校仍存在',
}
# ownership 回退：两校经公开资料核为公办（光新=公办九年一贯制、武宁=公立初级中学），
# 但**不在 2026 名录内**，故不能从 roster 取到；此处显式登记，不留空。
OWNERSHIP_FALLBACK = {
    '上海市光新学校': '公办',
    '上海市武宁中学': '公办',
}
FORMER_NAMES = {'上海市曹杨第二中学附属实验中学': '上海市兴陇中学'}



# ---- 2.3 逐年相对位置 rel ----
# 口径对齐嘉定（build_v3_jd.py L219-226）：
#   · **基准池** = 当年有数据的**公办**校（嘉定用 PUB）；普陀额外**排除 exited 校**
#     （光新暂停招生 / 武宁并入同济二附中，已退出名额到校体系，其分数是历史遗留，
#      纳入会污染基准）。这与 2.1 的 row_type 分类一致。
#   · **赋值范围** = 所有当年有数据的校（与嘉定相同，`for x in schools`），
#     因此民办与退出校**自身也有 rel 值**。
# ⚠️ 语义提醒：民办 / 退出校的 rel 含义是「相对公办池中位」，
#    **不是**「在其同类（民办 / 退出校）中的位置」。引用时必须写明。
#    趋势分析只用 RANKED，不受影响（见下方 rel 复用处的注释）。
# 实测：两种基准池（五年全勤 vs 当年公办非退出）的中位数差 ≤0.51 分且为**同量平移**，
#      故 delta_rel 与 SEN 不受影响（普陀 pool 逐年 32/32/34/36/36）。
OWNER = {c: (roster.get(c, {}).get('ownership', '') or OWNERSHIP_FALLBACK.get(c, ''))
         for c in WIDE_SCHOOLS}
REL_POOL, REL_MED, REL = {}, {}, {}
for _y in YEARS:
    # 注意 YEAR_MEAN 的键是 (c, y)，不是 (y, c)
    _pool = [c for c in WIDE_SCHOOLS
             if (c, _y) in YEAR_MEAN[('all', 'wq')]
             and OWNER.get(c) == '公办' and c not in EXITED]
    assert _pool, f'{_y} 年 rel 基准池为空——检查 OWNER 取值与 exited 过滤'
    REL_POOL[_y] = len(_pool)
    _med = st.median(sorted(YEAR_MEAN[('all', 'wq')][(c, _y)] for c in _pool))
    REL_MED[_y] = _med
    for _c in WIDE_SCHOOLS:
        if (_c, _y) in YEAR_MEAN[('all', 'wq')]:
            REL[(_c, _y)] = YEAR_MEAN[('all', 'wq')][(_c, _y)] - _med
print('rel 基准池（当年公办非退出）：'
      + ' '.join(f'{y}={REL_POOL[y]}所/中位{REL_MED[y]:.2f}' for y in YEARS))


# 趋势链与宽表共用同一 rel（口径 = 当年公办非退出池中位，见 2.3 注释）。
# 原实现以 RANKED（五年全勤）为基准，与宽表口径不一致，会出现两个 rel。
# 实测两种中位数差 ≤0.51 分且为**同量平移**，故 delta_rel / sen 不受影响。
rel = {k: v for k, v in REL.items() if k[0] in RANKED}
assert rel, '趋势链 rel 为空：REL 未覆盖 RANKED'


def sen_slope(pts):
    xs = sorted(pts)
    sl = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0])
          for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j][0] != xs[i][0]]
    return st.median(sl) if sl else None


def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    den = (sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5
    return sum((p - mx) * (q - my) for p, q in zip(rx, ry)) / den if den else None


trend = {}
for c in RANKED:
    pts = [(y, rel[(c, y)]) for y in YEARS if (c, y) in rel]
    pts3 = [p for p in pts if p[0] >= 2024]
    trend[c] = {'rel_first': pts[0][1], 'rel_last': pts[-1][1],
                'delta_rel': pts[-1][1] - pts[0][1],
                'sen': sen_slope(pts), 'spearman': spearman([p[0] for p in pts], [p[1] for p in pts]),
                'sen_recent3': sen_slope(pts3) if len(pts3) >= 2 else None}
# 收敛回归
xs = [trend[c]['rel_first'] for c in RANKED]
ys = [trend[c]['delta_rel'] for c in RANKED]
mx, my = st.fmean(xs), st.fmean(ys)
b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
a = my - b * mx
pred = [a + b * x for x in xs]
resid = [y - p for y, p in zip(ys, pred)]
sd = st.pstdev(resid)
r2 = 1 - sum(r * r for r in resid) / sum((y - my) ** 2 for y in ys)
for c, pr, rs in zip(RANKED, pred, resid):
    trend[c]['convergence_pred'] = pr
    trend[c]['residual'] = rs
    trend[c]['residual_z'] = rs / sd if sd else None
    trend[c]['beyond_convergence'] = int(abs(rs / sd) >= 1) if sd else 0

# ---------- 输出 1：宽表（扩容） ----------
wide_cols = ['junior_high_school', 'junior_high_school_code', 'ownership',
             'row_type', 'exit_reason', 'junior_high_school_former_names',
             'rel_avg', 'rel_pool_n',
             'years_included', 'years_list', 'ranked']
for s, full, _ in HS:
    for y in YEARS:
        wide_cols.append(f'score_{s}_{y}')
for s, full, _ in HS:
    for y in YEARS:
        wide_cols.append(f'quota_{s}_{y}')
for y in YEARS:
    wide_cols += [f'mean_score_base4_eq_{y}', f'mean_score_base4_wq_{y}',
                  f'rank_base4_eq_{y}', f'rank_base4_wq_{y}',
                  f'valid_pairs_{y}', f'quota4_{y}', f'rel_{y}',
                  f'P_eq_{y}', f'P_wq_{y}', f'Z_eq_{y}', f'Z_wq_{y}', f'ZR_eq_{y}', f'ZR_wq_{y}']
wide_cols += [
    'quota4_avg', 'quota_all_avg',
    'mean_rank_base4_wq_avg', 'mean_rank_base4_wq_median', 'mean_rank_base4_wq_var',
    'mean_rank_base4_eq_avg', 'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
    'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
    'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq',
    'P_wq_all', 'rank_P_wq_all', 'P_wq_head', 'rank_P_wq_head',
    'P_wq_tail', 'rank_P_wq_tail', 'P_wq_comb', 'rank_P_wq_comb',
    'P_eq_all', 'rank_P_eq_all', 'P_eq_head', 'rank_P_eq_head',
    'P_eq_tail', 'rank_P_eq_tail', 'P_eq_comb', 'rank_P_eq_comb',
    'Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb',
]
# 时间权重列**由 W_TIME 动态生成**：此前是硬编码清单，新增档位会静默丢列
# （P_recent2 曾整列缺失而无人察觉）。W_TIME 是唯一事实源。
for _k in W_TIME:
    wide_cols += [f'P_{_k}', f'rank_P_{_k}']
assert not (set(f'P_{k}' for k in W_TIME) & set(wide_cols[:-2 * len(W_TIME)])), \
    '时间权重列重复'
for _k in W_TIME:
    assert f'P_{_k}' in wide_cols and f'rank_P_{_k}' in wide_cols, \
        f'W_TIME 中的 {_k} 未进入 wide_cols，会静默丢列'


# ---- 2.1 ownership 补全 + 2.2 row_type 分类 ----
# 2026 名录只覆盖当年在读学校，光新（暂停招生）与武宁（已并入同济二附中）
# 已退出名录 ⇒ ownership 为空。此处按 1.1 官网核实结论补全，并按四分类打 row_type。
# 依据见 data/普陀区/学校/初中校名别名表-普陀区.csv（evidence 列）。

# 3.2 / 3.3 按口径取池：「近 N 年」列的池 = 当年有该 N 年全部数据的公办非退出校。
# 主排序（all/head/tail/comb）与 lin/exp 维持主池 TABLE（32 所），不动。
def _has_all_years(c, ys):
    return all((c, y) in YEAR_MEAN[('all', 'wq')] for y in ys)


_PUB_OK = lambda c: OWNER.get(c) == '公办' and c not in EXITED
POOL_BY_TIME = {
    'recent2': sorted(c for c in WIDE_SCHOOLS if _PUB_OK(c) and _has_all_years(c, [2025, 2026])),
    'recent3': sorted(c for c in WIDE_SCHOOLS if _PUB_OK(c) and _has_all_years(c, [2024, 2025, 2026])),
}
def row_type_of(c, own, n_years):
    """四分类：民办排除 / 退出 / 入榜 / 短样本。互斥且穷尽。"""
    if own == '民办':
        return 'excluded_private'
    if c in EXITED:
        return 'exited'
    if n_years >= 4:
        return 'ranked'
    return 'short_sample'


rows_out = []
for c in WIDE_SCHOOLS:
    cov = [y for y in YEARS if (c, y) in YEAR_MEAN[('all', 'wq')]]
    q4 = [sum(Q.get((c, h, y), 0) for h in QU4) for y in cov]
    qa = [sum(Q.get((c, h, y), 0) for h in ALL9) for y in cov]
    own = roster.get(c, {}).get('ownership', '') or OWNERSHIP_FALLBACK.get(c, '')
    d = {'junior_high_school': c, 'junior_high_school_code': CODE.get(c, ''),
         'ownership': own,
         'exit_reason': EXITED.get(c, ''),
         'junior_high_school_former_names': FORMER_NAMES.get(c, ''),
         'row_type': row_type_of(c, own, len(cov)),
         
         'years_included': len(cov), 'years_list': ';'.join(str(y) for y in cov),
         'ranked': 1 if c in TABLE else 0}
    for s, full, _ in HS:
        for y in YEARS:
            d[f'score_{s}_{y}'] = S.get((c, full, y), '')
    ROWS_BY_NAME[d['junior_high_school']] = d
    for s, full, _ in HS:
        for y in YEARS:
            d[f'quota_{s}_{y}'] = Q.get((c, full, y), '')
    for y in YEARS:
        d[f'mean_score_base4_eq_{y}'] = num(YEAR_MEAN[('all', 'eq')].get((c, y)), 3)
        d[f'mean_score_base4_wq_{y}'] = num(YEAR_MEAN[('all', 'wq')].get((c, y)), 3)
        d[f'rank_base4_eq_{y}'] = num(YEAR_RANK[('all', 'eq')].get((c, y)), 2)
        d[f'rank_base4_wq_{y}'] = num(YEAR_RANK[('all', 'wq')].get((c, y)), 2)
        d[f'valid_pairs_{y}'] = sum(1 for h in QU4 if (c, h, y) in S)
        d[f'quota4_{y}'] = sum(Q.get((c, h, y), 0) for h in QU4)
        d[f'rel_{y}'] = num(REL.get((c, y)), 4)
        for chain, tag in (('eq', 'eq'), ('wq', 'wq')):
            t = YEAR_PZR[('all', chain)].get((c, y))
            d[f'P_{tag}_{y}'] = num(t[0], 6) if t else ''
            d[f'Z_{tag}_{y}'] = num(t[1], 4) if t else ''
            d[f'ZR_{tag}_{y}'] = num(t[2], 4) if t else ''
    d['quota4_avg'] = num(st.fmean(q4), 4)
    d['quota_all_avg'] = num(st.fmean(qa), 4)
    mr = [YEAR_RANK[('all', 'wq')][(c, y)] for y in cov]
    d['mean_rank_base4_wq_avg'] = num(st.fmean(mr), 4)
    d['mean_rank_base4_wq_median'] = num(st.median(mr), 4)
    d['mean_rank_base4_wq_var'] = num(st.pvariance(mr), 4) if len(mr) > 1 else ''
    d['mean_rank_base4_eq_avg'] = num(agg(YEAR_RANK[('all', 'eq')], c), 4)
    d['mean_rank_base4_w_linear'] = num(
        sum(W_TIME['lin'][y] * YEAR_RANK[('all', 'wq')][(c, y)] for y in cov)
        / sum(W_TIME['lin'][y] for y in cov), 4)
    d['mean_rank_base4_w_exp'] = num(
        sum(W_TIME['exp'][y] * YEAR_RANK[('all', 'wq')][(c, y)] for y in cov)
        / sum(W_TIME['exp'][y] for y in cov), 4)
    rows_out.append(d)

# 聚合 P/Z/ZR（三组 × 两链 + 综合）与名次
P_agg, Z_agg, ZR_agg = {}, {}, {}
for g in GROUPS:
    for chain in ('eq', 'wq'):
        for c in WIDE_SCHOOLS:
            P_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 0)
            Z_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 1)
            ZR_agg[(g, chain, c)] = agg_tuple(YEAR_PZR[(g, chain)], c, 2)
MISSING = []
for c in WIDE_SCHOOLS:
    for chain in ('eq', 'wq'):
        for tag, dic in (('P', P_agg), ('Z', Z_agg), ('ZR', ZR_agg)):
            vals = [dic[(g, chain, c)] for g in GROUPS if dic[(g, chain, c)] is not None]
            if len(vals) < len(GROUPS):
                MISSING.append((c, chain, tag, len(vals)))
            dic[('comb', chain, c)] = st.fmean(vals) if vals else None
if MISSING:
    print('缺少部分分组数据的 (校, 链, 指标, 可用组数)：', MISSING[:8], '共', len(MISSING))


def ranks_of(dic, pool=None):
    """跨年聚合名次 = 顺序秩（降序 1..N），保证名次唯一便于排名表。

    注意：当年位次 rank_base4_{y} 用的是**平均秩**（并列同名次），
    两者口径不同是有意的 —— 聚合名次须唯一，当年位次须反映并列。
    代价：若聚合值出现并列，顺序秩会给出不同名次（并列者实际应同分）。
    故此处显式检测并列并警告，避免静默失真（嘉定 Spearman 并列问题的同类防护）。
    """
    _pool = TABLE if pool is None else pool
    ok = [(c, dic[c]) for c in _pool if dic.get(c) is not None]
    vals = [v for _, v in ok]
    dup = sorted({v for v in vals if vals.count(v) > 1})
    if dup:
        _names = [c for c, v in ok if v in dup]
        print(f'⚠️ 聚合口径 {len(ok)} 所中有 {len(dup)} 个并列值，'
              f'顺序秩会区分并列者：{[(c, round(v, 6)) for c, v in ok if v in dup]}')
    o = sorted(ok, key=lambda t: -t[1])
    return {c: i for i, (c, _) in enumerate(o, 1)}


RK = {}
for g in list(GROUPS) + ['comb']:
    for chain in ('eq', 'wq'):
        RK[(g, chain)] = ranks_of({c: P_agg[(g, chain, c)] for c in TABLE})
for chain in ('eq', 'wq'):
    for tag, dic in (('Z', Z_agg), ('ZR', ZR_agg)):
        RK[(tag + '_' + chain,)] = ranks_of({c: dic[('comb', chain, c)] for c in TABLE})
# 时间权重（加权主口径）
for c in WIDE_SCHOOLS:
    cov = [y for y in YEARS if (c, y) in YEAR_PZR[('all', 'wq')]]
    for k, w in W_TIME.items():
        num_ = sum(w[y] * YEAR_PZR[('all', 'wq')][(c, y)][0] for y in cov if w[y] > 0)
        den = sum(w[y] for y in cov if w[y] > 0)
        P_agg[(k, 'wq', c)] = num_ / den if den else None
# 3.4 lin/exp 维持主池；recent2/recent3 用各自「有该 N 年全部数据」的池
for k in W_TIME:
    _pool = POOL_BY_TIME.get(k, TABLE)
    RK[(k, 'wq')] = ranks_of({c: P_agg[(k, 'wq', c)] for c in _pool}, pool=_pool)
    _got = sorted(RK[(k, 'wq')].values())
    assert _got == list(range(1, len(_got) + 1)), \
        f'{k} 名次不连续或缺号：{_got[:5]}…{_got[-3:]}（池 {len(_pool)} 所）'
    print(f'  口径 {k:<8} 池 {len(_pool):>2} 所  名次 1–{len(_got)} 连续无缺号')
print('入榜样本:', len(TABLE), '｜4 年校:', [c for c in FOUR_YEAR])

# 写回宽表聚合列
by_name = {d['junior_high_school']: d for d in rows_out}
for c in WIDE_SCHOOLS:
    d = by_name[c]
    R = lambda key: RK[key].get(c, '')
    d['P_wq'] = num(P_agg[('all', 'wq', c)], 6)
    d['rank_P_wq'] = R(('all', 'wq'))
    d['P_eq'] = num(P_agg[('all', 'eq', c)], 6)
    d['rank_P_eq'] = R(('all', 'eq'))
    d['shift_wq_eq'] = (RK[('all', 'eq')][c] - RK[('all', 'wq')][c]) if c in TABLE else ''
    d['Z_wq'] = num(Z_agg[('all', 'wq', c)], 4)
    d['rank_Z_wq'] = R(('Z_wq',))
    d['ZR_wq'] = num(ZR_agg[('all', 'wq', c)], 4)
    d['rank_ZR_wq'] = R(('ZR_wq',))
    for g, tag in [('all', 'all'), ('head', 'head'), ('tail', 'tail'), ('comb', 'comb')]:
        d[f'P_wq_{tag}'] = num(P_agg[(g, 'wq', c)], 6)
        d[f'rank_P_wq_{tag}'] = R((g, 'wq'))
        d[f'P_eq_{tag}'] = num(P_agg[(g, 'eq', c)], 6)
        d[f'rank_P_eq_{tag}'] = R((g, 'eq'))
    d['Z_wq_comb'] = num(Z_agg[('comb', 'wq', c)], 4)
    d['rank_Z_wq_comb'] = R(('Z_wq',))
    d['ZR_wq_comb'] = num(ZR_agg[('comb', 'wq', c)], 4)
    d['rank_ZR_wq_comb'] = R(('ZR_wq',))
    for k in W_TIME:
        d[f'P_{k}'] = num(P_agg.get((k, 'wq', c)), 6)
        d[f'rank_P_{k}'] = R((k, 'wq'))
    _rv = [REL[(c, y)] for y in YEARS if (c, y) in REL]
    d['rel_avg'] = num(st.fmean(_rv), 4) if _rv else ''
    d['rel_pool_n'] = REL_POOL.get(cov[-1], '') if cov else ''

# ============ 2.1 / 2.2 值域断言（写盘前全部完成，规范陷阱 14）============
_own = [d['ownership'] for d in rows_out]
_blank = [d['junior_high_school'] for d in rows_out if not d['ownership'].strip()]
assert not _blank, f'ownership 存在空值：{_blank}'
assert set(_own) <= {'公办', '民办'}, f'ownership 值域越界：{set(_own)}'

_RT = {'ranked', 'short_sample', 'exited', 'excluded_private'}
_rt = [d['row_type'] for d in rows_out]
assert set(_rt) <= _RT, f'row_type 值域越界：{set(_rt) - _RT}'
# 四类互斥且穷尽：每行恰一类，且 exited/excluded_private 不进排名
for d in rows_out:
    n_own, n_rt = d['ownership'], d['row_type']
    if n_own == '民办':
        assert n_rt == 'excluded_private', f'{n_own} 民办行 row_type={n_rt}'
        assert d['ranked'] == 0, '民办不得入榜'
    elif n_rt == 'exited':
        assert d['exit_reason'].strip(), f'{d["junior_high_school"]} exited 但缺 exit_reason'
        assert d['ranked'] == 0, '退出校不得入榜'
    elif n_rt == 'ranked':
        assert d['years_included'] >= 4, f'{d["junior_high_school"]} years={d["years_included"]} 不应 ranked'
        assert d['ranked'] == 1, 'ranked 行与 ranked 标记不一致'
    else:
        assert d['years_included'] < 4, f'{d["junior_high_school"]} years={d["years_included"]} 应为 short_sample'
# former_names 有值时，对应旧名不得再作为独立行出现
_names = {d['junior_high_school'] for d in rows_out}
for d in rows_out:
    _fn = d['junior_high_school_former_names']
    if _fn.strip():
        assert _fn not in _names, f'旧名 {_fn} 仍作为独立行存在，归并未生效'
        assert d['row_type'] == 'ranked', f'{d["junior_high_school"]} 有 former_names 却非 ranked'
print(f'2.1/2.2 断言通过：ownership 无空值（{sorted(set(_own))}）；'
      f'row_type {sorted(set(_rt))}；四类互斥穷尽')

with open(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=wide_cols)
    w.writeheader()
    for d in sorted(rows_out, key=lambda d: (d['rank_P_wq'] if d['rank_P_wq'] != '' else 999)):
        w.writerow({k: d.get(k, '') for k in wide_cols})

# ---------- 输出 2：趋势分析（加权主口径） ----------
tcols = ['junior_high_school', 'n_years', 'rel_first', 'rel_last', 'delta_rel', 'sen', 'spearman',
         'sen_recent3', 'convergence_pred', 'residual', 'residual_z', 'beyond_convergence']
with open(f'{D_A}/趋势分析-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=tcols)
    w.writeheader()
    for c in sorted(RANKED, key=lambda c: RK[('all', 'wq')][c]):
        t = trend[c]
        w.writerow({'junior_high_school': c, 'n_years': 5,
                    'rel_first': num(t['rel_first'], 3), 'rel_last': num(t['rel_last'], 3),
                    'delta_rel': num(t['delta_rel'], 3), 'sen': num(t['sen'], 4),
                    'spearman': num(t['spearman'], 4), 'sen_recent3': num(t['sen_recent3'], 4),
                    'convergence_pred': num(t['convergence_pred'], 3),
                    'residual': num(t['residual'], 3), 'residual_z': num(t['residual_z'], 3),
                    'beyond_convergence': t['beyond_convergence']})

# ---------- 输出 3：rank-标准化 ----------
rcols = ['junior_high_school', 'junior_high_school_code', 'n_years', 'ranked',
         'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq', 'shift_wq_eq',
         'Z_wq', 'ZR_wq', 'rank_Z_wq', 'rank_ZR_wq', 'Z_eq', 'ZR_eq',
         'mean_rank_wq_avg', 'mean_rank_eq_avg']
with open(f'{D_A}/rank-标准化-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=rcols)
    w.writeheader()
    for c in WIDE_SCHOOLS:
        d = by_name[c]
        w.writerow({'junior_high_school': c, 'junior_high_school_code': d['junior_high_school_code'],
                    'n_years': d['years_included'], 'ranked': d['ranked'],
                    'P_wq': d['P_wq'], 'rank_P_wq': d['rank_P_wq'],
                    'P_eq': d['P_eq'], 'rank_P_eq': d['rank_P_eq'], 'shift_wq_eq': d['shift_wq_eq'],
                    'Z_wq': d['Z_wq'], 'ZR_wq': d['ZR_wq'],
                    'rank_Z_wq': d['rank_Z_wq'], 'rank_ZR_wq': d['rank_ZR_wq'],
                    'Z_eq': num(Z_agg[('all', 'eq', c)], 4), 'ZR_eq': num(ZR_agg[('all', 'eq', c)], 4),
                    'mean_rank_wq_avg': d['mean_rank_base4_wq_avg'],
                    'mean_rank_eq_avg': d['mean_rank_base4_eq_avg']})

# ---------- 输出 4：rank-多口径总表 ----------
mcols = ['junior_high_school', 'n_years',
         'P_wq_comb', 'rank_P_wq_comb', 'P_wq_all', 'rank_P_wq_all',
         'P_wq_head', 'rank_P_wq_head', 'P_wq_tail', 'rank_P_wq_tail',
         'P_eq_comb', 'rank_P_eq_comb', 'P_eq_all', 'rank_P_eq_all',
         'P_eq_head', 'rank_P_eq_head', 'P_eq_tail', 'rank_P_eq_tail',
         'shift_comb_wq_eq', 'Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb',
         'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp', 'P_recent3', 'rank_P_recent3',
         'mean_rank_wq_avg', 'quota4_avg', 'quota_all_avg']
with open(f'{D_A}/rank-多口径总表-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=mcols)
    w.writeheader()
    for d in sorted([r for r in rows_out if r['junior_high_school'] in TABLE],
                    key=lambda d: d['rank_P_wq_comb']):
        d['shift_comb_wq_eq'] = RK[('comb', 'eq')][d['junior_high_school']] - d['rank_P_wq_comb']
        d['n_years'] = d['years_included']
        w.writerow({k: d.get(k, '') for k in mcols})

# ---------- 输出 5：rank-加权敏感性（加权主口径） ----------
scols = ['junior_high_school', 'n_years', 'P_eq', 'P_lin', 'P_exp', 'P_recent3',
         'rank_eq', 'rank_lin', 'rank_exp', 'rank_recent3',
         'shift_lin', 'shift_exp', 'shift_recent3']
with open(f'{D_A}/rank-加权敏感性-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=scols)
    w.writeheader()
    for c in sorted(TABLE, key=lambda c: RK[(('all', 'wq'))][c]):
        d = by_name[c]
        r = {k: RK[(k, 'wq')][c] for k in W_TIME}
        w.writerow({'junior_high_school': c, 'n_years': d['years_included'],
                    'P_eq': d['P_wq'], 'P_lin': d['P_lin'], 'P_exp': d['P_exp'],
                    'P_recent3': d['P_recent3'],
                    'rank_eq': d['rank_P_wq'], 'rank_lin': r['lin'], 'rank_exp': r['exp'],
                    'rank_recent3': r['recent3'],
                    'shift_lin': r['lin'] - d['rank_P_wq'],
                    'shift_exp': r['exp'] - d['rank_P_wq'],
                    'shift_recent3': r['recent3'] - d['rank_P_wq']})

# ---------- 控制台 ----------
print(f'宽表列数 {len(wide_cols)}，行数 {len(rows_out)}')
print(f'入榜 {len(TABLE)} 所（五年全勤 {len(RANKED)} + 4 年 {len(FOUR_YEAR)}）')
print(f'\n=== 加权主口径 综合排名（前 10）与等权对照 ===')
for c in sorted(TABLE, key=lambda c: RK[('comb', 'wq')][c])[:10]:
    d = by_name[c]
    print(f"  {d['rank_P_wq_comb']:>2} {c.replace('上海市',''):<24} 加权综合={d['P_wq_comb']} "
          f"等权综合第{d['rank_P_eq_comb']:>2}（位次差 {d['shift_comb_wq_eq']:+d}） "
          f"全身{ d['rank_P_wq_all'] }/头{ d['rank_P_wq_head'] }/尾{ d['rank_P_wq_tail'] }")
print(f'\n收敛回归：b={b:.3f}  R²={r2:.3f}  残差σ={sd:.2f}')
print(f'规模相关性：ρ(名额, 加权名次)={spearman([F(by_name[c]["quota4_avg"]) for c in TABLE], [RK[("all","wq")][c] for c in TABLE]):+.3f}')
print('年限池量：', {k: YEAR_N[k] for k in sorted(YEAR_N)})
