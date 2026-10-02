# -*- coding: utf-8 -*-
"""普陀区：主口径 P 的时间加权变体与敏感性（2.3 计算）。

- 逐年 P：从原始分数线重建 base4 均分 → 当年池内名次（平均名次法）→ P_it = 1-(rank-1)/(n-1)
  （普陀宽表无逐年列，故必须重算）
- 自校验：P_eq 必须与 rank-标准化-普陀区-2022-2026.csv 的 P 逐值一致
- 输出：rank-加权敏感性-普陀区-2022-2026.csv（4 口径 P + 名次 + 相对等权的位次变动）
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_S = f"{BASE}/data/普陀区/学校"
D_A = f"{BASE}/analysis/普陀区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
QU = ['华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']
W = {
    'eq': {2022: 1, 2023: 1, 2024: 1, 2025: 1, 2026: 1},
    'lin': {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
    'exp': {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
    'recent3': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1},
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

# ---- 逐年 P ----
per = {}
for c in schools:
    for y in YEARS:
        vs = [S[(c, h, y)] for h in QU if (c, h, y) in S]
        if vs:
            per[(c, y)] = st.fmean(vs)
Py = {}
pool = {}
for y in YEARS:
    vals = {c: per[(c, y)] for c in schools if (c, y) in per}
    xs = list(vals.values())
    pool[y] = len(xs)
    for c, v in vals.items():
        better = sum(1 for w in xs if w > v)
        eq = sum(1 for w in xs if w == v)
        r = better + (eq + 1) / 2
        Py[(c, y)] = 1 - (r - 1) / (len(xs) - 1)

# ---- 自校验 P_eq vs 既有 rank CSV ----
rcsv = load(f'{D_A}/rank-标准化-普陀区-2022-2026.csv')
ranked = [r for r in rcsv if r['ranked'] == '1']
bad = 0
for r in ranked:
    c = r['junior_high_school']
    mine = st.fmean([Py[(c, y)] for y in YEARS if (c, y) in Py])
    got = F(r['P'])
    if got is None or abs(mine - got) > 5e-4:
        bad += 1
        print(f"  [自校验失败] {c}: 重建 P_eq={mine:.5f} vs rank CSV P={got}")
print(f'自校验：{len(ranked)} 所的 P_eq 与 rank-标准化 CSV 比对，不一致 {bad} 项')


def wavg(c, w):
    num = den = 0.0
    for y in YEARS:
        if w[y] == 0 or (c, y) not in Py:
            continue
        num += w[y] * Py[(c, y)]
        den += w[y]
    return num / den if den else None


rows = []
for r in ranked:
    c = r['junior_high_school']
    d = {'junior_high_school': c, 'n_years': sum(1 for y in YEARS if (c, y) in Py)}
    for k in W:
        d['P_' + k] = round(wavg(c, W[k]), 6)
    rows.append(d)

# 名次（各口径独立排名，降序）
for k in W:
    key = 'P_' + k
    order = sorted(rows, key=lambda d: -d[key])
    for i, d in enumerate(order, 1):
        d['rank_' + k] = i
for d in rows:
    for k in ['lin', 'exp', 'recent3']:
        d['shift_' + k] = d['rank_' + k] - d['rank_eq']

cols = ['junior_high_school', 'n_years', 'P_eq', 'P_lin', 'P_exp', 'P_recent3',
        'rank_eq', 'rank_lin', 'rank_exp', 'rank_recent3',
        'shift_lin', 'shift_exp', 'shift_recent3']
with open(f'{D_A}/rank-加权敏感性-普陀区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for d in sorted(rows, key=lambda d: d['rank_eq']):
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


print('\n== 权重方案敏感性（相对等权榜）==')
print('  权重逐年：2022→2026')
for k, label in [('lin', '线性 1:2:3:4:5'), ('exp', '指数 1:2:4:8:16'), ('recent3', '近3年 0:0:1:1:1')]:
    sp = spearman([d['P_eq'] for d in rows], [d['P_' + k] for d in rows])
    shifts = [(d['junior_high_school'], d['shift_' + k]) for d in rows]
    big = [t for t in shifts if abs(t[1]) >= 3]
    mx = max(shifts, key=lambda t: abs(t[1]))
    print(f'  {label:<18} Spearman={sp:+.3f}  最大变动={mx[1]:+d}（{mx[0]}）  ≥3位 {len(big)} 所')
    print('      ', ', '.join(f'{c.replace("上海市","")}{s:+d}' for c, s in big))

print('\n== 逐年 P 明细（等权榜前 8 + 变动最大 4 所）==')
watch = [d['junior_high_school'] for d in sorted(rows, key=lambda d: d['rank_eq'])[:8]]
watch += [d['junior_high_school'] for d in sorted(rows, key=lambda d: -abs(d['shift_exp']))[:4]]
seen = []
for c in watch:
    if c in seen:
        continue
    seen.append(c)
    d = [x for x in rows if x['junior_high_school'] == c][0]
    yr = ' '.join(f'{Py[(c, y)]:.2f}' for y in YEARS)
    print(f'  {c.replace("上海市", ""):<24} {yr}  | 等权第{d["rank_eq"]:>2} 线性第{d["rank_lin"]:>2} '
          f'指数第{d["rank_exp"]:>2} 近3年第{d["rank_recent3"]:>2}')
print(f'\n逐年排名池：{pool}')
