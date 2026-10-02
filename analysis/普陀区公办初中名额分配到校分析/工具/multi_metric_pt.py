# -*- coding: utf-8 -*-
"""普陀区：多口径总表（2.3 计算）。

三组结构口径 + 综合口径，并把既有单指标/时间权重口径汇到一张表：

- all  = 4 所区属（华二普陀/曹杨二中/晋元/宜川）
- head = 华二普陀/曹杨二中
- tail = 晋元/宜川
- comb = (P_all + P_head + P_tail) / 3      ← 用户选定的等权三组合成规则

自校验：P_all 必须与既有主口径 `rank-标准化-普陀区-2022-2026.csv` 的 `P` 逐值一致。
单指标（Z/ZR/均名）与时间权重（线性/指数/近3年）从既有 CSV 读取，不重算。
输出：rank-多口径总表-普陀区-2022-2026.csv
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
GROUPS = {
    'all': ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
            '上海市晋元高级中学', '上海市宜川中学'],
    'head': ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学'],
    'tail': ['上海市晋元高级中学', '上海市宜川中学'],
}


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def F(v):
    return float(v) if v not in ('', None) else None


raw = load(f'{D_S}/名额到校最低分数线-普陀区-2022-2026.csv')
S = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): float(r['min_score'])
     for r in raw if r['min_score'] not in ('', None)}
schools = sorted({k[0] for k in S})

# 计划名额（用于「年均到校计划数」）：口径 = 按该校有数据的年份求均值
plan = load(f'{D_S}/名额到校计划-普陀区-2022-2026.csv')
QP = {(r['junior_high_school'], r['senior_high_school'], int(r['year'])): int(r['quota'])
      for r in plan}
ALL9 = GROUPS['all'] + ['华东师范大学第二附属中学', '上海市上海中学', '复旦大学附属中学',
                        '上海交通大学附属中学', '上海师范大学附属中学']
cover_years = {c: [y for y in YEARS if any((c, h, y) in S for h in GROUPS['all'])]
               for c in schools}
QUOTA = {}
for c in schools:
    ys = cover_years[c]
    QUOTA[c] = (
        st.fmean([sum(QP.get((c, h, y), 0) for h in GROUPS['all']) for y in ys]) if ys else None,
        st.fmean([sum(QP.get((c, h, y), 0) for h in ALL9) for y in ys]) if ys else None,
    )


def group_P(lines):
    """返回 (P聚合, Z聚合, ZR聚合, 逐年池量)。Z 用 μ/σ；ZR 用 中位/(IQR/1.349)。"""
    per = {}
    for c in schools:
        for y in YEARS:
            vs = [S[(c, h, y)] for h in lines if (c, h, y) in S]
            if vs:
                per[(c, y)] = st.fmean(vs)
    Py, Zy, ZRy, py = {}, {}, {}, {}
    for y in YEARS:
        vals = {c: per[(c, y)] for c in schools if (c, y) in per}
        xs = sorted(vals.values())
        n = len(xs)
        mu, sg = st.fmean(xs), st.pstdev(xs)
        med = st.median(xs)
        iqr = xs[n * 3 // 4] - xs[n // 4]
        rs = iqr / 1.349 if iqr else None
        py[y] = n
        for c, v in vals.items():
            b = sum(1 for w in xs if w > v)
            e = sum(1 for w in xs if w == v)
            Py[(c, y)] = 1 - ((b + (e + 1) / 2) - 1) / (n - 1)
            Zy[(c, y)] = (v - mu) / sg
            if rs:
                ZRy[(c, y)] = (v - med) / rs
    def agg(D):
        out = {}
        for c in schools:
            v = [D[(c, y)] for y in YEARS if (c, y) in D]
            if v:
                out[c] = st.fmean(v)
        return out
    return (agg(Py), agg(Zy), agg(ZRy), py, PA_N if False else {c: len([y for y in YEARS if (c, y) in Py]) for c in schools})


PA, ZA, ZRA, pool_all, ny_a = group_P(GROUPS['all'])
PH, ZH, ZRH, pool_head, ny_h = group_P(GROUPS['head'])
PT, ZT, ZRT, pool_tail, ny_t = group_P(GROUPS['tail'])

# ---- 自校验 P_all vs 既有主口径 ----
rcsv = load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')
ranked = [r for r in rcsv if r['ranked'] == '1']
bad = 0
for r in ranked:
    c = r['junior_high_school']
    if c in PA and abs(PA[c] - F(r['P'])) > 5e-4:
        bad += 1
        print(f'  [自校验失败] {c}: {PA[c]:.5f} vs {r["P"]}')
print(f'自校验：{len(ranked)} 所 P_all vs 主口径 CSV，不一致 {bad} 项')

# ---- 既有口径读取 ----
wcsv = {r['junior_high_school']: r for r in load(f'{D_A}/rank-加权敏感性-普陀区-2022-2026.csv')}
wide = {r['junior_high_school']: r for r in load(f'{D_A}/宽表-初中水平-普陀区-2022-2026.csv')}


def rank_of(vals, desc):
    """给 {校: 值} 排名次（1 = 最好）。"""
    s = sorted(vals.items(), key=lambda kv: -kv[1] if desc else kv[1])
    return {c: i for i, (c, _) in enumerate(s, 1)}


rows = []
for r in ranked:
    c = r['junior_high_school']
    w = wcsv[c]
    rows.append({
        'junior_high_school': c,
        'n_years': ny_a[c],
        'P_comb': round((PA[c] + PH[c] + PT[c]) / 3, 6),
        'P_all': round(PA[c], 6), 'P_head': round(PH[c], 6), 'P_tail': round(PT[c], 6),
        'P': F(r['P']), 'Z': F(r['Z']), 'ZR': F(r['ZR']),
        'mean_rank': F(r['old_mean_rank']),
        'P_lin': F(w['P_lin']), 'P_exp': F(w['P_exp']), 'P_recent3': F(w['P_recent3']),
        'Z_comb': round((ZA[c] + ZH[c] + ZT[c]) / 3, 6),
        'ZR_comb': round((ZRA[c] + ZRH[c] + ZRT[c]) / 3, 6),
        'quota4_avg': round(QUOTA[c][0], 4), 'quota_all_avg': round(QUOTA[c][1], 4),
    })

for key, desc in [('P_comb', True), ('Z_comb', True), ('ZR_comb', True),
                  ('P_all', True), ('P_head', True), ('P_tail', True),
                  ('P', True), ('Z', True), ('ZR', True), ('mean_rank', False),
                  ('P_lin', True), ('P_exp', True), ('P_recent3', True)]:
    rk = rank_of({d['junior_high_school']: d[key] for d in rows}, desc)
    for d in rows:
        d['rank_' + key] = rk[d['junior_high_school']]

cols = ['junior_high_school', 'n_years', 'P_comb', 'rank_P_comb',
        'Z_comb', 'rank_Z_comb', 'ZR_comb', 'rank_ZR_comb',
        'P_all', 'rank_P_all', 'P_head', 'rank_P_head', 'P_tail', 'rank_P_tail',
        'P', 'rank_P', 'Z', 'rank_Z', 'ZR', 'rank_ZR', 'mean_rank', 'rank_mean_rank',
        'P_lin', 'rank_P_lin', 'P_exp', 'rank_P_exp', 'P_recent3', 'rank_P_recent3',
        'quota4_avg', 'quota_all_avg']
with open(f'{D_A}/rank-多口径总表-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for d in sorted(rows, key=lambda d: d['rank_P_comb']):
        w.writerow({k: d[k] for k in cols})

# ---- 控制台报告 ----
def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((p - mx) * (q - my) for p, q in zip(rx, ry))
    return num / ((sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5)


print(f'\n逐年组内池量：all={pool_all} head={pool_head} tail={pool_tail}')
print(f"三组相关性：Spearman(all,head)={spearman([d['P_all'] for d in rows], [d['P_head'] for d in rows]):+.3f}  "
      f"(all,tail)={spearman([d['P_all'] for d in rows], [d['P_tail'] for d in rows]):+.3f}  "
      f"(head,tail)={spearman([d['P_head'] for d in rows], [d['P_tail'] for d in rows]):+.3f}")

print('\n== 综合口径总表（P_comb 降序）==')
print(f"{'名':>3} {'初中':<26}{'P综合':>7}{'全身':>6}{'头':>5}{'尾':>5}{'覆盖':>5}")
for d in sorted(rows, key=lambda d: d['rank_P_comb']):
    print(f"{d['rank_P_comb']:>3} {d['junior_high_school'].replace('上海市',''):<26}"
          f"{d['P_comb']:>7.3f}{d['rank_P_all']:>6}{d['rank_P_head']:>5}{d['rank_P_tail']:>5}"
          f"{str(d['n_years']) + '年':>5}")

print('\n== 偏科最大的学校（三组名次极差）==')
sp = sorted(rows, key=lambda d: -(max(d['rank_P_all'], d['rank_P_head'], d['rank_P_tail'])
                                  - min(d['rank_P_all'], d['rank_P_head'], d['rank_P_tail'])))
for d in sp[:8]:
    rng = max(d['rank_P_all'], d['rank_P_head'], d['rank_P_tail']) - min(d['rank_P_all'], d['rank_P_head'], d['rank_P_tail'])
    print(f"  {d['junior_high_school'].replace('上海市',''):<24} 全身第{d['rank_P_all']:>2} 头部第{d['rank_P_head']:>2} "
          f"尾部第{d['rank_P_tail']:>2}  极差{rng}  综合第{d['rank_P_comb']}")

print('\n== 单指标名次对照（前 10）==')
for d in sorted(rows, key=lambda d: d['rank_P_comb'])[:10]:
    print(f"  {d['junior_high_school'].replace('上海市',''):<24} 综合{d['rank_P_comb']:>2} "
          f"P{d['rank_P']:>2} Z{d['rank_Z']:>2} ZR{d['rank_ZR']:>2} 均名{d['rank_mean_rank']:>2} "
          f"线性{d['rank_P_lin']:>2} 指数{d['rank_P_exp']:>2} 近3年{d['rank_P_recent3']:>2}")
