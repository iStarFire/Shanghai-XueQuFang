"""独立复算校验宽表（S6 验收）。

刻意不复用 build_wide.py 的任何函数，直接从两份长表重新实现一遍算法，
以「两份独立实现结果一致」作为正确性证据。

⛔⛔⛔ 旧管线脚本，已退役 ⛔⛔⛔
本脚本属于**旧方法管线**（`build_wide.py` / `build_trend.py`），校验的是旧宽表列名
（`BASE4` 四条基线线、`quota_zone_total_*`、`mean_score_base4_*` 等）。

阶段 1 起数据层已按**分位主口径**重建（基线线 `QU6` 六条，实际参与 4/5/5/5/6 条，
派生列名随之全改），本脚本的预期列名**不再存在**。

· 新管线的门禁是 `verify_wide_xh.py` / `verify_tables_xh.py` /
  `verify_conclusion_xh.py` / `verify_vs_baseline_xh.py`
· 旧管线保留仅为「与阶段 0 归并前基线做同源比对」提供参照，见
  `verify_vs_baseline_xh.py`
· 需要重跑旧管线请先运行 `build_wide.py`（会覆盖当前宽表，**务必先备份**）

保留本文件仅为对照历史实现，不作为门禁。
"""
import pathlib
import csv, statistics as st, random, sys

ROOT = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{ROOT}/data/徐汇区/学校"
OUT = f"{ROOT}/analysis/徐汇区公办初中名额分配到校分析"
# ---- 旧管线适用性检查：预期列名不存在就明确退出，而不是抛 KeyError ----
_w = pathlib.Path(__file__).resolve().parents[1] / '宽表-初中水平-徐汇区-2022-2026.csv'
if _w.exists() and 'quota_zone_total_2022' not in _w.open(encoding='utf-8-sig').readline():
    print(__doc__)
    raise SystemExit(2)

YEARS = [2022, 2023, 2024, 2025, 2026]
BASE4 = ['042001', '042008', '042035', '043015']
ZONE = {2022: ['042001', '042008', '042035', '043015'],
        2023: ['042001', '042008', '042035', '043015', '042036'],
        2024: ['042001', '042008', '042035', '043015', '042036'],
        2025: ['042001', '042008', '042035', '043015', '042036'],
        2026: ['042001', '042002', '042008', '042035', '042036', '043015']}
ZONE_COLS = ['042008', '042035', '042001', '042002', '043015', '042036']
MINBAN = {'041363', '041385', '044162', '044164', '044181', '044182'}


