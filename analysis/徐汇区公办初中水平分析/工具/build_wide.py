"""构建「徐汇区公办初中水平」大宽表（S6）。

口径与算法严格遵循 .trellis/tasks/09-30-xuhui-junior-high-level/design.md
§4（高中分层）、§5（指标）、§6（宽表结构）。

输出：
  analysis/徐汇区公办初中水平分析/宽表-初中水平-徐汇区-2022-2026.csv
"""
import csv, statistics as st

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{ROOT}/data/徐汇区/学校"
OUT = f"{ROOT}/analysis/徐汇区公办初中水平分析"
YEARS = [2022, 2023, 2024, 2025, 2026]

# ---- design.md §4 高中分层 ----
BASE4 = ['042001', '042008', '042035', '043015']
ZONE = {
    2022: ['042001', '042008', '042035', '043015'],
    2023: ['042001', '042008', '042035', '043015', '042036'],
    2024: ['042001', '042008', '042035', '043015', '042036'],
    2025: ['042001', '042008', '042035', '043015', '042036'],
    2026: ['042001', '042002', '042008', '042035', '042036', '043015'],
}
# 宽表计划/分数列固定用 2026 列序（design.md §6.2，已对 2026 表头核实）
ZONE_COLS = ['042008', '042035', '042001', '042002', '043015', '042036']
NANMO = '042008'

WEIGHTS = {
    'linear': {y: float(y - 2021) for y in YEARS},
    'exp': {y: 0.7 ** (2026 - y) for y in YEARS},
}
W_SUMMARY = ['mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
             'nanmo_rank_w_linear', 'nanmo_rank_w_exp']


