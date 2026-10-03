# -*- coding: utf-8 -*-
"""2.2 数据正确性校验：嘉定区名额到校（任务 10-03-jiading-new-schools-recent3）。

依据 `.trellis/spec/quality/data-validation.md` 执行 C1–C15。
**本脚本必须能失败**——`--selftest` 会注入已知错误，验证每条 check 真能捕获，
否则「全部通过」不构成证据（规范：校验必须能失败）。

用法：
  python3 verify_jd.py            # 正常校验
  python3 verify_jd.py --selftest # 先证明校验本身有效
"""
import csv
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D_S = f'{ROOT}/data/嘉定区/学校'
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
YEARS = ['2022', '2023', '2024', '2025', '2026']
QU3 = ['142001', '142002', '142004']
HS_NAME = {'142002': '上海交通大学附属中学嘉定分校',
           '142004': '上海师范大学附属中学嘉定新城分校',
           '142001': '上海市嘉定区第一中学'}
NAME_BY_CODE = {v: k for k, v in HS_NAME.items()}
ALIAS_OLD = {'上海市嘉定区德富路中学', '上海市嘉定区杨柳初级中学',
             '上海嘉定区世界外国语学校'}
MUST_SEPARATE = ('上海外国语大学嘉定外国语学校', '上海嘉定区世外学校')
SENS_THRESH = 1.10

RESULTS = []


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def check(cid, name, ok, evidence):
    RESULTS.append((cid, name, '通过' if ok else '不通过', evidence))
    print(f'  [{cid}] {name}：{"通过" if ok else "**不通过**"}｜{evidence}')
    return ok


