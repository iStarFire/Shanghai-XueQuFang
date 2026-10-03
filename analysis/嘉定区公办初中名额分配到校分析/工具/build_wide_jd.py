# -*- coding: utf-8 -*-
"""2.3 嘉定区名额到校初中水平分析：建宽表 + 排名表。

主口径（用户 2026-10-03 确认）：
  当年到校均分 = **当年全部区属市重点线**的名额加权平均
  区属线 = 142001 嘉定一中 / 142002 交大附中嘉定分校 / 142004 上师大附中嘉定新城分校
  委属线排除出排名口径（每年仅 1–4 所初中有名额、每格常仅 1 个名额）
排名主指标：逐年名次 → 分位 P（当年全池内），5 年均 P 为主排序
"""
import csv
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/嘉定区/学校'
OUT = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = [2022, 2023, 2024, 2025, 2026]
QLINE = ['142001', '142002', '142004']

def load(p, d=D):
    with open(f'{d}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

score = load('名额到校最低分数线-嘉定区-2022-2026.csv')
plan = load('名额到校计划-嘉定区-2023-2026.csv') + load('名额到校计划-嘉定区-2022-图片转录.csv')
S = {(r['junior_high_school'], r['senior_high_school_code'], int(r['year'])): float(r['min_score'])
     for r in score if r['senior_high_school_code'] in QLINE}
Q = {(r['junior_high_school'], r['senior_high_school_code'], int(r['year'])): int(r['quota'])
     for r in plan if r['senior_high_school_code'] in QLINE}
schools = sorted({k[0] for k in S} | {k[0] for k in Q})

def wmean(vals, wts):
    num = den = 0.0
    for v, w in zip(vals, wts):
        if v is not None and w:
            num += v * w
            den += w
    return num / den if den else None

per, ymu, ysg, ymed = {}, {}, {}, {}
_RAW = {}
for y in YEARS:
    lines_y = [c for c in QLINE if any((s, c, y) in Q for s in schools)]
    sch = {}
    for s in schools:
        pr = [(c, S.get((s, c, y)), Q.get((s, c, y), 0)) for c in lines_y]
        pr = [(c, v, q) for c, v, q in pr if v is not None]
        if pr:
            sch[s] = pr
    wq = {s: wmean([v for _, v, _ in p], [q for _, _, q in p]) for s, p in sch.items()}
    eq = {s: st.fmean([v for _, v, _ in p]) for s, p in sch.items()}
    vals = list(wq.values())
    ymu[y], ysg[y], ymed[y] = st.fmean(vals), st.pstdev(vals), st.median(vals)
    sv = sorted(vals)
    q1, q3 = sv[len(sv)//4], sv[(3*len(sv))//4]
    iqr = (q3 - q1) / 1.349 if q3 > q1 else None
    for s in sch:
        b = sum(1 for w in vals if w > wq[s])
        e = sum(1 for w in vals if w == wq[s])
        r = b + (e + 1) / 2
        per[(s, y)] = {'lines': len(sch[s]), 'wq': wq[s], 'eq': eq[s],
                       'rel': wq[s] - ymed[y], 'z': (wq[s] - ymu[y]) / ysg[y],
                       'zr': (wq[s] - ymed[y]) / iqr if iqr else None,
                       'P': 1 - (r - 1) / (len(vals) - 1), 'mean_rank': r, 'pool': len(vals),
                       'quota': sum(q for _, _, q in sch[s])}
print('逐年区属线与池量：')
for y in YEARS:
    ly = [c for c in QLINE if any((s, c, y) in Q for s in schools)]
    pool = max(v['pool'] for (s, yy), v in per.items() if yy == y)
    print(f'  {y}: 区属线 {ly}｜池量 {pool}')

WEIGHTS = {'等权': {y: 1 for y in YEARS},
           '线性1:5': {2022: 1, 2023: 2, 2024: 3, 2025: 4, 2026: 5},
           '指数1:16': {2022: 1, 2023: 2, 2024: 4, 2025: 8, 2026: 16},
           '近3年': {2022: 0, 2023: 0, 2024: 1, 2025: 1, 2026: 1}}
rows = []
for s in schools:
    ys = [y for y in YEARS if (s, y) in per]
    rec = {'junior_high_school': s, 'years_included': len(ys), 'years_list': ';'.join(map(str, ys))}
    for y in YEARS:
        v = per.get((s, y))
        for k in ('lines', 'wq', 'eq', 'rel', 'z', 'zr', 'P', 'mean_rank', 'quota'):
            rec[f'{k}_{y}'] = round(v[k], 4) if v and v[k] is not None else ''
        _RAW[(s, y)] = v
    for wn, w in WEIGHTS.items():
        for k, tag in (('wq', 'w'), ('eq', 'e'), ('rel', 'r'), ('P', 'P'), ('z', 'z'), ('zr', 'zr')):
            _v = wmean([_RAW[(s, y)][k] for y in ys], [w[y] for y in ys])
            rec[f'{tag}_{wn}'] = round(_v, 4) if _v is not None else ''
    rec['quota_avg'] = round(st.fmean([_RAW[(s, y)]['quota'] for y in ys]), 2)
    rl = [_RAW[(s, y)]['rel'] for y in ys]
    rec['rel_2022'], rec['rel_2026'] = (rl[0] if ys else ''), (rl[-1] if ys else '')
    if len(ys) >= 3:
        xs = list(range(len(ys)))
        d = len(ys) * sum((i - st.fmean(xs)) ** 2 for i in xs)
        rec['SEN'] = round(sum((xs[i] - st.fmean(xs)) * (rl[i] - st.fmean(rl)) for i in xs) / d, 3)
    else:
        rec['SEN'] = ''
    rows.append(rec)
core = [r for r in rows if r['years_included'] >= 4]
print(f'\n五年全勤 {len([r for r in rows if r["years_included"]==5])}｜n≥4 入榜 {len(core)}｜n<4 {len([r for r in rows if r["years_included"]<4])}')

def rank(key, desc=True, data=None):
    data = data or core
    o = sorted([r for r in data if r.get(key) not in ('', None)],
               key=lambda r: -r[key] if desc else r[key])
    return {r['junior_high_school']: i for i, r in enumerate(o, 1)}

R = {k: rank(k) for k in ('P_等权', 'P_线性1:5', 'P_指数1:16', 'P_近3年', 'r_等权')}
Re, Rz, Rzr = rank('e_等权'), rank('z_等权'), rank('zr_等权')
out = []
for r in core:
    n = r['junior_high_school']
    out.append({'junior_high_school': n, 'rank_P_wq': R['P_等权'].get(n, ''), 'P_wq': r['P_等权'],
                'rank_rel': R['r_等权'].get(n, ''), 'rel_avg': r['r_等权'],
                'rank_P_lin': R['P_线性1:5'].get(n, ''), 'rank_P_exp': R['P_指数1:16'].get(n, ''),
                'rank_P_recent3': R['P_近3年'].get(n, ''), 'rank_eq': Re.get(n, ''),
                'rank_Z': Rz.get(n, ''), 'rank_ZR': Rzr.get(n, ''), 'quota_avg': r['quota_avg'],
                'SEN': r['SEN'], 'rel_2022': r['rel_2022'], 'rel_2026': r['rel_2026'],
                'years_included': r['years_included'], 'P_lin': r['P_线性1:5'],
                'P_exp': r['P_指数1:16'], 'P_recent3': r['P_近3年'],
                'eq_avg': r['e_等权'], 'Z_wq': r['z_等权'], 'ZR_wq': r['zr_等权']})
out.sort(key=lambda r: r['rank_P_wq'])
for path, data in ((f'{OUT}/rank-标准化-嘉定区-2022-2026.csv', out),
                   (f'{OUT}/宽表-初中水平-嘉定区-2022-2026.csv', rows)):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)
    print(f'写出 {len(data)} 行 -> {path.split("/")[-1]}')
print('\n=== 名额加权综合口径排名（n≥4）===')
print(f"{'名':>3} {'初中':<26}{'P_wq':>7}{'均名':>7}{'名额':>7}{'SEN':>8}{'线性':>5}{'指数':>5}{'近3':>5}")
for r in out[:14]:
    print(f"  {r['rank_P_wq']:>2} {r['junior_high_school']:<26}{r['P_wq']:>7.3f}{r['rel_avg']:>7.2f}"
          f"{r['quota_avg']:>7.1f}{str(r['SEN']):>8}{r['rank_P_lin']:>5}{r['rank_P_exp']:>5}{r['rank_P_recent3']:>5}")

# ---------- 逐年离散度（收敛） ----------
print('\n=== 逐年离散度与收敛 ===')
for y in YEARS:
    v = sorted(per[(s, y)]['wq'] for s in schools if (s, y) in per)
    n = len(v)
    print(f'  {y}: n={n} σ={st.pstdev(v):.2f} IQR={v[n*3//4]-v[n//4]:.1f} 极差={max(v)-min(v):.1f}')
# 收敛回归：rel_y = a + b * rel_2022 + e（仅 5 年全勤样本）
full = [r for r in rows if r['years_included'] == 5]
xs = [float(r['rel_2022']) for r in full]
for y in YEARS[1:]:
    ys_ = [float(r[f'rel_{y}']) for r in full]
    b = st.correlation(xs, ys_) if hasattr(st, 'correlation') else None
    mx, my = st.fmean(xs), st.fmean(ys_)
    cov = sum((a-mx)*(c-my) for a, c in zip(xs, ys_)); vx = sum((a-mx)**2 for a in xs)
    slope = cov/vx; icpt = my - slope*mx
    fit = [icpt + slope*a for a in xs]
    sse = sum((c-f)**2 for c, f in zip(ys_, fit)); sst = sum((c-my)**2 for c in ys_)
    r2 = 1 - sse/sst if sst else 0
    resid = [(r['junior_high_school'], c-f) for r, c, f in zip(full, ys_, fit)]
    sd = st.pstdev([x[1] for x in resid]) or 1
    z = [x[1]/sd for x in resid]
    outz = sorted([(abs(v_), r[0], v_) for r, v_ in zip(resid, z)], reverse=True)
    print(f'  {y} vs 2022: b={slope:+.3f} R²={r2:.3f} n={len(full)}｜|z|≥1 的学校 {sum(1 for a,_,_ in outz if a>=1)} 所')
    for a, nm, v_ in outz[:5]:
        if a >= 0.7:
            print(f'       {nm:<26} 残差 {v_:+.2f}')


# ---------- 规模（名额）与位次：两层检验 ----------
def sp(x, y):
    def rk(a):
        s_ = sorted(a)
        return [sum(1 for t in s_ if t < v) + (sum(1 for t in s_ if t == v) + 1) / 2 for v in a]
    rx, ry = rk(x), rk(y)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None

print('\n=== 名额（规模代理）与位次的关系 ===')
q5 = [float(r['quota_avg']) for r in core]
P5 = [float(r['P_等权']) for r in core]
R5 = [float(r['r_等权']) for r in core]
print(f'  跨样本 n={len(core)}  Spearman(名额, P) = {sp(q5, P5):+.3f}   Spearman(名额, rel均名) = {sp(q5, R5):+.3f}')
# 同线内：该校该线名额 vs 该线名次
A, B = [], []
for y in YEARS:
    for code in [c for c in QLINE if any((s, c, y) in Q for s in schools)]:
        vals = {s: S[(s, code, y)] for s in schools if (s, code, y) in S}
        for s, v in vals.items():
            b = sum(1 for w in vals.values() if w > v)
            e = sum(1 for w in vals.values() if w == v)
            qq = Q.get((s, code, y), 0)
            if qq > 0:
                A.append(qq)
                B.append(b + (e + 1) / 2)
print(f'  同线内 n={len(A)}  Spearman(该校该线名额, 该线名次) = {sp(A, B):+.3f}  （名次大=差；负=名额越多名次越好）')
for code in [c for c in QLINE]:
    A1, B1 = [], []
    for y in YEARS:
        vals = {s: S[(s, code, y)] for s in schools if (s, code, y) in S}
        for s, v in vals.items():
            b = sum(1 for w in vals.values() if w > v)
            e = sum(1 for w in vals.values() if w == v)
            qq = Q.get((s, code, y), 0)
            if qq > 0:
                A1.append(qq)
                B1.append(b + (e + 1) / 2)
    if len(A1) > 20:
        print(f'    {code}: n={len(A1):>3} ρ={sp(A1, B1):+.3f}')

# ---------- 名额占比离散 + 切点深度 ----------
print('\n=== 名额占比离散与切点深度 ===')
for code in QLINE:
    line = []
    for y in YEARS:
        base, q = {}, {}
        for s in schools:
            tot = sum(Q.get((s, c, y), 0) for c in QLINE)
            if tot and (s, code, y) in S and Q.get((s, code, y), 0) > 0:
                base[s] = tot
                q[s] = Q[(s, code, y)]
        if len(base) >= 5:
            v = sorted(q[s] / base[s] for s in base)
            line.append(f'{y}: 极差 {max(v)-min(v):.3f} 中位 {st.median(v):.3f} 最大 {max(v):.3f}')
    if line:
        print(f'  {code} 占本校区属名额: ' + ' | '.join(line))
# 切点深度 = 该线名额占本校区属名额的中位 × 覆盖率估算
print('\n  区内 4 条区属线名额合计/年:',
      {y: sum(Q.get((s, c, y), 0) for s in schools for c in QLINE) for y in YEARS})

# ---------- 头/尾分组（仅 2025–2026：3 条区属线） ----------
print('\n=== 2025–2026 头/尾分组（3 条区属线，取最高 1 + 最低 1）===')
NAME = {'142001': '嘉定一中', '142002': '交大附中嘉定分校', '142004': '上师大附中嘉定新城'}
for y in (2025, 2026):
    diff = {}
    for code in QLINE:
        vals = {s: S[(s, code, y)] for s in schools if (s, code, y) in S}
        diff[code] = st.fmean(vals.values())
    order = sorted(diff, key=lambda c: -diff[c])
    head, tail = order[0], order[-1]
    print(f'  {y} 线难度: ' + ' > '.join(f'{NAME[c]}({diff[c]:.1f})' for c in order) + f'｜头={NAME[head]} 尾={NAME[tail]}')
    for tag, code in (('头', head), ('尾', tail)):
        pv = {}
        for s in schools:
            if (s, code, y) not in S:
                continue
            vals = {x: S[(x, code, y)] for x in schools if (x, code, y) in S}
            v = S[(s, code, y)]
            b = sum(1 for w in vals.values() if w > v)
            e = sum(1 for w in vals.values() if w == v)
            pv[s] = 1 - ((b + (e + 1) / 2) - 1) / (len(vals) - 1)
        top = sorted(pv.items(), key=lambda t: -t[1])[:5]
        print(f'     {tag}线({NAME[code]}) 前 5: ' + '、'.join(f'{k.replace("上海市嘉定区","")} {v:.2f}' for k, v in top))

# ---------- 公办 / 民办 ----------
print('\n=== 公办 vs 民办（名称初判）===')
priv = {r['junior_high_school'] for r in load('初中名录-公办民办-嘉定区-2026.csv')
        if r['ownership'] == '民办'}
for r in core:
    r['own'] = '民办' if r['junior_high_school'] in priv else '公办'
for tag in ('公办', '民办'):
    g = [r for r in core if r['own'] == tag]
    if g:
        print(f'  {tag}: n={len(g)}｜P 均值 {st.fmean([float(r["P_等权"]) for r in g]):.3f}｜'
              f'rel 均名 {st.fmean([float(r["r_等权"]) for r in g]):+.2f}｜'
              f'名额均值 {st.fmean([float(r["quota_avg"]) for r in g]):.1f}｜'
              f'前 5 名次 {sorted(int(r["P_等权"]*0)+0 for r in g)[:0] or [int(r.get("rank_P_wq") or 0) for r in g][:5]}')
print('  民办入榜学校:', [r['junior_high_school'] for r in core if r['own'] == '民办'])
print('  民办未入榜(n<4):', sorted(priv - {r['junior_high_school'] for r in core}))

# ---------- 委属线观察（不进排名） ----------
print('\n=== 委属线观察（每年仅 1–4 所初中有名额，不进排名）===')
CODE2N2 = {'042032': '上海中学', '102056': '交大附中本部', '102057': '复旦附中',
            '152003': '华师大二附中', '152006': '上师大附中'}
sc_all = load('名额到校最低分数线-嘉定区-2022-2026.csv')
for code, nm in CODE2N2.items():
    row = []
    for y in YEARS:
        cs = [r['junior_high_school'] for r in sc_all
              if r['senior_high_school_code'] == code and r['year'] == str(y)]
        row.append(len(cs))
    print(f'  {code} {nm:<12} 各年覆盖: {row}  合计 {sum(row)} 所次')
