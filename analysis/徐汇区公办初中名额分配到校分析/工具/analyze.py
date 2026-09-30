"""徐汇区公办初中名额分配到校分析的计算部分（S7）。

读取宽表，输出 A1–A4 四个维度所需的全部数字。
报告只负责叙述，所有数字均来自本脚本，保证可复算。
"""
import csv, statistics as st

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
OUT = f"{ROOT}/analysis/徐汇区公办初中名额分配到校分析"
YEARS = [2026, 2025, 2024, 2023, 2022]      # 展示用倒序


def load():
    with open(f'{OUT}/宽表-初中水平-徐汇区-2022-2026.csv', encoding='utf-8-sig') as f:
        R = list(csv.DictReader(f))
    core = [r for r in R if r['years_included'] == '5']
    rest = [r for r in R if r['years_included'] != '5']
    return R, core, rest


def f(r, k):
    v = r.get(k, '')
    return float(v) if v not in ('', None) else None


def tercile_split(core):
    xs = sorted(f(r, 'quota_zone_avg') for r in core)
    n = len(xs)
    q1 = xs[n // 3]
    q2 = xs[2 * n // 3]
    small = [r for r in core if f(r, 'quota_zone_avg') <= q1]
    mid = [r for r in core if q1 < f(r, 'quota_zone_avg') <= q2]
    big = [r for r in core if f(r, 'quota_zone_avg') > q2]
    return (q1, q2), small, mid, big


def main():
    R, core, rest = load()
    print(f'宽表 {len(R)} 行；CORE {len(core)} 所；非 CORE {len(rest)} 所\n')

    print('=' * 78)
    print('A1 整体水平与稳定性（CORE，按 mean_rank_base4_avg 升序）')
    print('=' * 78)
    print(f'{"初中":<24}{"均名":>7}{"中位":>7}{"方差":>8}{"极差":>7}{"最好":>6}{"最差":>6}')
    for r in sorted(core, key=lambda r: f(r, 'mean_rank_base4_avg')):
        v = [f(r, f'mean_rank_base4_{y}') for y in YEARS]
        v = [x for x in v if x is not None]
        print(f'{r["junior_high_school"]:<24}{f(r,"mean_rank_base4_avg"):>7.2f}'
              f'{f(r,"mean_rank_base4_median"):>7.2f}{f(r,"mean_rank_base4_var"):>8.2f}'
              f'{max(v)-min(v):>7.1f}{min(v):>6.1f}{max(v):>6.1f}')

    print()
    print('=' * 78)
    print('A2 时间加权敏感性（线性 / 指数 vs 等权均值）')
    print('=' * 78)
    print(f'{"初中":<24}{"等权":>7}{"线性":>7}{"指数":>7}{"最大偏移":>9}{"方向":>6}')
    shifts = []
    for r in sorted(core, key=lambda r: f(r, 'mean_rank_base4_avg')):
        a = f(r, 'mean_rank_base4_avg')
        l = f(r, 'mean_rank_base4_w_linear')
        e = f(r, 'mean_rank_base4_w_exp')
        d = max(abs(l - a), abs(e - a))
        shifts.append((d, r['junior_high_school'], a, l, e))
        print(f'{r["junior_high_school"]:<24}{a:>7.2f}{l:>7.2f}{e:>7.2f}'
              f'{d:>9.2f}{"↑近强" if e < a else "↓近弱":>6}')
    shifts.sort(reverse=True)
    print(f'\n  最大偏移 top3: ' +
          '; '.join(f'{n} 偏移 {d:.2f}' for d, n, *_ in shifts[:3]))
    print(f'  偏移中位数 {st.median([s[0] for s in shifts]):.2f}，'
          f'偏移 >2 名的学校数 {sum(1 for s in shifts if s[0] > 2)}/{len(shifts)}')

    print()
    print('=' * 78)
    print('A3 规模分档（规模代理 = 区属市重年均总计划数）')
    print('=' * 78)
    (q1, q2), small, mid, big = tercile_split(core)
    print(f'  三分位阈值: 小/中 = {q1}，中/大 = {q2}    样本量 {len(core)}')
    for label, grp in (('小规模', small), ('中规模', mid), ('大规模', big)):
        print(f'\n  【{label}】{len(grp)} 所  区间 '
              f'[{min(f(r,"quota_zone_avg") for r in grp):.1f}, '
              f'{max(f(r,"quota_zone_avg") for r in grp):.1f}]')
        print(f'    {"初中":<24}{"年均计划":>9}{"全样本名次":>11}{"档内名次":>9}{"档内方差":>9}')
        for i, r in enumerate(sorted(grp, key=lambda r: f(r, 'mean_rank_base4_avg')), 1):
            overall = 1 + sum(1 for x in core
                              if f(x, 'mean_rank_base4_avg') < f(r, 'mean_rank_base4_avg'))
            print(f'    {r["junior_high_school"]:<24}{f(r,"quota_zone_avg"):>9.1f}'
                  f'{overall:>11}{i:>9}{f(r,"mean_rank_base4_var"):>9.2f}')

    print()
    print('=' * 78)
    print('A4-a 南模线 vs 区属均分 的分歧校')
    print('=' * 78)
    div = []
    for r in core:
        a = f(r, 'mean_rank_base4_avg')     # 区属均分名次（整体）
        n = f(r, 'nanmo_rank_avg')          # 南模线名次（头部代理）
        div.append((n - a, r['junior_high_school'], a, n))
    div.sort()
    print(f'{"初中":<24}{"区属均值":>9}{"南模线":>8}{"差(线-属)":>10}  解读')
    for d, name, a, n in div:
        tag = ('头部明显强于整体' if d <= -3 else
               '头部略强' if d < -1.5 else
               '整体明显强于头部' if d >= 3 else
               '整体略强' if d > 1.5 else '基本一致')
        print(f'{name:<24}{a:>9.2f}{n:>8.2f}{d:>10.2f}  {tag}')

    print()
    print('=' * 78)
    print('A4-b 口径稳健性：主口径(4校基线) vs 辅口径(当年全量区属)')
    print('=' * 78)
    topA = [r['junior_high_school'] for r in
            sorted(core, key=lambda r: f(r, 'mean_rank_base4_avg'))[:5]]
    botA = [r['junior_high_school'] for r in
            sorted(core, key=lambda r: f(r, 'mean_rank_base4_avg'))[-5:]]
    print('  主口径 Top5   :', topA)
    print('  主口径 Bottom5:', botA)
    print('\n  逐年 Top3 / Bottom3（主口径 vs 辅口径）：')
    for y in YEARS:
        def pick(key, rev=False):
            pool = [r for r in core if f(r, f'{key}_{y}') is not None]
            pool.sort(key=lambda r: f(r, f'{key}_{y}'), reverse=rev)
            return [r['junior_high_school'] for r in pool]
        t4, ta = pick('mean_rank_base4')[:3], pick('mean_rank_all')[:3]
        b4, ba = pick('mean_rank_base4')[-3:], pick('mean_rank_all')[-3:]
        print(f'   {y}  Top 主 {t4}  / 辅 {ta}    {"一致" if t4==ta else "★不一致"}')
        print(f'   {y}  Bot 主 {b4}  / 辅 {ba}    {"一致" if b4==ba else "★不一致"}')

    print()
    print('=' * 78)
    print('A4-c 样本进出（纳入年数不足 5 的学校）')
    print('=' * 78)
    for r in sorted(rest, key=lambda r: f(r, 'mean_rank_base4_avg') or 99):
        print(f'  {r["junior_high_school"]:<26} 纳入 {r["years_included"]} 年 '
              f'({r["years_list"]})  均值 {r["mean_rank_base4_avg"] or "—"}  '
              f'年均计划 {r["quota_zone_avg"]}')

    print()
    print('=' * 78)
    print('A4-d 年度样本量与规模')
    print('=' * 78)
    for r in sorted(core, key=lambda r: f(r, 'quota_zone_avg'), reverse=True)[:1]:
        pass
    for y in YEARS:
        qt = sum(f(r, f'quota_zone_total_{y}') or 0 for r in R)
        vp = [f(r, f'valid_pairs_{y}') for r in R]
        ns = sum(1 for r in R if f(r, f'mean_score_base4_{y}') is not None)
        print(f'  {y}: 区属总计划 {qt:>4.0f}（{len(R)} 校合计）；'
              f'有区属均分的学校 {ns} 所；有效 (校,高中) 对数合计 {sum(v for v in vp if v):.0f}')


if __name__ == '__main__':
    main()