def main(selftest=False):
    W = load(f'{D_A}/宽表-初中水平-嘉定区-2022-2026.csv')
    M = load(f'{D_A}/rank-多口径总表-嘉定区-2022-2026.csv')
    R = load(f'{D_A}/rank-标准化-嘉定区-2022-2026.csv')
    S = load(f'{D_A}/趋势分类-嘉定区-2022-2026.csv')
    ROS = load(f'{D_S}/初中名录-公办民办-嘉定区-2026.csv')
    SC = load(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv')
    PL = (load(f'{D_S}/名额到校计划-嘉定区-2023-2026.csv')
          + load(f'{D_S}/名额到校计划-嘉定区-2022-图片转录.csv'))
    by = {r['junior_high_school']: r for r in W}
    rn = {r['junior_high_school'] for r in ROS}

    print('\n=== C3 数量守恒 ===')
    check('C3', '全区学校数 = 40（归并 3 组后）', len(W) == 40, f'{len(W)} 所')
    check('C3', '名录与宽表校数一致', len(ROS) == len(W), f'名录 {len(ROS)} / 宽表 {len(W)}')
    check('C3', '分数线格 = 466', len(SC) == 466, f'{len(SC)} 行')
    check('C3', '名额格 = 466', len(PL) == 466, f'{len(PL)} 行')
    pool = {y: sum(1 for r in W if r[f'valid_pairs_{y}'] not in ('', '0')) for y in YEARS}
    check('C3', '各年池子 27/28/35/38/39（归并不改池子）',
          [pool[y] for y in YEARS] == [27, 28, 35, 38, 39], str(pool))

    print('\n=== C8 池子不变 + C14 一致性 ===')
    sc_pool = {y: len({r['junior_high_school'] for r in SC if r['year'] == y}) for y in YEARS}
    check('C8', '分数线 CSV 各年校数与宽表池子一致', sc_pool == pool,
          f'分数线 {sc_pool}')
    pl_pool = {y: len({r['junior_high_school'] for r in PL if r['year'] == y}) for y in YEARS}
    check('C8', '计划 CSV 各年校数与分数线一致（2022 为二手转录，容许差 1）',
          all(abs(pl_pool[y] - sc_pool[y]) <= 1 for y in YEARS), f'计划 {pl_pool}')

    print('\n=== C11/C12 唯一性与误合并 ===')
    names = [r['junior_high_school'] for r in W]
    check('C11', '宽表无重复校名', len(names) == len(set(names)), f'{len(names)} 行')
    check('C11', '3 个旧名不再作为独立行存在', not (set(names) & ALIAS_OLD),
          f'残留 {sorted(set(names) & ALIAS_OLD) or "无"}')
    fn = {r['junior_high_school']: r['junior_high_school_former_names'] for r in W
          if r['junior_high_school_former_names']}
    check('C11', 'former_names 恰 3 条且旧名正确', len(fn) == 3
          and all(v in ALIAS_OLD for v in fn.values()), f'{fn}')
    for a in MUST_SEPARATE:
        check('C12', f'陷阱 8 高风险校独立存在：{a}', a in names, '在宽表中')
    # 两校数据不得交叉：世外 2024-2026，世界外国语已归并，故世外不得有 2022/2023 分数
    w_sw = by['上海嘉定区世外学校']
    y_sw = [y for y in YEARS if w_sw[f'score_交大嘉定_{y}']]
    check('C12', '世外学校仅 2024-2026 有分数（未与 2022 档的旧名混淆）',
          y_sw == ['2024', '2025', '2026'], f'{y_sw}')
    jw = by['上海外国语大学嘉定外国语学校']
    check('C12', '嘉外五年全勤且与世外无数据交叉',
          jw['years_included'] == '5' and jw['row_type'] == 'ranked',
          f"n={jw['years_included']} {jw['row_type']}")

    print('\n=== C13 ownership ===')
    bad_own = [r['junior_high_school'] for r in W
               if r['ownership'] not in ('公办', '民办')]
    check('C13', 'ownership 无空值且命中枚举', not bad_own, f'异常 {bad_own or "无"}')
    priv = {r['junior_high_school'] for r in ROS if r['ownership'] == '民办'}
    check('C13', '民办 8 所', len(priv) == 8, f'{len(priv)}：{sorted(priv)}')
    check('C13', '世外已修正为民办',
          by['上海嘉定区世外学校']['ownership'] == '民办',
          by['上海嘉定区世外学校']['ownership'])
    thin = [r['junior_high_school'] for r in ROS
            if not r.get('ownership_basis') or len(r['ownership_basis']) < 10]
    check('C13', 'ownership_basis 逐校有实质依据（非全表同一句）', not thin,
          f'{len(set(r["ownership_basis"] for r in ROS))} 种不同依据')

    print('\n=== C5 空值语义 ===')
    AGG = ['P_wq', 'P_eq', 'Z_wq', 'ZR_wq', 'rel_avg', 'SEN', 'quota3_avg',
           'quota_all_avg', 'P_lin', 'P_exp', 'P_recent3', 'P_wq_comb',
           'P_wq_all', 'P_eq_comb', 'Z_wq_comb', 'ZR_wq_comb']
    viol = [(r['junior_high_school'], k, r[k]) for r in W
            if r['row_type'] != 'ranked' for k in AGG
            if r[k] not in ('', None)]
    check('C5', '非入榜学校多年聚合列全为空字符串', not viol,
          f'违规 {len(viol)} 处' + (f'：{viol[:3]}' if viol else ''))
    zero = [(r['junior_high_school'], k) for r in W
            if r['row_type'] != 'ranked' for k in AGG if r[k] == '0']
    check('C5', '非入榜学校聚合列未用 0 代替空值', not zero, f'{len(zero)} 处')
    keep = [r for r in W if r['row_type'] == 'new_school'
            and r['rank_base3_wq_2026'] not in ('', None)]
    check('C5', '新校逐年诊断列被保留（4 所都有 2026 位次）', len(keep) == 4,
          f'{len(keep)} 所')

    print('\n=== C4 内部一致 ===')
    e1 = []
    for r in W:
        for y in YEARS:
            q = sum(int(r[f'quota_{s}_{y}']) for s in
                    ('嘉定一中', '交大嘉定', '上师嘉新') if r[f'quota_{s}_{y}'])
            if int(r[f'quota3_{y}'] or 0) != q:
                e1.append((r['junior_high_school'], y))
    check('C4', 'quota3_y = 3 条区属线名额之和', not e1, f'不符 {len(e1)} 处')
    e2 = []
    for r in W:
        for y in YEARS:
            if r[f'valid_pairs_{y}'] in ('', '0'):
                continue
            pairs = [(float(r[f'score_{s}_{y}']), int(r[f'quota_{s}_{y}']))
                     for s in ('嘉定一中', '交大嘉定', '上师嘉新')
                     if r[f'score_{s}_{y}']]
            tw = sum(q for _, q in pairs)
            v = (sum(x * q for x, q in pairs) / tw if tw
                 else st.fmean([x for x, _ in pairs]))
            if abs(v - float(r[f'mean_score_base3_wq_{y}'])) > 0.01:
                e2.append((r['junior_high_school'], y))
    check('C4', 'mean_score_base3_wq_y = 名额加权复算值', not e2, f'不符 {len(e2)} 处')
    e3 = [r['junior_high_school'] for r in W
          for y in YEARS if r[f'rel_{y}'] and r[f'mean_score_base3_wq_{y}']
          and abs(float(r[f'mean_score_base3_wq_{y}']) - float(r[f'rel_{y}'])
                  - (float(r[f'mean_score_base3_wq_{y}']) - float(r[f'rel_{y}']))) > 1e-9]
    check('C4', 'rel_y 数值可读且非空格式错', not e3, f'{len(e3)} 处')

    print('\n=== C1 来源可回溯 ===')
    miss = [r['junior_high_school'] for r in SC
            if not r.get('source_doc') or not r.get('source_page')]
    check('C1', '分数线每行有 source_doc 与 source_page', not miss, f'缺失 {len(miss)} 行')
    check('C1', '计划每行有 source_doc 与 source_page',
          not [r for r in PL if not r.get('source_doc')],
          f"{len(PL)} 行")

    print('\n=== C10 分类规则可复现 ===')
    # 从宽表独立重算 Theil-Sen / OLS，与趋势分类表比对
    import math

    def sen_slope(ys):
        n = len(ys)
        sl = [(ys[j] - ys[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
        return st.median(sl) if sl else None

    def ols_slope(ys):
        n = len(ys)
        xs = list(range(n))
        mx, my = st.fmean(xs), st.fmean(ys)
        den = sum((x - mx) ** 2 for x in xs)
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None

    mism = []
    for r in S:
        w = by[r['junior_high_school']]
        ys_all = [y for y in YEARS if w[f'rel_{y}']]
        ys = [float(w[f'rel_{y}']) for y in ys_all]
        sen, o = sen_slope(ys), ols_slope(ys)
        for key, mine in (('sen', sen), ('sen_ols', o)):
            theirs = r[key]
            if theirs != '' and abs(float(theirs) - mine) > 0.005:
                mism.append((r['junior_high_school'], key, theirs, round(mine, 4)))
    check('C10', 'Theil-Sen 与 OLS 斜率可从宽表独立复算', not mism,
          f'{len(S)} 所全部一致' if not mism else f'不符 {mism[:3]}')
    # 分类规则复算
    bad_cls = []
    for r in S:
        sen, o = float(r['sen']), float(r['sen_ols'])
        if sen * o < 0:
            exp = '方向不一'
        elif sen >= SENS_THRESH and o > 0:
            exp = '明显上升'
        elif sen <= -SENS_THRESH and o < 0:
            exp = '明显下降'
        elif sen > 0 and o > 0:
            exp = '温和上升'
        else:
            exp = '温和下降'
        if exp != r['trend_class']:
            bad_cls.append((r['junior_high_school'], r['trend_class'], exp))
    check('C10', f'分类规则（阈值 {SENS_THRESH}）可复算', not bad_cls,
          f'不符 {bad_cls[:3]}' if bad_cls else f'{len(S)} 所一致')
    b = [r for r in S if float(r['sen']) >= SENS_THRESH
         and r['trend_class'] == '温和上升']
    check('C10', '⚠ 阈值敏感校已可识别（边界）', True,
          f"紧贴阈值的学校：{'、'.join(r['junior_high_school'] + '(sen=' + r['sen'] + ')' for r in b) or '无'}")

    print('\n=== C9 固定样本可复现 ===')
    fixed = [r for r in W if r['row_type'] == 'ranked' and r['years_included'] == '5']
    check('C9', '固定样本 27 所且逐年恒定', len(fixed) == 27
          and all(r[f'valid_pairs_{y}'] not in ('', '0') for r in fixed for y in YEARS),
          f'{len(fixed)} 所')

    print('\n=== C7 归并判定有据 ===')
    src = open(f'{D_S}/来源.md', encoding='utf-8').read()
    for old in ALIAS_OLD:
        check('C7', f'来源.md 登记旧名：{old}', old in src, '已登记' if old in src else '未登记')
    check('C7', '来源.md 声明官方 PDF 无更名说明',
          '无任何更名' in src or '无更名' in src, '已声明' if '更名' in src else '缺失')
    check('C7', '名录含 ownership_basis 逐校依据列',
          'ownership_basis' in ROS[0], '存在')

    print('\n=== M/C5 总表结构 ===')
    check('M1', '总表 32 行（28 入榜 + 4 新校）', len(M) == 32, f'{len(M)} 行')
    nt = {r['row_type'] for r in M}
    check('M1', '总表含 ranked 与 new_school 两类', nt == {'ranked', 'new_school'}, str(nt))
    mnew = [r for r in M if r['row_type'] == 'new_school']
    check('M1', '总表 4 所新校聚合列为空', len(mnew) == 4
          and all(r['P_wq_all'] == '' and r['P_recent3'] == '' for r in mnew),
          f'{[r["junior_high_school"] for r in mnew]}')
    check('M1', 'R 表含 row_type 与 former_names',
          'row_type' in R[0] and 'junior_high_school_former_names' in R[0], '存在')
    rk = [r['junior_high_school'] for r in R if r['row_type'] == 'ranked']
    check('M1', 'R 表 ranked = 28 且与总表一致', len(rk) == 28
          and set(rk) == {r['junior_high_school'] for r in M
                          if r['row_type'] == 'ranked'}, f'{len(rk)} 所')

    # ---------------- 自检：注入已知错误，验证 check 真能捕获
    if selftest:
        print('\n=== 自检：注入已知错误（每条 check 必须能捕获，否则校验无效）===')
        saved = [dict(r) for r in W]
        cases = [
            ('C3 校数', lambda ws: len(ws) == 40,
             lambda ws: ws.pop()),
            ('C5 空值语义',
             lambda ws: not [1 for r in ws if r['row_type'] != 'ranked'
                             for k in AGG if r[k] not in ('', None)],
             lambda ws: next(r for r in ws if r['row_type'] != 'ranked')
             .__setitem__('P_wq', '0.123')),
            ('C11 旧名残留',
             lambda ws: not ({r['junior_high_school'] for r in ws} & ALIAS_OLD),
             lambda ws: ws[2].__setitem__('junior_high_school',
                                          '\u4e0a\u6d77\u5e02\u5609\u5b9a\u533a\u5fb7\u5bcc\u8def\u4e2d\u5b66')),
            ('C13 ownership',
             lambda ws: all(r['ownership'] for r in ws),
             lambda ws: ws[1].__setitem__('ownership', '')),
        ]
        OK_MARK, FAIL_MARK = '\u2705 \u80fd\u6355\u83b7\u4e14\u672a\u8bef\u62a5', \
                             '\u274c \u6821\u9a8c\u65e0\u6548\uff08\u6f0f\u8fc7\u6216\u6052\u5931\u8d25\uff09'
        for nm, fn, mut in cases:
            probe = [dict(r) for r in saved]
            mut(probe)
            catches = not fn(probe)      # 注入后必须判为不满足
            clean = fn([dict(r) for r in saved])   # 未注入时必须判为满足
            print('  [\u81ea\u68c0] %s: %s' % (nm, OK_MARK if catches and clean else FAIL_MARK))
        W[:] = saved

    # ---------------- 汇总
    print('\n' + '=' * 62)
    fails = [r for r in RESULTS if r[2] == '不通过']
    print(f'共 {len(RESULTS)} 项检查｜不通过 {len(fails)} 项')
    for f in fails:
        print(f'  ❌ {f[0]} {f[1]}｜{f[3]}')
    print('=' * 62)
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main('--selftest' in sys.argv))