def rd(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def main():
    plan = rd(f'{D}/名额到校计划-徐汇区-2022-2026.csv')
    score = rd(f'{D}/名额到校最低分数线-徐汇区-2022-2026.csv')
    wide = rd(f'{OUT}/宽表-初中水平-徐汇区-2022-2026.csv')
    fails = []

    # --- 1. 列序 ---
    exp = ['junior_high_school', 'junior_high_school_code',
           'junior_high_school_former_names', 'ownership',
           'years_included', 'years_list', 'quota_zone_avg',
           'mean_rank_base4_avg', 'mean_rank_base4_median', 'mean_rank_base4_var',
           'nanmo_rank_avg', 'nanmo_rank_median', 'nanmo_rank_var',
           'mean_rank_base4_w_linear', 'mean_rank_base4_w_exp',
           'nanmo_rank_w_linear', 'nanmo_rank_w_exp']
    for y in [2026, 2025, 2024, 2023, 2022]:
        exp += [f'plan_{c}_{y}' for c in ZONE_COLS]
        exp += [f'score_{c}_{y}' for c in ZONE_COLS]
        exp += [f'quota_zone_total_{y}', f'valid_pairs_{y}',
                f'mean_score_base4_{y}', f'mean_rank_base4_{y}',
                f'mean_score_all_{y}', f'mean_rank_all_{y}',
                f'nanmo_score_{y}', f'nanmo_rank_{y}']
    got = list(wide[0].keys())
    print(f'[1] 列数 {len(got)}（期望 {len(exp)}）列序一致: {got == exp}')
    if got != exp:
        for i, (a, b) in enumerate(zip(got, exp)):
            if a != b:
                print(f'    首个不同 @{i}: 实际 {a} / 期望 {b}')
                break
        fails.append('列序')

    # --- 2. 只含公办、无重复 ---
    codes = [r['junior_high_school_code'] for r in wide]
    print(f'[2] 行数 {len(wide)}，编号唯一 {len(set(codes)) == len(codes)}，'
          f'含民办 {sorted(set(codes) & MINBAN)}，'
          f'ownership 取值 {set(r["ownership"] for r in wide)}')
    if set(codes) & MINBAN or len(set(codes)) != len(codes):
        fails.append('民办/重复')

    # --- 3. 委属不得出现在宽表 ---
    weishu = [c for c in got if any(c.endswith('_' + h) for h in
                                    ['042032', '102056', '102057', '152003', '152006'])]
    print(f'[3] 宽表中委属列: {weishu}')
    if weishu:
        fails.append('委属列泄漏')

    # --- 4. quota_zone_total 与长表逐校加总一致 ---
    q = {}
    for r in plan:
        if r['senior_high_school_code'] in ZONE[int(r['year'])]:
            q[(r['junior_high_school_code'], int(r['year']))] = \
                q.get((r['junior_high_school_code'], int(r['year'])), 0) \
                + int(r['quota_plan'] or 0)
    bad_q = [(r['junior_high_school_code'], y) for r in wide for y in YEARS
             if int(r[f'quota_zone_total_{y}'] or 0) != q.get((r['junior_high_school_code'], y), 0)]
    print(f'[4] quota_zone_total 与长表不符的格数: {len(bad_q)} {bad_q[:5]}')
    if bad_q:
        fails.append('quota_zone_total')

    # --- 5. mean_score_base4 / mean_score_all 独立重算 ---
    sv = {}
    for r in score:
        sv[(r['junior_high_school_code'], int(r['year']),
            r['senior_high_school_code'])] = float(r['min_score'])
    bad_b = bad_a = 0
    for r in wide:
        c = r['junior_high_school_code']
        for y in YEARS:
            e4 = [sv[(c, y, h)] for h in BASE4 if (c, y, h) in sv]
            ea = [sv[(c, y, h)] for h in ZONE[y] if (c, y, h) in sv]
            got4 = r[f'mean_score_base4_{y}']
            gota = r[f'mean_score_all_{y}']
            if (round(sum(e4) / len(e4), 3) if e4 else None) != (float(got4) if got4 else None):
                bad_b += 1
            if (round(sum(ea) / len(ea), 3) if ea else None) != (float(gota) if gota else None):
                bad_a += 1
    print(f'[5] mean_score_base4 不符 {bad_b} 格；mean_score_all 不符 {bad_a} 格')
    if bad_b or bad_a:
        fails.append('均分重算')

    # --- 6. 排名独立重算 ---
    bad_r = 0
    for y in YEARS:
        for src, dst in (('mean_score_base4', 'mean_rank_base4'),
                         ('mean_score_all', 'mean_rank_all'),
                         ('nanmo_score', 'nanmo_rank')):
            pool = []
            for r in wide:
                v = r[f'{src}_{y}']
                if v:
                    pool.append(float(v))
            for r in wide:
                v = r[f'{src}_{y}']
                if not v:
                    continue
                v = float(v)
                want = 1 + sum(1 for x in pool if x > v) + \
                    (sum(1 for x in pool if x == v) - 1) / 2
                if abs(want - float(r[f'{dst}_{y}'])) > 1e-9:
                    bad_r += 1
    print(f'[6] 排名不符格数: {bad_r}')
    if bad_r:
        fails.append('排名')

    # --- 7. 回源抽查 10 格 ---
    random.seed(20260930)
    picks = []
    while len(picks) < 10:
        r = random.choice(wide)
        y = random.choice(YEARS)
        h = random.choice(ZONE_COLS)
        if r[f'plan_{h}_{y}'] or r[f'score_{h}_{y}']:
            picks.append((r['junior_high_school_code'], y, h))
    picks = list(dict.fromkeys(picks))[:10]
    srcmap = {(r['junior_high_school_code'], int(r['year']), r['senior_high_school_code']): r
              for r in score}
    srcmap_p = {(r['junior_high_school_code'], int(r['year']), r['senior_high_school_code']): r
                for r in plan}
    print('[7] 抽 10 格回源：')
    for c, y, h in picks:
        sp = srcmap.get((c, y, h)); pp = srcmap_p.get((c, y, h))
        wr = next(r for r in wide if r['junior_high_school_code'] == c)
        print(f'    {(c, y, h)}  计划={wr[f"plan_{h}_{y}"]:>3}'
              f'(源 {pp["quota_plan"] if pp else "-"}'
              f' {pp["source_doc"][-16:] if pp else "-"}'
              f' p{pp["source_page"] if pp else "-"})'
              f'  分数={wr[f"score_{h}_{y}"]:>6}'
              f'(源 {sp["min_score"] if sp else "-"}'
              f' {sp["source_doc"][-16:] if sp else "-"}'
              f' p{sp["source_page"] if sp else "-"})')

    # --- 8. 汇总统计量复算 ---
    bad_s = 0
    for r in wide:
        rb = [float(r[f'mean_rank_base4_{y}']) for y in YEARS
              if r[f'mean_rank_base4_{y}']]
        if not rb:
            continue
        if abs(st.mean(rb) - float(r['mean_rank_base4_avg'])) > 1e-3: bad_s += 1
        if abs(st.median(rb) - float(r['mean_rank_base4_median'])) > 1e-3: bad_s += 1
        if abs(st.pvariance(rb) - float(r['mean_rank_base4_var'])) > 1e-3: bad_s += 1
    print(f'[8] 汇总均值/中位数/方差不符的学校数: {bad_s}')
    if bad_s:
        fails.append('汇总统计')

    # --- 9. 校名：显示名必须是最新年份的写法，旧名进 former_names ---
    #     独立从长表重算，用于防止「改名学校被显示成旧名」而读者误判为两所学校
    nm = {}
    for r in plan + score:
        nm.setdefault(r['junior_high_school_code'], {})[
            int(r['year'])] = r['junior_high_school']
    bad_n = []
    for r in wide:
        c = r['junior_high_school_code']
        m = nm.get(c, {})
        want = m.get(max(m)) if m else None
        old = (';'.join(sorted({n for n in m.values() if n != want}))
               if m else '')
        if (r['junior_high_school'] != want
                or r['junior_high_school_former_names'] != old):
            bad_n.append((c, r['junior_high_school'], want,
                          r['junior_high_school_former_names'], old))
    renamed = [(r['junior_high_school_code'], r['junior_high_school'],
                r['junior_high_school_former_names'])
               for r in wide if r['junior_high_school_former_names']]
    print(f'[9] 校名/曾用名不符的行数: {len(bad_n)}；用到过旧名的学校 '
          f'{len(renamed)} 所')
    for code, cur, old in renamed:
        print(f'      {code}  「{cur}」 ← 原用名「{old}」')
    for x in bad_n[:5]:
        print('      ✗', x)
    if bad_n:
        fails.append('校名/曾用名')

    print()
    print('门禁：', '✅ 全部通过' if not fails else f'❌ 未通过 {fails}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
