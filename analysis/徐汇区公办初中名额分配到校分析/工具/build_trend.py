"""排名趋势分析（R5 / design.md §9）。

主口径：rel(c,y) = mean_score_base4(c,y) − 当年 CORE 中位（单位：分）
判定：严格三重条件（方向一致 / 去尾不翻转 / 留一法非单年驱动）

输出：analysis/徐汇区公办初中名额分配到校分析/趋势分析-徐汇区-2022-2026.csv
"""
import csv, statistics as st

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
OUT = f"{ROOT}/analysis/徐汇区公办初中名额分配到校分析"
YEARS = [2022, 2023, 2024, 2025, 2026]
# 幅度阈值（design.md §9.3）：5 年窗内累计约 4 分。写定后不得事后调整。
SEN_MIN = 1.0


def load_core():
    with open(f'{OUT}/宽表-初中水平-徐汇区-2022-2026.csv', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    core = [r for r in rows if r['years_included'] == '5']
    # 全部公办（含非 CORE），用于「基准换成当年全部有效公办」的互校
    return rows, core


def num(r, k):
    v = r.get(k, '')
    return float(v) if v not in ('', None) else None


def theil_sen(pts):
    """Theil–Sen 斜率：全部点对斜率的**中位数**。对单期异常稳健。"""
    pts = [(float(x), float(y)) for x, y in pts]
    s = [(b[1] - a[1]) / (b[0] - a[0]) for i, a in enumerate(pts) for b in pts[i + 1:]]
    return st.median(s) if s else None


def spearman(pts):
    """年份与 rel 的 Spearman 秩相关（5 个点，年份无并列）。"""
    n = len(pts)
    xs = [p[0] for p in pts]
    ys = sorted(p[1] for p in pts)
    ry = {v: i + 1 for i, v in enumerate(ys)}
    # 并列取平均秩
    from collections import defaultdict
    grp = defaultdict(list)
    for i, v in enumerate(ys):
        grp[v].append(i + 1)
    ry = {v: st.mean(r) for v, r in grp.items()}
    ryv = [ry[p[1]] for p in pts]
    rxv = [float(i + 1) for i in range(n)]
    mx, my = st.mean(rxv), st.mean(ryv)
    num_ = sum((a - mx) * (b - my) for a, b in zip(rxv, ryv))
    den = (sum((a - mx) ** 2 for a in rxv) * sum((b - my) ** 2 for b in ryv)) ** 0.5
    return num_ / den if den else None


def load_pairs():
    """每校每年「区属 4 校基线」的有效对数。

    主口径的均值分母是有效对数（design.md §5.2），故若某校某年对数不齐，
    其均值与相邻年**不可比**——这类样本必须单独标注。
    """
    import collections
    D = f"{ROOT}/data/徐汇区/学校"
    with open(f'{D}/名额到校最低分数线-徐汇区-2022-2026.csv', encoding='utf-8-sig') as f:
        S = list(csv.DictReader(f))
    base4 = ['042001', '042008', '042035', '043015']
    acc = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in S:
        if r['senior_high_school_code'] in base4:
            acc[r['junior_high_school_code']][int(r['year'])].add(
                r['senior_high_school_code'])
    return {c: [len(v[y]) for y in YEARS] for c, v in acc.items()}


def main():
    rows, core = load_core()
    pairs = load_pairs()
    uneven = {c: s for c, s in pairs.items() if len(set(s)) > 1}
    print(f'[构成检查] 基线有效对数逐年不齐的学校: {len(uneven)} 所 {uneven}')
    print('           （满值 4；不齐则该校该年均值与相邻年不可比）')
    print()

    # --- 基准：当年 CORE 中位 ---
    med_core = {y: st.median([num(r, f'mean_score_base4_{y}') for r in core
                              if num(r, f'mean_score_base4_{y}') is not None])
                for y in YEARS}
    # 互校基准：当年全部有效公办中位
    med_all = {y: st.median([num(r, f'mean_score_base4_{y}') for r in rows
                             if num(r, f'mean_score_base4_{y}') is not None])
               for y in YEARS}
    print('CORE 中位   :', {y: round(med_core[y], 2) for y in YEARS})
    print('全部公办中位:', {y: round(med_all[y], 2) for y in YEARS})
    print()

    out = []
    for r in core:
        c = r['junior_high_school_code']
        rel = {y: (num(r, f'mean_score_base4_{y}') - med_core[y])
               if num(r, f'mean_score_base4_{y}') is not None else None
               for y in YEARS}
        pts = [(y, rel[y]) for y in YEARS if rel[y] is not None]
        if len(pts) < 5:
            continue
        sen = theil_sen(pts)
        sp = spearman(pts)
        sen_d26 = theil_sen(pts[:-1])
        loo = {y: theil_sen([p for p in pts if p[0] != y]) for y in YEARS}
        sign = lambda v: (1 if v > 0 else -1 if v < 0 else 0)
        loo_ok = all(sign(v) == sign(sen) for v in loo.values())

        # 名次口径（仅用于互校，不作主口径）
        rpts = [(y, num(r, f'mean_rank_base4_{y}')) for y in YEARS
                if num(r, f'mean_rank_base4_{y}') is not None]
        sen_rank = theil_sen(rpts)

        # 换基准互校
        rel2 = {y: num(r, f'mean_score_base4_{y}') - med_all[y] for y in YEARS}
        sen_all = theil_sen(sorted(rel2.items()))

        # --- 严格三重判定 ---
        c1 = (sign(sen) == sign(sp)) and sign(sen) != 0 and abs(sen) >= SEN_MIN
        c2 = sign(sen_d26) == sign(sen)
        c3 = loo_ok
        passed = c1 and c2 and c3
        if passed:
            direc = '上升' if sen > 0 else '下降'
        else:
            direc = '无趋势'
        reasons = []
        if not c1:
            if sign(sen) != sign(sp):
                reasons.append('①方向不一致(Sen与Spearman异号)')
            elif abs(sen) < SEN_MIN:
                reasons.append(f'①幅度不足(|{sen:.2f}|<{SEN_MIN})')
            else:
                reasons.append('①斜率或秩相关为 0')
        if not c2:
            reasons.append('②去尾翻转')
        if not c3:
            bad = [str(y) for y, v in loo.items() if sign(v) != sign(sen)]
            reasons.append(f'③单年驱动(删{"、".join(bad)}后翻转)')

        out.append({
            'junior_high_school': r['junior_high_school'],
            'junior_high_school_code': c,
            **{f'rel_{y}': round(rel[y], 2) for y in YEARS},
            'mean_rank_base4_avg': r['mean_rank_base4_avg'],
            'sen': round(sen, 3),
            'spearman': round(sp, 3) if sp is not None else '',
            'sen_drop26': round(sen_d26, 3),
            'sen_loo_min': round(min(loo.values()), 3),
            'sen_loo_max': round(max(loo.values()), 3),
            'loo_signs_consistent': loo_ok,
            'sen_rank': round(sen_rank, 3),
            'sen_base_all': round(sen_all, 3),
            'direction': direc,
            'passed': passed,
            'fail_reason': '；'.join(reasons),
            'base4_pairs': '/'.join(str(v) for v in pairs.get(c, [])),
            'pairs_uniform': len(set(pairs.get(c, []))) <= 1,
            # 近 3 年窗（design.md S11 要求的换窗敏感性）
            'sen_recent3': round(theil_sen(pts[-3:]), 3),
        })

    # --- 第二阶段诊断：扣除「整体收敛」可解释的部分（design.md §9.6）---
    # 注意：这是观察到「通过者中 4/5 的历史前五全在下降」之后补做的诊断，
    # 不是事前登记的门槛；主判定仍以上面的严格三重条件为准。
    xs = [d['rel_2022'] for d in out]
    ys = [d['rel_2026'] - d['rel_2022'] for d in out]
    n = len(xs)
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    a = my - b * mx
    res_all = [c - (a + b * x) for x, c in zip(xs, ys)]
    sd_res = st.pstdev(res_all)
    ss_res = sum(r ** 2 for r in res_all)
    ss_tot = sum((c - my) ** 2 for c in ys)
    r2 = 1 - ss_res / ss_tot
    for d, x, c, rs in zip(out, xs, ys, res_all):
        d['delta_rel'] = round(c, 2)
        d['convergence_pred'] = round(a + b * x, 2)
        d['residual'] = round(rs, 2)
        d['residual_z'] = round(rs / sd_res, 2) if sd_res else ''
        d['beyond_convergence'] = d['passed'] and abs(rs / sd_res) >= 1.0
    print(f'[收敛诊断] Δrel(22→26) = {a:.2f} + ({b:.3f})×rel_2022   '
          f'R² = {r2:.3f}   残差 SD = {sd_res:.2f}')
    print(f'            起点每高 1 分，五年后相对分差平均回落 {abs(b):.2f} 分')
    print()

    out.sort(key=lambda d: (not d['passed'], -d['sen']))
    head = (['junior_high_school', 'junior_high_school_code']
            + [f'rel_{y}' for y in YEARS]
            + ['mean_rank_base4_avg', 'sen', 'spearman', 'sen_drop26',
               'sen_loo_min', 'sen_loo_max', 'loo_signs_consistent',
               'sen_rank', 'sen_base_all', 'direction', 'passed', 'fail_reason',
               'base4_pairs', 'pairs_uniform', 'sen_recent3',
               'delta_rel', 'convergence_pred', 'residual', 'residual_z',
               'beyond_convergence'])
    path = f'{OUT}/趋势分析-徐汇区-2022-2026.csv'
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        w.writerows(out)

    print('=' * 100)
    print('严格三重判定通过的学校')
    print('=' * 100)
    print(f'{"初中":<24}{"历史均名":>8}{"Sen":>7}{"Spearman":>9}{"去26":>7}  逐年相对分差')
    for d in out:
        if not d['passed']:
            continue
        seq = [d[f'rel_{y}'] for y in YEARS]
        print(f'{d["junior_high_school"]:<24}{d["mean_rank_base4_avg"]:>8}'
              f'{d["sen"]:>7.2f}{d["spearman"]:>9.2f}{d["sen_drop26"]:>7.2f}  {seq}'
              f'  {d["direction"]}')
    n_pass = sum(1 for d in out if d['passed'])
    print(f'\n通过 {n_pass} 所 / 共 {len(out)} 所')
    print()
    print('=' * 100)
    print('未通过清单（逐条原因）')
    print('=' * 100)
    for d in out:
        if d['passed']:
            continue
        seq = [d[f'rel_{y}'] for y in YEARS]
        print(f'{d["junior_high_school"]:<24}Sen={d["sen"]:>6.2f}  {d["fail_reason"]}')
        print(f'{"":<24}逐年 {seq}')
    print()
    # design §9.5 降级条件检查
    dis = [d for d in out if d['passed']
           and (d['sen'] > 0) != (d['sen_rank'] < 0)]
    print(f'[降级检查] 分差口径通过但名次口径方向相反的学校: {len(dis)}/{n_pass}'
          f'  {[d["junior_high_school"] for d in dis]}')
    flip = [d for d in out if d['passed']
            and (d['sen'] > 0) != (d['sen_base_all'] > 0)]
    print(f'[换基准检查] 换成「全部公办中位」后方向翻转: {len(flip)}/{n_pass}'
          f'  {[d["junior_high_school"] for d in flip]}')
    rec3 = [d for d in out if d['passed']
            and (d['sen'] > 0) != (d['sen_recent3'] > 0)]
    print(f'[换窗检查] 近 3 年（2024-2026）方向与 5 年窗相反: {len(rec3)}/{n_pass}'
          f'  {[(d["junior_high_school"], d["sen"], d["sen_recent3"]) for d in rec3]}')
    beyond = [d for d in out if d['beyond_convergence']]
    print(f'[收敛诊断] 位移超出「整体收敛」可解释范围（|z|≥1）: {len(beyond)}/{n_pass}')
    for d in sorted(beyond, key=lambda x: -x['residual']):
        print(f'    {d["junior_high_school"]:<24} 残差 {d["residual"]:>7.2f}  '
              f'z={d["residual_z"]:>5.2f}  {d["direction"]}')
    print(f'\n已写出: {path}')


if __name__ == '__main__':
    main()