def load(name):
    with open(f"{D}/{name}", encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def rank_of(pool, value):
    """平均名次法（design.md §5.5）。名次越小越好。"""
    if value is None:
        return None
    hi = sum(1 for v in pool if v > value)
    eq = sum(1 for v in pool if v == value)
    return 1 + hi + (eq - 1) / 2


def wavg(by_year, scheme):
    num = den = 0.0
    for y in YEARS:
        v = by_year.get(y)
        if v is None:
            continue
        w = WEIGHTS[scheme][y]
        num += w * v
        den += w
    return num / den if den else None


def num(x, nd=2):
    return '' if x is None else f'{x:.{nd}f}'


def build():
    plan = load('名额到校计划-徐汇区-2022-2026.csv')
    score = load('名额到校最低分数线-徐汇区-2022-2026.csv')
    alias = load('初中校名别名表-徐汇区.csv')
    roster = load('初中名录-公办民办-徐汇区-2026.csv')

    # ---- 公办/民办：名录校名 → 别名表 → 编号 ----
    name2code = {}
    for a in alias:
        name2code[a['canonical_name']] = a['school_code']
        for al in (a['alias_name'] or '').split(';'):
            if al:
                name2code[al] = a['school_code']
    minban = set()
    for r in roster:
        if r['ownership'] == '民办':
            c = name2code.get(r['school_name'])
            assert c, f'民办校名无法映射到编号: {r["school_name"]}'
            minban.add(c)

    # 校名按编号收集「逐年名」，再取**最新年份**的名字作为显示名。
    # 不能取其首次出现名——长表中 2022 年在前，会把 041328 显示成旧名
    # 「上海市长桥中学」，而该校 2025 起已改为「徐教院附中南部分校」，
    # 会被误读成两所不相干的学校（曾用名记入 former_names 列）。
    name_by_code = {}
    for r in plan + score:
        name_by_code.setdefault(r['junior_high_school_code'], {})[
            int(r['year'])] = r['junior_high_school']
    code2name = {c: m[max(m)] for c, m in name_by_code.items()}
    # 曾用名 = 历年出现过的**与现名不同**的写法（不能按「非最新年份」筛，
    # 那样会把与现名相同的历年写法也算成曾用名）
    former_names = {
        c: ';'.join(sorted({n for n in m.values() if n != code2name[c]}))
        for c, m in name_by_code.items()}
    renamed = {c: v for c, v in former_names.items() if v}
    print(f'用过旧名的学校 {len(renamed)} 所: '
          + '; '.join(f'{code2name[c]}(原{v})' for c, v in renamed.items()))
    P = {(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code']):
         r['quota_plan'] for r in plan}
    S = {(int(r['year']), r['junior_high_school_code'], r['senior_high_school_code']):
         r['min_score'] for r in score}

    gongban = [c for c in sorted(code2name) if c not in minban]

    def sv(c, y, h):
        v = S.get((y, c, h), '')
        return float(v) if v not in ('', None) else None

    def pv(c, y, h):
        v = P.get((y, c, h), '')
        return int(v) if v not in ('', None) else 0

    met = {}
    for y in YEARS:
        for c in gongban:
            e4 = [sv(c, y, h) for h in BASE4 if sv(c, y, h) is not None]
            ea = [sv(c, y, h) for h in ZONE[y] if sv(c, y, h) is not None]
            met[(c, y)] = {
                'plan': {h: P.get((y, c, h), '') for h in ZONE_COLS},
                'score': {h: sv(c, y, h) for h in ZONE_COLS},
                'quota_zone_total': sum(pv(c, y, h) for h in ZONE[y]),
                'valid_pairs': len(ea),
                'mean_score_base4': sum(e4) / len(e4) if e4 else None,
                'mean_score_all': sum(ea) / len(ea) if ea else None,
                'nanmo_score': sv(c, y, NANMO),
            }

    # ---- 逐年排名：样本 = 当年全部有效公办初中 ----
    for y in YEARS:
        for src, dst in (('mean_score_base4', 'mean_rank_base4'),
                         ('mean_score_all', 'mean_rank_all'),
                         ('nanmo_score', 'nanmo_rank')):
            pool = [met[(c, y)][src] for c in gongban
                    if met[(c, y)][src] is not None]
            for c in gongban:
                met[(c, y)][dst] = rank_of(pool, met[(c, y)][src])

    core = [c for c in gongban
            if all(met[(c, y)]['mean_score_base4'] is not None for y in YEARS)]

    # ---- 汇总列 ----
    summ = {}
    for c in gongban:
        rb = {y: met[(c, y)]['mean_rank_base4'] for y in YEARS}
        nm = {y: met[(c, y)]['nanmo_rank'] for y in YEARS}
        rbv = [rb[y] for y in YEARS if rb[y] is not None]
        nmv = [nm[y] for y in YEARS if nm[y] is not None]
        incl = [y for y in YEARS
                if met[(c, y)]['quota_zone_total'] > 0 or met[(c, y)]['valid_pairs'] > 0]
        summ[c] = {
            'years_included': len(incl),
            'years_list': ';'.join(str(y) for y in incl),
            'quota_zone_avg': sum(met[(c, y)]['quota_zone_total'] for y in YEARS)
                              / len(YEARS),
            'mean_rank_base4_avg': st.mean(rbv) if rbv else None,
            'mean_rank_base4_median': st.median(rbv) if rbv else None,
            'mean_rank_base4_var': (st.pvariance(rbv) if len(rbv) > 1
                                    else (0.0 if rbv else None)),
            'nanmo_rank_avg': st.mean(nmv) if nmv else None,
            'nanmo_rank_median': st.median(nmv) if nmv else None,
            'nanmo_rank_var': (st.pvariance(nmv) if len(nmv) > 1
                               else (0.0 if nmv else None)),
            'mean_rank_base4_w_linear': wavg(rb, 'linear'),
            'mean_rank_base4_w_exp': wavg(rb, 'exp'),
            'nanmo_rank_w_linear': wavg(nm, 'linear'),
            'nanmo_rank_w_exp': wavg(nm, 'exp'),
        }
    return met, summ, core, gongban, minban, code2name, former_names


def header():
    h = ['junior_high_school', 'junior_high_school_code',
         'junior_high_school_former_names', 'ownership',
         'years_included', 'years_list', 'quota_zone_avg',
         'mean_rank_base4_avg', 'mean_rank_base4_median', 'mean_rank_base4_var',
         'nanmo_rank_avg', 'nanmo_rank_median', 'nanmo_rank_var',
         'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
         'nanmo_rank_w_linear', 'nanmo_rank_w_exp']
    for y in [2026, 2025, 2024, 2023, 2022]:
        h += [f'plan_{c}_{y}' for c in ZONE_COLS]
        h += [f'score_{c}_{y}' for c in ZONE_COLS]
        h += [f'quota_zone_total_{y}', f'valid_pairs_{y}',
              f'mean_score_base4_{y}', f'mean_rank_base4_{y}',
              f'mean_score_all_{y}', f'mean_rank_all_{y}',
              f'nanmo_score_{y}', f'nanmo_rank_{y}']
    return h


def row_of(c, met, summ, code2name, former_names):
    s = summ[c]
    r = [code2name[c], c, former_names.get(c, ''), '公办',
         s['years_included'], s['years_list'],
         num(s['quota_zone_avg'], 3),
         num(s['mean_rank_base4_avg'], 3), num(s['mean_rank_base4_median'], 3),
         num(s['mean_rank_base4_var'], 3),
         num(s['nanmo_rank_avg'], 3), num(s['nanmo_rank_median'], 3),
         num(s['nanmo_rank_var'], 3)]
    for k in W_SUMMARY:
        r.append(num(s[k], 3))
    for y in [2026, 2025, 2024, 2023, 2022]:
        m = met[(c, y)]
        r += [m['plan'][h] for h in ZONE_COLS]
        r += [num(m['score'][h], 1) for h in ZONE_COLS]
        r += [m['quota_zone_total'], m['valid_pairs'],
              num(m['mean_score_base4'], 3), num(m['mean_rank_base4'], 2),
              num(m['mean_score_all'], 3), num(m['mean_rank_all'], 2),
              num(m['nanmo_score'], 1), num(m['nanmo_rank'], 2)]
    return r


if __name__ == '__main__':
    met, summ, core, gongban, minban, code2name, former_names = build()
    H = header()
    print(f'民办 {len(minban)} 所: {sorted(minban)}')
    print(f'初中 {len(code2name)} 所 → 公办 {len(gongban)} 所；CORE {len(core)} 所')
    print(f'宽表列数 {len(H)}')
    out = f'{OUT}/宽表-初中水平-徐汇区-2022-2026.csv'
    order = sorted(core, key=lambda c: (summ[c]['mean_rank_base4_avg'] is None,
                                        summ[c]['mean_rank_base4_avg'] or 0))
    rest = [c for c in sorted(gongban) if c not in core]
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(H)
        for c in order + rest:
            r = row_of(c, met, summ, code2name, former_names)
            assert len(r) == len(H), f'{c}: {len(r)} != {len(H)}'
            w.writerow(r)
    print(f'已写出: {out}  （CORE 在前，按 mean_rank_base4_avg 升序）')
