#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""徐汇区名额到校分析 —— 数据层 v3（按嘉定/普陀方法重做）

与旧管线 `build_wide.py` 的关系
--------------------------------
`build_wide.py` 是**旧口径**：主指标为 `mean_rank_base4`（平均名次），
只输出公办 28 行，无 row_type / rel / 多口径。本脚本是**新口径**重建，
产出 `宽表-初中水平-徐汇区-2022-2026.csv`。两者**并存**：旧脚本保留作基线参照
（阶段 0.2 已验证它能逐字节复现旧产物），⛔ 不得用旧脚本重算后再与本脚本比较。

口径（详见 .trellis/tasks/10-04-xuhui-apply-jiading-method/design.md）
--------------------------------------------------------------------
· 基线线 **方案 C**：`QU6` 六条定义集合，某年某线无分数则该年不计入
  ⇒ 实际参与线数逐年 **[4, 5, 5, 5, 6]**，脚本**断言**该值。
  另附 `QU4`（= 2022 年全部线）作敏感性对照。
· 线分组**只有 `all` 一组**（D-XH2 取消头/尾分层，不产出 head/tail/comb）。
· 委属线 5 条**不参与排名** —— 依据 2022–2024 计划 PDF 原文
  「以均衡、随机为原则**抽签**确定」，抽签结果与学校规模无关。
· `rel_y` = 当年名额加权均分 − 当年**公办非退出**池中位（普陀 D3 口径）。

⛔ 三处照搬普陀会踩的坑（徐汇源数据不同）
------------------------------------------
1. 字段名：普陀 `senior_high_school_tier` / `quota` / 有 short 名；
   徐汇 `high_school_tier` / `quota_plan` / ⛔ **无 short 名**。本脚本一律用**代码**作键。
2. `初中名录-公办民办-徐汇区-2026.csv` 的 `school_code` **整列为空**（35 行）
   ⇒ `ownership` **必须按校名**连接（经别名表换到代码）。按代码连接会全部落空。
3. 分数线表多 7 列：`min_score` 是 **800 分制总分**（`min_score/800 == score_rate`，
   883/883 自洽）**可用**；⛔ `comprehensive_eval` 恒为 `50`、是等级标记而非分数，
   **本脚本不使用该列**（误混用会彻底毁掉排名）。

