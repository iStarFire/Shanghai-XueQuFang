"""阶段 5：用宽表**重新生成**报告 2.1 / 2.2 的排名表，杜绝手抄误差。

与 build_ch8_jd.py 同思路：表格由 CSV 动态生成，叙述文字另行改写。
本脚本只替换表格区块（按标记定位），不触碰叙述文字。

写入策略：内存拼装 + 断言通过后才落盘（规范陷阱 14）。
"""
import csv
import re
import statistics as st
from collections import Counter
from pathlib import Path

D = Path('.')
REPORT = D / '分析报告.md'
YEARS = ['2022', '2023', '2024', '2025', '2026']
MEAN_COL = 'mean_score_base4_wq_{y}'


def load(p):
    with Path(p).open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


W = {r['junior_high_school']: r for r in load(D / '宽表-初中水平-普陀区-2022-2026.csv')}
RANKED = [r for r in W.values() if r['row_type'] == 'ranked']
RANKED.sort(key=lambda r: int(r['rank_P_wq_comb']))


def q4avg(r):
    vs = [r[f'quota4_{y}'] for y in YEARS if r.get(f'quota4_{y}') not in ('', None)]
    return st.fmean([float(v) for v in vs]) if vs else None


# ================= 表 2-1 =================
t21 = ['| 综合名次 | 初中 | P综合（加权） | 全身 | 头部 | 尾部 | 等权综合名次 | 位次差 | 年均计划 | 覆盖 |',
       '|---|---|---|---|---|---|---|---|---|---|']
for i, r in enumerate(RANKED, 1):
    q = q4avg(r)
    shift = int(r['rank_P_eq_comb']) - int(r['rank_P_wq_comb'])
    cov = f"{r['years_included']} 年"
    t21.append(f"| {i} | {r['junior_high_school']} | {float(r['P_wq_comb']):.3f} "
               f"| {r['rank_P_wq_all']} | {r['rank_P_wq_head']} | {r['rank_P_wq_tail']} "
               f"| {r['rank_P_eq_comb']} | {shift:+d} | {q:.1f} | {cov} |")
T21 = '\n'.join(t21)

# ================= 表 2-2 =================
COLS2 = [('P加权', 'rank_P_wq_comb'), ('P等权', 'rank_P_eq_comb'),
         ('Z加权', 'rank_Z_wq_comb'), ('ZR加权', 'rank_ZR_wq_comb')]
T_TIME = [('P线性', 'rank_P_lin'), ('P指数', 'rank_P_exp'),
          ('P近3年', 'rank_P_recent3'), ('P近2年', 'rank_P_recent2')]
t22 = ['| 初中 | ' + ' | '.join(c[0] for c in COLS2) + ' | 均名(加权) | '
       + ' | '.join(c[0] for c in T_TIME) + ' |',
       '|---|' + '---|' * (len(COLS2) + 1 + len(T_TIME))]
for r in RANKED:
    cells = [r[k] for _, k in COLS2]
    t22.append(f"| {r['junior_high_school']} | " + ' | '.join(cells)
               + f" | {float(r['mean_rank_base4_wq_avg']):.2f} | "
               + ' | '.join(r[k] for _, k in T_TIME) + ' |')
T22 = '\n'.join(t22)


# ================= 表 3-1~3-4：四条区属线的单线视角 =================
# 单线位次的池与 P/Z/ZR 一致 = 当年「全部有数据初中」（含民办），
# 因该线当年有分数的校数（31–41）与 P 口径全池相同。
LINES = ['华二普陀', '二中', '晋元', '宜川']
# 报告中的显示名与数据列名不完全一致（「二中」列在报告里叫「曹杨二中线」）
LINE_LABEL = {'华二普陀': '华二普陀', '二中': '曹杨二中', '晋元': '晋元', '宜川': '宜川'}
TOP_N = 8


def rank_avg_tie(pairs):
    """当年位次 = 平均秩（并列同名次），与 rank_base4_{y} 口径一致。

    ⚠️ **必须用「比它强的个数」而非「比它弱的个数」** —— 后者会把最高分算成第 n 名。
    本函数内含方向自检，防止此类符号错误（曾因验证脚本写反而误判「旧报告符号错误」）。
    """
    xs = sorted(v for _, v in pairs)
    out = {}
    for c, v in pairs:
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        out[c] = b + (e + 1) / 2
    # ---- 方向自检：分数最高者位次必须为 1（并列时为并列区间的上界）----
    top = max(xs)
    top_ranks = [out[c] for c, v in pairs if v == top]
    assert min(top_ranks) == 1, (
        f'位次方向错误：最高分 {top} 的位次为 {top_ranks}，应为 1。'
        f'请检查用的是「比它强」还是「比它弱」。')
    assert max(out.values()) <= len(pairs), '位次超出并列范围'
    return out


