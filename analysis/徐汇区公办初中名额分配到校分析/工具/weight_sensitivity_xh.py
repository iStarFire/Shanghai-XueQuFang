# -*- coding: utf-8 -*-
"""徐汇区：主口径 P 的时间加权变体与敏感性（2.3 计算）。

- 逐年 P：从宽表逐年分层分数列（score_{code}_{y}，基线 = BASE5）重建
  `mean_score_base5(c,y)` → 当年池内名次（平均名次法）→ P_it = 1-(rank-1)/(n-1)
  口径与 `工具/build_rank_v2.py` 一致（A8 的主口径）。
- 自校验：P_eq 必须与 rank-标准化-徐汇区-2022-2026.csv 的 P 逐值一致。
- 输出：rank-加权敏感性-徐汇区-2022-2026.csv
"""
import csv, statistics as st

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{BASE}/analysis/徐汇区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
BASE5 = ["042001", "042008", "042035", "043015", "042036"]   # 二中/南模/位育/南洋/复附徐汇
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


wide = load(f'{D}/宽表-初中水平-徐汇区-2022-2026.csv')

# ---- 逐年 base5 均分与名次（与 build_rank_v2.py 同口径）----
score5 = {}
for r in wide:
    c = r['junior_high_school']
    for y in YEARS:
        vs = [F(r.get(f'score_{h}_{y}')) for h in BASE5]
        vs = [v for v in vs if v is not None]
        if vs:
            score5[(c, y)] = st.fmean(vs)
pool = {y: [v for (c, yy), v in score5.items() if yy == y] for y in YEARS}
n = {y: len(pool[y]) for y in YEARS}
Py = {}
for y in YEARS:
    for (c, yy), v in score5.items():
        if yy != y:
            continue
        better = sum(1 for w in pool[y] if w > v)
        eq = sum(1 for w in pool[y] if w == v)
        r = better + (eq + 1) / 2
        Py[(c, y)] = 1 - (r - 1) / (n[y] - 1)

# ---- 自校验 ----
rcsv = load(f'{D}/rank-标准化-徐汇区-2022-2026.csv')
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
for k in W:
    for i, d in enumerate(sorted(rows, key=lambda d: -d['P_' + k]), 1):
        d['rank_' + k] = i
for d in rows:
    for k in ['lin', 'exp', 'recent3']:
        d['shift_' + k] = d['rank_' + k] - d['rank_eq']

cols = ['junior_high_school', 'n_years', 'P_eq', 'P_lin', 'P_exp', 'P_recent3',
        'rank_eq', 'rank_lin', 'rank_exp', 'rank_recent3',
        'shift_lin', 'shift_exp', 'shift_recent3']
with open(f'{D}/rank-加权敏感性-徐汇区-2022-2026.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for d in sorted(rows, key=lambda d: d['rank_eq']):
        w.writerow({k: d[k] for k in cols})


def spearman(x, y):
    def rk(a):
        s = sorted(a)
        return [sum(1 for w in s if w < t) + (sum(1 for w in s if w == t) + 1) / 2 for t in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((p - mx) * (q - my) for p, q in zip(rx, ry))
    return num / ((sum((p - mx) ** 2 for p in rx) * sum((q - my) ** 2 for q in ry)) ** 0.5)


print('\n== 权重方案敏感性（相对等权榜）==')
for k, label in [('lin', '线性 1:2:3:4:5'), ('exp', '指数 1:2:4:8:16'), ('recent3', '近3年 0:0:1:1:1')]:
    sp = spearman([d['P_eq'] for d in rows], [d['P_' + k] for d in rows])
    shifts = [(d['junior_high_school'], d['shift_' + k]) for d in rows]
    big = [t for t in shifts if abs(t[1]) >= 3]
    mx = max(shifts, key=lambda t: abs(t[1]))
    print(f'  {label:<18} Spearman={sp:+.3f}  最大变动={mx[1]:+d}（{mx[0]}）  ≥3位 {len(big)} 所')
    print('      ', ', '.join(f'{c.replace("上海市","")}{s:+d}' for c, s in big))

print('\n== 逐年 P 明细（等权榜前 6 + 变动最大 3 所）==')
watch = [d['junior_high_school'] for d in sorted(rows, key=lambda d: d['rank_eq'])[:6]]
watch += [d['junior_high_school'] for d in sorted(rows, key=lambda d: -abs(d['shift_recent3']))[:3]]
seen = []
for c in watch:
    if c in seen:
        continue
    seen.append(c)
    d = [x for x in rows if x['junior_high_school'] == c][0]
    yr = ' '.join(f'{Py[(c, y)]:.2f}' if (c, y) in Py else ' -- ' for y in YEARS)
    print(f'  {c.replace("上海市", ""):<24} {yr}  | 等权第{d["rank_eq"]:>2} 线性第{d["rank_lin"]:>2} '
          f'指数第{d["rank_exp"]:>2} 近3年第{d["rank_recent3"]:>2}')
print(f'\n逐年排名池：{n}')