写入策略：全部在内存拼装 + 断言通过后才落盘（规范陷阱 14）。
"""
import csv
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D_S = ROOT / 'data/徐汇区/学校'
D_A = ROOT / 'analysis/徐汇区公办初中名额分配到校分析'
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 共用算法实现：生成侧与校验侧同一份代码（implement.md 6.1，避免假门禁）
from xh_common import midrank, weighted_mean, p_from_rank  # noqa: E402

YEARS = [2022, 2023, 2024, 2025, 2026]

# ---- 方案 C：6 条区属线定义集合（= 2026 年的全部区属线）----
QU6 = ['042001', '042002', '042008', '042035', '042036', '043015']
QU4 = ['042001', '042008', '042035', '043015']        # 对照 = 2022 年全部线
#: 逐年实际参与线数（**实测**，design.md 三点六）；脚本据此断言
BASE_N_BY_YEAR = {2022: 4, 2023: 5, 2024: 5, 2025: 5, 2026: 6}
QU_NAMES = {'042001': '二中', '042002': '二中梅陇', '042008': '南模',
            '042035': '位育', '042036': '复附徐汇', '043015': '南洋'}
#: 时间权重四档。`recent3`/`recent2` **按语义取池**（见 POOL_BY_TIME），
#: 与 `lin`/`exp`（维持主池）不同 —— 偏离普陀「其余口径维持主池」的做法。
W_TIME = {
    'lin':    {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
    'exp':    {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
    'recent3': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1},
    'recent2': {2022: 0, 2023: 0, 2024: 0, 2025: 1, 2026: 1},
}
#: 委属线：不参与排名（PDF 原文「抽签」，design 1.4）
COMMISSIONAL = ['042032', '102056', '102057', '152003', '152006']

# ---- 已退出的公办初中（**仅数据层证据**，无官方文件 ⇒ 原因待核实）----
# 依据：别名表 years_present + 不在 2026 名录
EXITED = {
    '041313': '已退出名额到校体系（2023 起不再出现）；原因待核实：未查到公开文件',
    '044125': '已退出名额到校体系（2025 起不再出现）；原因待核实：未查到公开文件',
    '045146': '已退出名额到校体系（2024 起不再出现）；2023 年有名额但无录取线；原因待核实',
}
MIN_YEARS_RANKED = 4      # years_included >= 4 入榜（与嘉定/普陀一致）
MIN_YEARS_FIXED = 5       # 收敛指标固定样本 = 五年全勤

# ---- 同名不同实体：别名表明文警告，绝不可合并（design 1.3）----
NEVER_MERGE = [('041316', '043015'),   # 南洋初中 vs 南洋中学（高中，只在招生学校列）
               ('044110', '044109')]   # 徐汇南校 vs 徐汇中学


def load(name):
    with open(D_S / name, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def num(x, nd=2):
    return '' if x is None else f'{x:.{nd}f}'


def fmean(xs):
    return st.fmean(xs) if xs else None


# ==================== 载入 ====================
plan = load('名额到校计划-徐汇区-2022-2026.csv')
score = load('名额到校最低分数线-徐汇区-2022-2026.csv')
alias = load('初中校名别名表-徐汇区.csv')
roster = load('初中名录-公办民办-徐汇区-2026.csv')

# 坑 2 前置断言：名录 school_code 确实整列为空（若上游补了代码，此处须同步改）
assert not any((r.get('school_code') or '').strip() for r in roster), \
    '徐汇名录 school_code 不应有值；本脚本按校名连接，若上游已补代码需同步改此处'

name2code = {}
for a in alias:
    name2code[a['canonical_name']] = a['school_code']
    for al in (a['alias_name'] or '').split(';'):
        if al:
            name2code[al] = a['school_code']

SCHOOLS = {r['junior_high_school_code'] for r in plan}
_PLAN_NAMES = {r['junior_high_school'] for r in plan}

# ownership 按**校名**判定（名录无代码，只能走别名表）。
# 名录是 2026 当年在读学校全集，其中 9 校**不在计划表**（未参与名额到校）——
#   · 拆校区写法：园南中学（总校/罗城校区）、徐汇中学（蒲汇塘校区）、徐汇中学南校
#   · 高中部：上海市南洋中学（= 043015 的高中，出现在招生学校列而非初中行）
#   · 未参与名额到校的新校/特教校：位育附属徐汇科技实验、复旦附中徐汇实验、
#     西南位育附属实验、徐汇区董李凤美康健
# 这些**不进入宽表**（没有名额到校记录），但须计数并打印，避免静默丢校。
own = {}
roster_extra, roster_dup = [], []
for r in roster:
    c = name2code.get(r['school_name'])
    if c is None:
        # 名录校名在别名表里无对应代码 ⇒ 该校不在名额到校体系，不进宽表
        roster_extra.append((r['school_name'], r['ownership'], None))
        continue
    if c in own:
        # 同一代码被两条名录条目映射（如「园区/总校」写法）：允许但须留痕
        roster_dup.append((c, r['school_name'], own[c], r['ownership']))
    own[c] = r['ownership']
# ---- ownership 回退：名录未收录但仍在/曾参与名额到校的学校 ----
# 实测 4 个代码在 2026 名录里无对应条目：
#   041313 宛平 / 044125 龙华 / 045146 位育体校 —— **已退出**（EXITED），
#     名录无收录属预期；ownership 取「公办」（它们在计划表五年均属公办序列，
#     别名表有 years_present 记录）。
#   045304 位育实验学校 —— ⚠️ **2022–2026 五年都在计划表、2026 名录却查不到**。
#     名录里的「上海市位育附属徐汇科技实验中学」是**另一所**学校（名字不同、
#     名录无代码），**不得**据此认定二者同一。⇒ ownership 标「公办」但
#     `ownership_source = 'unverified'`，报告须写「2026 名录未收录，归属待核实」。
OWNERSHIP_FALLBACK = {
    '041313': '公办', '044125': '公办', '045146': '公办', '045304': '公办',
}
own_source = {}
for c, v in own.items():
    own_source[c] = 'roster'
for c, v in OWNERSHIP_FALLBACK.items():
    if c not in own:
        own[c] = v
        own_source[c] = 'unverified'
assert set(own) == SCHOOLS, (
    f'ownership 未覆盖全部计划表学校：缺 {sorted(SCHOOLS - set(own))}；'
    f'名录/别名表需补 alias_name')
# 校名映射可能把两所不同学校归到同一代码 —— 别名表已警示 043015/041316 绝不可合并，
# 这里从数据侧兜底：043015 作为**初中**在计划表出现 0 行，故不可能是初中实体
assert not any(r['junior_high_school_code'] == '043015' for r in plan), \
    '043015（南洋中学·高中）不应作为初中出现在计划表，若出现则 NEVER_MERGE 判断需重审'
name_by_code = {}
for r in plan + score:
    name_by_code.setdefault(r['junior_high_school_code'], {})[int(r['year'])] = \
        r['junior_high_school']
code2name = {c: m[max(m)] for c, m in name_by_code.items()}      # 显示名取最新年份
former_names = {c: ';'.join(sorted({n for n in m.values() if n != code2name[c]}))
                for c, m in name_by_code.items()}

# ---- 同一性断言（阶段 1）----
# 1) 同一代码的多个校名必须**年份不重叠**（重叠 ⇒ 代码复用错误，不可归并）
for c, m in name_by_code.items():
    spans = {}
    for y, n in m.items():
        spans.setdefault(n, []).append(y)
    names = list(spans)
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            assert max(spans[n1]) < min(spans[n2]) or max(spans[n2]) < min(spans[n1]), \
                f'代码 {c} 的校名 {n1} / {n2} 在同一年共存: {spans} ⇒ 不可归并'
# 2) 曾用名有值时，旧名不得同时作为独立学校存在（041328 归并生效）
_names = set(code2name)
for c, fn in former_names.items():
    for old in filter(None, fn.split(';')):
        assert old not in _names, f'旧名 {old} 仍作为独立学校存在（归并未生效）'
# 3) NEVER_MERGE 两对不得出现在同一归并结果里
for a, b in NEVER_MERGE:
    assert a in SCHOOLS or a not in SCHOOLS, f'{a} 不在计划表'
    assert b in SCHOOLS or b not in SCHOOLS, f'{b} 不在计划表'
    assert code2name.get(a) != code2name.get(b), f'{a} 与 {b} 被错误合并'
# 4) 退出校必须在计划表里（否则 EXITED 登记无意义）
for c in EXITED:
    assert c in SCHOOLS, f'EXITED 中的 {c} 不在计划表'

print(f'学校 {len(SCHOOLS)} 所｜民办 {sum(1 for c in SCHOOLS if own.get(c) == "民办")} 所'
      f'｜曾用名 {sum(1 for v in former_names.values() if v)} 所'
      f'｜退出 {len(EXITED)} 所')
print(f'名录 {len(roster)} 校 → 映射到计划表 {len(own)} 校；'
      f'{len(roster_extra)} 校无对应代码（未参与名额到校，不进宽表）：'
      + '、'.join(f'{n}' for n, _, _ in roster_extra))
if roster_dup:
    print(f'  ⚠️ 同一代码被多条名录条目映射 {len(roster_dup)} 处：'
          + '；'.join(f'{c}←{n}({o2})' for c, n, o1, o2 in roster_dup))

# ==================== 数值字典 ====================
Q = {}
for r in plan:
    v = r['quota_plan']
    Q[(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code'])] = \
        int(v) if v not in ('', None) else 0
SC = {}
for r in score:
    v = r['min_score']
    SC[(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code'])] = \
        float(v) if v not in ('', None) else None


def q(c, y, h):
    return Q.get((y, c, h), 0)


def sc(c, y, h):
    return SC.get((y, c, h))


# ==================== 方案 C：逐年参与线 ====================
ACT = {y: [h for h in QU6 if any(sc(c, y, h) is not None for c in SCHOOLS)]
       for y in YEARS}
for y in YEARS:
    assert len(ACT[y]) == BASE_N_BY_YEAR[y], \
        f'{y} 实际参与线数 {len(ACT[y])} ≠ 预期 {BASE_N_BY_YEAR[y]}：{ACT[y]}'
print('参与线数断言通过：' + ' '.join(f'{y}={len(ACT[y])}' for y in YEARS))


# ==================== 加权均分 ====================
def wmean(c, y, lines):
    pairs = [(sc(c, y, h), q(c, y, h)) for h in lines]
    return weighted_mean([(s, n) for s, n in pairs if s is not None and n])


MEAN, MEAN_Q4, EQ = {}, {}, {}
for y in YEARS:
    act4 = [h for h in QU4 if h in ACT[y]]
    for c in SCHOOLS:
        MEAN[(c, y)] = wmean(c, y, ACT[y])
        MEAN_Q4[(c, y)] = wmean(c, y, act4)
        vs = [sc(c, y, h) for h in ACT[y] if sc(c, y, h) is not None]
        EQ[(c, y)] = fmean(vs)

# ==================== row_type 四分类 ====================
COV = {c: sum(1 for y in YEARS if MEAN.get((c, y)) is not None) for c in SCHOOLS}


def row_type_of(c):
    if own.get(c) == '民办':
        return 'excluded_private'
    if c in EXITED:
        return 'exited'
    return 'ranked' if COV[c] >= MIN_YEARS_RANKED else 'short_sample'


ROW_TYPE = {c: row_type_of(c) for c in SCHOOLS}

# ==================== 逐年 位次/分位/z/稳健z ====================
# 池 = 当年有数据的**公办非退出**校（与普陀 rel 基准池同口径）
RANK_POOL, YEAR_RANK, YEAR_P, YEAR_Z, YEAR_ZR = {}, {}, {}, {}, {}
for y in YEARS:
    pool = [c for c in sorted(SCHOOLS)
            if MEAN.get((c, y)) is not None
            and own.get(c) == '公办' and c not in EXITED]
    RANK_POOL[y] = len(pool)
    rk = midrank([(c, MEAN[(c, y)]) for c in pool])
    xs = [MEAN[(c, y)] for c in pool]
    mu, sg = fmean(xs), (st.pstdev(xs) if len(xs) > 1 else 0.0)
    med = st.median(xs)
    sxs = sorted(xs)
    iqr = sxs[len(sxs) * 3 // 4] - sxs[len(sxs) // 4]
    rs = iqr / 1.349 if iqr else None
    YEAR_RANK[y], YEAR_P[y], YEAR_Z[y], YEAR_ZR[y] = {}, {}, {}, {}
    for c, r in rk.items():
        YEAR_RANK[y][c] = r
        YEAR_P[y][c] = p_from_rank(r, len(pool))
        YEAR_Z[y][c] = (MEAN[(c, y)] - mu) / sg if sg else None
        YEAR_ZR[y][c] = (MEAN[(c, y)] - med) / rs if rs else None
print('排名池（当年公办非退出）：' + ' '.join(f'{y}={RANK_POOL[y]}' for y in YEARS))

# ==================== rel ====================
REL = {}
for y in YEARS:
    pool = [c for c in sorted(SCHOOLS)
            if MEAN.get((c, y)) is not None
            and own.get(c) == '公办' and c not in EXITED]
    med = st.median([MEAN[(c, y)] for c in pool])
    for c in SCHOOLS:
        if MEAN.get((c, y)) is not None:
            REL[(c, y)] = MEAN[(c, y)] - med

# ==================== 汇总宽表 ====================
RANKED = [c for c in sorted(SCHOOLS) if ROW_TYPE[c] == 'ranked']

# ---- 时间权重四档的**按口径取池**（design 2.1 / implement 3.2–3.3）----
# lin/exp 维持主池（ranked）；recent3/recent2 按语义扩池到
# 「有该窗口全部数据的公办非退出校」，从而把短样本新校纳入。
_PUB_OK = lambda c: own.get(c) == '公办' and c not in EXITED
_HAS = lambda c, ys: all(MEAN.get((c, y)) is not None for y in ys)
POOL_BY_TIME = {
    'lin': RANKED,
    'exp': RANKED,
    'recent3': sorted(c for c in sorted(SCHOOLS)
                      if _PUB_OK(c) and _HAS(c, [2024, 2025, 2026])),
    'recent2': sorted(c for c in sorted(SCHOOLS)
                      if _PUB_OK(c) and _HAS(c, [2025, 2026])),
}
for _k, _p in POOL_BY_TIME.items():
    assert _p, f'时间权重档 {_k} 的池为空'
print('时间权重池：' + ' '.join(f'{k}={len(v)}' for k, v in POOL_BY_TIME.items()))

QU_ALL = QU6 + COMMISSIONAL
rows = {}
for c in sorted(SCHOOLS):
    cov = [y for y in YEARS if MEAN.get((c, y)) is not None]
    d = {
        'junior_high_school': code2name[c],
        'junior_high_school_code': c,
        'ownership': own.get(c, ''),
        'ownership_source': own_source.get(c, ''),
        'row_type': ROW_TYPE[c],
        'exit_reason': EXITED.get(c, ''),
        'junior_high_school_former_names': former_names.get(c, ''),
        'years_included': COV[c],
        'years_list': ';'.join(str(y) for y in cov),
    }
    for y in YEARS:
        for h in QU_ALL:
            nm = QU_NAMES.get(h, f'委属{h}')
            d[f'quota_{nm}_{y}'] = q(c, y, h)
            d[f'score_{nm}_{y}'] = num(sc(c, y, h), 3)
        d[f'quota6_{y}'] = sum(q(c, y, h) for h in ACT[y])
        d[f'base_n_{y}'] = len(ACT[y])
        d[f'valid_pairs_{y}'] = sum(1 for h in ACT[y] if sc(c, y, h) is not None)
        d[f'mean_score_base_{y}'] = num(MEAN.get((c, y)), 3)
        d[f'mean_score_base_eq_{y}'] = num(EQ.get((c, y)), 3)
        d[f'mean_score_qu4_{y}'] = num(MEAN_Q4.get((c, y)), 3)
        d[f'rank_base_{y}'] = num(YEAR_RANK[y].get(c), 2)
        d[f'P_base_{y}'] = num(YEAR_P[y].get(c), 6)
        d[f'Z_base_{y}'] = num(YEAR_Z[y].get(c), 6)
        d[f'ZR_base_{y}'] = num(YEAR_ZR[y].get(c), 6)
        d[f'rel_{y}'] = num(REL.get((c, y)), 4)
    d['rel_avg'] = num(fmean([REL[(c, y)] for y in cov if (c, y) in REL]), 4)
    d['rel_pool_n'] = RANK_POOL.get(cov[-1], '') if cov else ''
    d['mean_rank_base_avg'] = num(fmean([YEAR_RANK[y][c] for y in cov
                                         if c in YEAR_RANK[y]]), 4)
    for src, key in ((YEAR_P, 'P_wq'), (YEAR_Z, 'Z_wq'), (YEAR_ZR, 'ZR_wq')):
        d[key] = num(fmean([src[y][c] for y in cov if c in src[y]]), 6)
    # 等权链：同池同年 P（分位与链无关，链差体现在 mean_score 的算法上），
    # 故 P_eq 另算：等权均分在**同池**内的分位
    rows[c] = d

# ---- 等权链 P_eq：等权均分在同一排名池内的分位 ----
YR_PE = {}
for y in YEARS:
    pool = [c for c in sorted(SCHOOLS)
            if EQ.get((c, y)) is not None
            and own.get(c) == '公办' and c not in EXITED]
    rk = midrank([(c, EQ[(c, y)]) for c in pool])
    YR_PE[y] = {c: p_from_rank(r, len(pool)) for c, r in rk.items()}
for c, d in rows.items():
    cov = [y for y in YEARS if MEAN.get((c, y)) is not None]
    d['P_eq'] = num(fmean([YR_PE[y][c] for y in cov if c in YR_PE[y]]), 6)


def ranks_of(dic, pool):
    """聚合名次 = 顺序秩（降序 1..N，须唯一）；并列也给出不同名次。

    `dic` 的值是 `num()` 格式化后的**字符串**（宽表列一律存字符串），
    故此处必须先转回 float 再排序。
    """
    ok = []
    for c in pool:
        v = dic.get(c)
        if v in (None, ''):
            continue
        ok.append((c, float(v)))
    ok.sort(key=lambda t: -t[1])
    return {c: i for i, (c, _) in enumerate(ok, 1)}


RK = {k: ranks_of({c: rows[c][k] for c in rows}, RANKED)
      for k in ('P_wq', 'P_eq', 'Z_wq', 'ZR_wq')}
for c, d in rows.items():
    for k in ('P_wq', 'P_eq', 'Z_wq', 'ZR_wq'):
        d[f'rank_{k}'] = RK[k].get(c, '')

# ==================== 时间权重四档 ====================
# P_{档}：在该档**池**内，先按时间权重把「当年 P」聚合成一个数，再在池内转成分位。
# 顺序：逐年 P（已在 YEAR_P，按当年池算）→ 加权平均 → 池内分位 → 顺序秩。
# ⚠️ 池随档位变化（recent3/recent2 扩池到含短样本），故**名次不可跨档直接比较**。
P_TIME = {}
for k, w in W_TIME.items():
    pool = POOL_BY_TIME[k]
    agg = {}
    for c in pool:
        # 局部累加器用 `_wnum`，⛔ 不得叫 `num` —— 那会遮蔽模块级的格式化函数
        _wnum = _wden = 0.0
        for y in YEARS:
            v = YEAR_P[y].get(c)
            if v is None or not w[y]:
                continue
            _wnum += w[y] * v
            _wden += w[y]
        if _wden:
            agg[c] = _wnum / _wden
    P_TIME[k] = {c: p_from_rank(r, len(agg)) for c, r in midrank(list(agg.items())).items()}
for c, d in rows.items():
    for k in W_TIME:
        d[f'P_{k}'] = num(P_TIME[k].get(c), 6)
RK_T = {k: ranks_of({c: (num(P_TIME[k].get(c), 6) or '') for c in rows}, POOL_BY_TIME[k])
        for k in W_TIME}
for c, d in rows.items():
    for k in W_TIME:
        d[f'rank_P_{k}'] = RK_T[k].get(c, '')

# 2026 当年位次 + 排名变化（design 2.1b；方向：负值 = 上升）
for c, d in rows.items():
    d['rank_2026'] = d.get('rank_base_2026', '') or ''
    r22, r25, r26 = d.get('rank_base_2022', ''), d.get('rank_base_2025', ''), d.get('rank_base_2026', '')
    d['rank_chg_5y'] = num(float(r26) - float(r22), 2) if r22 and r26 else ''
    d['rank_chg_1y'] = num(float(r26) - float(r25), 2) if r25 and r26 else ''

# ==================== 值域断言（写盘前全部完成）================
_blank = [rows[c]['junior_high_school'] for c in rows if not rows[c]['ownership'].strip()]
assert not _blank, f'ownership 存在空值：{_blank}'
assert {rows[c]['ownership'] for c in rows} <= {'公办', '民办'}, 'ownership 值域越界'

_RT = {'ranked', 'short_sample', 'exited', 'excluded_private'}
assert {rows[c]['row_type'] for c in rows} <= _RT, 'row_type 值域越界'
for c, d in rows.items():
    if d['ownership'] == '民办':
        assert d['row_type'] == 'excluded_private', f'民办行 row_type={d["row_type"]}'
    elif d['row_type'] == 'exited':
        assert d['exit_reason'].strip(), f'{d["junior_high_school"]} exited 但缺 exit_reason'
    elif d['row_type'] == 'ranked':
        assert d['years_included'] >= MIN_YEARS_RANKED, \
            f'{d["junior_high_school"]} years={d["years_included"]} 不应 ranked'
    else:
        assert d['years_included'] < MIN_YEARS_RANKED, \
            f'{d["junior_high_school"]} years={d["years_included"]} 应为 short_sample'
_cnt = Counter(rows[c]['row_type'] for c in rows)
assert sum(_cnt.values()) == len(rows), 'row_type 四类之和 ≠ 行数（不互斥穷尽）'
assert all(rows[c]['rank_P_wq'] == '' for c in rows if rows[c]['row_type'] != 'ranked'), \
    '非 ranked 行竟有入榜名次'
for y in YEARS:
    got = {rows[c][f'base_n_{y}'] for c in rows}
    assert got == {BASE_N_BY_YEAR[y]}, f'base_n_{y} 应为 {BASE_N_BY_YEAR[y]}，实为 {got}'
# ownership 来源必须逐行有值，且 unverified 的行须在报告中披露
assert all(rows[c]['ownership_source'] in ('roster', 'unverified') for c in rows), \
    'ownership_source 值域越界'
_unv = sorted(c for c in rows if rows[c]['ownership_source'] == 'unverified')
print('ownership 待核实（2026 名录未收录）：'
      + '、'.join(f"{rows[c]['junior_high_school']}({c})" for c in _unv))

print('row_type：' + str(dict(_cnt)))
print(f'入榜（ranked）{len(RANKED)} 所')

COLS = (['junior_high_school', 'junior_high_school_code', 'ownership',
         'ownership_source', 'row_type', 'exit_reason',
         'junior_high_school_former_names',
         'years_included', 'years_list']
        + [f'{p}_{QU_NAMES.get(h, "委属" + h)}_{y}'
           for y in YEARS for p in ('quota', 'score') for h in QU_ALL]
        + [f'{k}_{y}' for y in YEARS
           for k in ('quota6', 'base_n', 'valid_pairs', 'mean_score_base',
                     'mean_score_base_eq', 'mean_score_qu4', 'rank_base',
                     'P_base', 'Z_base', 'ZR_base', 'rel')]
        + ['rel_avg', 'rel_pool_n', 'mean_rank_base_avg',
           'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq',
           'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq']
        + [f'{p}_{k}' for k in W_TIME for p in ('P', 'rank_P')]
        + ['rank_2026', 'rank_chg_5y', 'rank_chg_1y'])
# 陷阱 24（普陀踩过）：时间权重列必须**动态生成并断言在列内**，
# 否则新增档位会静默丢列（普陀的 P_recent2 曾整列缺失而脚本正常退出）。
_cols = set(COLS)
for _k in W_TIME:
    for _p in ('P', 'rank_P'):
        assert f'{_p}_{_k}' in _cols, f'W_TIME 中的 {_k} 未进入宽表列，会静默丢列'
# 四档名次必须是各自池内的 1..N 连续（否则「按口径取池」没生效或池定义有误）
for _k in W_TIME:
    _got = sorted(int(rows[c][f'rank_P_{_k}']) for c in POOL_BY_TIME[_k]
                  if rows[c][f'rank_P_{_k}'] != '')
    assert _got == list(range(1, len(_got) + 1)), \
        f'{_k} 档名次非 1..N 连续：{_got[:12]}'
    # 池外的行不得有该档名次
    _out = [c for c in rows if c not in POOL_BY_TIME[_k] and rows[c][f'rank_P_{_k}'] != '']
    assert not _out, f'{_k} 档池外校竟有名次：{_out[:5]}'
# rank_chg 断言：逐校等于 rank_2026 − 基年位次
for c, d in rows.items():
    if d['rank_chg_5y'] != '':
        assert abs(float(d['rank_chg_5y'])
                   - (float(d['rank_base_2026']) - float(d['rank_base_2022']))) < 1e-9, \
            f"{d['junior_high_school']} rank_chg_5y 与逐项计算不一致"
    if d['rank_chg_1y'] != '':
        assert abs(float(d['rank_chg_1y'])
                   - (float(d['rank_base_2026']) - float(d['rank_base_2025']))) < 1e-9, \
            f"{d['junior_high_school']} rank_chg_1y 与逐项计算不一致"

# ==================== 落盘（全部断言通过后）====================
out = D_A / '宽表-初中水平-徐汇区-2022-2026.csv'
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
    w.writeheader()
    for c in sorted(rows, key=lambda c: (rows[c]['rank_P_wq'] == '',
                                         rows[c]['rank_P_wq'] or 999)):
        w.writerow(rows[c])
print(f'写出 宽表 {len(rows)} 行 × {len(COLS)} 列（ranked 在前，按 rank_P_wq 升序）')