R32 = {}
for l in LINES:
    per = {}
    for y in YEARS:
        pairs = [(r['junior_high_school'], float(r[f'score_{l}_{y}']))
                 for r in W.values() if r.get(f'score_{l}_{y}') not in ('', None)]
        per[y] = rank_avg_tie(pairs)
    rows = []
    for r in RANKED:
        n = r['junior_high_school']
        rks = [per[y][n] for y in YEARS if n in per[y]]
        scs = [float(W[n][f'score_{l}_{y}']) for y in YEARS
               if W[n].get(f'score_{l}_{y}') not in ('', None)]
        if rks:
            rows.append((st.fmean(rks), st.fmean(scs) if scs else None, n, len(rks)))
    rows.sort(key=lambda t: t[0])   # 名次 1 = 均名最小，须**升序**
    R32[l] = rows[:TOP_N]
    assert len(rows) >= TOP_N, f'{l} 线可用校不足 {TOP_N}：{len(rows)}'
R32_ALL = {l: len([1 for r in RANKED if any(
    W[r['junior_high_school']].get(f'score_{l}_{y}') not in ('', None) for y in YEARS)])
    for l in LINES}

# 每条线**独立**成表。⚠️ 不可把四条线拼成一个整块替换 —— 3.2 节内还含
# 3.2.1（曹二线完整排名）与 3.2.2（单线稳定性分析）两块内容，
# 整块替换会把它们一并吞掉（曾发生，丢失 53 行）。
T32 = {}
for l in LINES:
    rows = [f'**{LINE_LABEL[l]}线**', '',
            '| 名次 | 初中 | 该线均名 | 该线均分 |', '|---|---|---|---|']
    for i, (mr, ms, n, k) in enumerate(R32[l], 1):
        rows.append(f'| {i} | {n} | {mr:.2f} | {ms:.1f} |')
    T32[l] = '\n'.join(rows)
    assert 'None' not in T32[l], f'{l} 线表含 None'


# ================= 第 4 章：收敛指标 / 收敛检验 / 趋势分类 =================
R2 = load(D / '收敛指标-普陀区-2022-2026.csv')
R3 = load(D / '收敛趋势检验-普陀区-2022-2026.csv')
R4 = load(D / '趋势分类-普陀区-2022-2026.csv')


def pctl(xs, p):
    import math
    ss = sorted(xs)
    n = len(ss)
    k = (n - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return ss[lo] + (ss[hi] - ss[lo]) * (k - lo)


FIXED5 = [r for r in RANKED if int(r['years_included']) == 5]
T41 = ['| 年 | IQR | σ | 中位 | 中位 ±5 分内占比 | ±10 分内占比 |',
       '|---|---|---|---|---|---|']
for r in R2:
    y = r['year']
    xs = [float(x[MEAN_COL.format(y=y)]) for x in FIXED5]
    med = st.median(xs)
    iqr = pctl(xs, 75) - pctl(xs, 25)
    w5 = sum(1 for v in xs if abs(v - med) <= 5) / len(xs)
    w10 = sum(1 for v in xs if abs(v - med) <= 10) / len(xs)
    T41.append(f"| {y} | {iqr:.1f} | {float(r['sigma']):.2f} | {float(r['pool_median']):.1f} "
               f"| {w5*100:.0f}% | {w10*100:.0f}% |")
T41 = '\n'.join(T41)

METS = ['sigma', 'cv', 'iqr_norm', 'gini', 'r90_10_norm', 'range_norm', 'mad_norm']
NAMES = {'sigma': 'σ（分）', 'cv': 'CV', 'iqr_norm': 'IQR/中位', 'gini': '基尼',
         'r90_10_norm': '(P90−P10)/中位', 'range_norm': '极差/中位', 'mad_norm': 'MAD/中位'}
T42 = ['| 指标 | 2022 | 2026 | 斜率 / 年 | p | R² | 95% CI | 判定 |',
       '|---|---|---|---|---|---|---|---|']
for r in R3:
    m = r['metric']
    lo, hi = float(r['ci_lo']), float(r['ci_hi'])
    cross = lo <= 0 <= hi
    T42.append(f"| {NAMES[m]} | {float(r['v2022']):.5f} | {float(r['v2026']):.5f} "
               f"| {float(r['slope_b']):+.5f} | {float(r['p']):.3f} | {float(r['r2']):.3f} "
               f"| [{lo:+.5f}, {hi:+.5f}] | {'**CI 跨 0，无法判定**' if cross else 'CI 不跨 0，显著'} |")
T42 = '\n'.join(T42)

# 趋势分类：按类别分组列出
CLS_ORDER = ['明显上升', '明显下降', '基本持平']
T44 = ['| 趋势判定 | 校数 | 学校（按 Sen 极值排序） |', '|---|---|---|']
for cls in CLS_ORDER:
    g = [r for r in R4 if r['trend_class'] == cls]
    if not g:
        continue
    g = sorted(g, key=lambda r: -float(r['sen']))
    names = '、'.join(r['junior_high_school'].replace('上海市', '').replace('上海', '')
                      for r in g)
    T44.append(f"| {cls} | {len(g)} | {names} |")
T44 = '\n'.join(T44)

# ---- 第 4 章断言 ----
assert len(FIXED5) == 32, f'固定样本应为 32，实际 {len(FIXED5)}'
assert {r['n_fixed'] for r in R2} == {'32'}, '收敛表固定样本数逐年不等'
assert len(R3) == 7 and {r['metric'] for r in R3} == set(METS), '收敛检验指标集不符'
assert len(R4) == 32 and all(int(r['n_years']) >= 4 for r in R4), '趋势分类覆盖不符'
_cls = Counter(r['trend_class'] for r in R4)
assert sum(_cls.values()) == 32
for tbl, nm in ((T41, '4-1'), (T42, '4-2'), (T44, '4-4')):
    assert 'None' not in tbl and 'nan' not in tbl, f'表 {nm} 含 None/nan'

# ================= 断言 =================
assert len(RANKED) == 32, f'入榜应为 32 所，实际 {len(RANKED)}'
for i, r in enumerate(RANKED, 1):
    assert int(r['rank_P_wq_comb']) == i, \
        f'第 {i} 行 rank_P_wq_comb={r["rank_P_wq_comb"]}，与排序不符'
    assert r['row_type'] == 'ranked'
    assert r['years_included'] == '5', f'{r["junior_high_school"]} 年数 {r["years_included"]}'
    assert q4avg(r) is not None, f'{r["junior_high_school"]} 缺区属名额'
# P近2年 / P近3年 的池不同，须在表内可区分
pool_r2 = sorted(int(r['rank_P_recent2']) for r in W.values() if r.get('rank_P_recent2'))
pool_r3 = sorted(int(r['rank_P_recent3']) for r in W.values() if r.get('rank_P_recent3'))
assert pool_r2 == list(range(1, 37)), f'近2年名次不连续：{pool_r2[:3]}…'
assert pool_r3 == list(range(1, 35)), f'近3年名次不连续：{pool_r3[:3]}…'
# 表 3-x：四条线各 TOP_N 所，且均名随名次非递减（降序）
for l in LINES:
    mrs = [t[0] for t in R32[l]]
    assert len(mrs) == TOP_N, f'{l} 线表行数 {len(mrs)} ≠ {TOP_N}'
    assert mrs == sorted(mrs), f'{l} 线均名未按升序排列（名次 1 应为均名最小者）'
    for mr, ms, n, k in R32[l]:
        assert n in {r['junior_high_school'] for r in RANKED}, f'{l} 线混入非入榜校：{n}'
        assert 1 <= k <= 5, f'{n} 在 {l} 线只有 {k} 年数据'
# 无 None / 空值混入表格
for tbl, name in ((T21, '2-1'), (T22, '2-2')):
    assert 'None' not in tbl, f'表 {name} 含 None'
    assert 'nan' not in tbl, f'表 {name} 含 nan'

# ================= 替换 =================
s = REPORT.read_text(encoding='utf-8')

# 表 2-1：表头行 → 末行（以空行前的连续表格行为界）
m21 = re.search(r'\| 综合名次 \| 初中 \|.*?\n\n', s, re.S)
assert m21, '未定位到表 2-1'
s = s[:m21.start()] + T21 + '\n\n' + s[m21.end():]

# 表 2-2：以「| 初中 | P加权（名次） |」开头到空行
m22 = re.search(r'\| 初中 \| P加权 \|.*?\n\n', s, re.S)
assert m22, '未定位到表 2-2'
s = s[:m22.start()] + T22 + '\n\n' + s[m22.end():]

# 3.2：四条线**逐一**替换（每张表独立定位到下一个空行），不整块替换
for l in LINES:
    pat = re.compile(r'\*\*' + LINE_LABEL[l] + r'线\*\*\n\n\|.*?\n\n', re.S)
    m = pat.search(s)
    assert m, f'未定位到 {LINE_LABEL[l]}线表'
    s = s[:m.start()] + T32[l] + '\n\n' + s[m.end():]
# 复核：3.2 节的子节（3.2.1 / 3.2.2）必须仍在
assert '#### 3.2.1' in s and '#### 3.2.2' in s, '3.2 子节丢失'
assert '### 3.3' in s, '3.3 丢失'

# 4.1 逐年离散度
m41 = re.search(r'\| 年 \| IQR \| σ \| 中位 \|.*?\n\n', s, re.S)
assert m41, '未定位到表 4-1'
s = s[:m41.start()] + T41 + '\n\n' + s[m41.end():]

REPORT.write_text(s, encoding='utf-8')
print(f'表 2-1 已重建（{len(RANKED)} 行 × 10 列）')
print(f'表 2-2 已重建（{len(RANKED)} 行 × {len(COLS2) + 1 + len(T_TIME)} 列）')
print(f'  近 2 年名次池 {len(pool_r2)} 所 ｜ 近 3 年名次池 {len(pool_r3)} 所（两者不同，表内需说明）')
print('  前 5：' + '、'.join(r['junior_high_school'] for r in RANKED[:5]))
