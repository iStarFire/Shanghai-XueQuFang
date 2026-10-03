# -*- coding: utf-8 -*-
"""2.2 门禁校验脚本（trellis-check 独立实现，不复用 build_* 脚本的计算过程）。

用 pandas 读原始 CSV，自行重算 quota3 / mean_score_base3_wq / P_wq / SEN / 分类 /
收敛指标，与宽表、总表、新表逐格比对。
"""
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.environ.get('JD_ROOT') or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..'))
D_S = f'{ROOT}/data/嘉定区/学校'
D_A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
BASE = '/tmp/jdcheck/base'

YEARS = ['2022', '2023', '2024', '2025', '2026']
QU3 = ['142002', '142004', '142001']          # 区属 3 线
ALL8 = ['142002', '142004', '142001', '042032', '102056', '102057', '152003', '152006']
SHORT = {'142002': '交大嘉定', '142004': '上师嘉新', '142001': '嘉定一中',
         '042032': '上海中学', '102056': '交大本部', '102057': '复旦附中',
         '152003': '华师大二附', '152006': '上师大附中'}

ALIAS = {                                      # 旧名 -> 规范名
    '上海市嘉定区德富路中学': '交大附中附属嘉定德富中学',
    '上海市嘉定区杨柳初级中学': '上海市嘉定区嘉二实验学校',
    '上海嘉定区世界外国语学校': '上海嘉定区世外学校',
}
NEW4 = ['交大附中附属嘉定洪德中学', '同济大学附属嘉定实验中学',
        '上海师范大学附属第五嘉定实验学校', '上海市嘉定区嘉一实验初级中学']
MUST_SEPARATE = ('上海外国语大学嘉定外国语学校', '上海嘉定区世外学校')

RESULTS = []


def rep(check, ok, msg):
    RESULTS.append((check, bool(ok), msg))
    print(f'  [{"PASS" if ok else "FAIL"}] {check}: {msg}')


def canon(n):
    return ALIAS.get(n, n)


def rd(path):
    return pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)


def f(x):
    x = str(x).strip()
    return float(x) if x not in ('', 'nan', 'None') else None


SC = rd(f'{D_S}/名额到校最低分数线-嘉定区-2022-2026.csv')
PL = pd.concat([rd(f'{D_S}/名额到校计划-嘉定区-2022-图片转录.csv'),
                rd(f'{D_S}/名额到校计划-嘉定区-2023-2026.csv')], ignore_index=True)
ROSTER = rd(f'{D_S}/初中名录-公办民办-嘉定区-2026.csv')
RO = ROSTER.set_index('junior_high_school')
W = rd(f'{D_A}/宽表-初中水平-嘉定区-2022-2026.csv')
T = rd(f'{D_A}/rank-多口径总表-嘉定区-2022-2026.csv')
CLS = rd(f'{D_A}/趋势分类-嘉定区-2022-2026.csv')
CVG = rd(f'{D_A}/收敛指标-嘉定区-2022-2026.csv')
CVD = rd(f'{D_A}/收敛趋势检验-嘉定区-2022-2026.csv')
S2 = rd(f'{D_A}/rank-标准化-嘉定区-2022-2026.csv')
BW = rd(f'{BASE}/宽表-初中水平-嘉定区-2022-2026.csv')
bmap = {r['junior_high_school']: r for _, r in BW.iterrows()}
wmap = {r['junior_high_school']: r for _, r in W.iterrows()}

S, Q = {}, {}
for _, r in SC.iterrows():
    v = f(r['min_score'])
    if v is not None:
        S[(canon(r['junior_high_school']), r['senior_high_school_code'], int(r['year']))] = v
for _, r in PL.iterrows():
    Q[(canon(r['junior_high_school']), r['senior_high_school_code'], int(r['year']))] = \
        int(float(r['quota']))
schools = sorted({k[0] for k in S} | {k[0] for k in Q})


def wq_mean(c, y, codes=QU3):
    """区属线名额加权均分；无名额则退化为算术平均。返回 None 表示该年无数据。"""
    have = [cd for cd in codes if (c, cd, int(y)) in S]
    if not have:
        return None
    tw = sum(Q.get((c, cd, int(y)), 0) for cd in have)
    sc = [S[(c, cd, int(y))] for cd in have]
    return (sum(s * Q.get((c, cd, int(y)), 0) for s, cd in zip(sc, have)) / tw
            if tw > 0 else float(np.mean(sc)))


def main():
    print(f'=== 载入：分数线 {len(SC)} 行 / 计划 {len(PL)} 行 / 宽表 {len(W)} 行 / '
          f'名录 {len(ROSTER)} 行 ===')
    raw_names = ({r['junior_high_school'] for _, r in SC.iterrows()}
                 | {r['junior_high_school'] for _, r in PL.iterrows()})
    print(f'原始（未归并）校名 {len(raw_names)} → 归并后 {len(schools)}')

    # ================= C3 数量守恒 =================
    print('\n--- C3 数量守恒 ---')
    pool_n = {y: len({r['junior_high_school'] for _, r in SC.iterrows()
                      if r['year'] == y and f(r['min_score']) is not None}) for y in YEARS}
    expect = {'2022': 27, '2023': 28, '2024': 35, '2025': 38, '2026': 39}
    rep('C3a 逐年有分数学校数 27/28/35/38/39', pool_n == expect, f'{pool_n}')
    rep('C3b 归并后全区校数 = 40', len(schools) == 40, f'{len(schools)}')
    rep('C3c 名录行数 = 40', len(ROSTER) == 40, f'{len(ROSTER)}')
    rep('C3d 总表行数 = 32 = 28 入榜 + 4 新校', len(T) == 32,
        f'{len(T)} 行；row_type 分布 {T["row_type"].value_counts().to_dict()}')
    rep('C3e 分数线 CSV 行数 = 466（未变）', len(SC) == 466, f'{len(SC)}')
    rep('C3f 计划 CSV 行数 = 63+403 = 466（未变）', len(PL) == 466, f'{len(PL)}')
    rep('C3g 归并未丢格（S/Q 格数 = 原始）', len(S) == 466 and len(Q) == 466,
        f'S={len(S)} 格，Q={len(Q)} 格（466 = 有分数的分数线行数 / 计划行数）')
    # 逐年计划格数
    plan_n = {y: len({k[0] for k in Q if k[2] == int(y)}) for y in YEARS}
    score_n = {y: len({k[0] for k in S if k[2] == int(y)}) for y in YEARS}
    print(f'    [info] 逐年有分数校数 {score_n}｜逐年有名额校数 {plan_n}')

    # ================= C8 池子不变 =================
    print('\n--- C8 池子不变 ---')
    mp = {y: len([c for c in schools if wq_mean(c, y) is not None]) for y in YEARS}
    rep('C8 逐年参与分位/rel 计算的学校数 = 27/28/35/38/39', mp == expect, f'{mp}')
    # 归并未改变任何一年的「校名集合」以外的东西：比较归并前后每年 wq 均分向量（按规范名）
    ren_ok = True
    for y in YEARS:
        a = {canon(r['junior_high_school']): wq_mean(canon(r['junior_high_school']), y)
             for _, r in SC.iterrows()
             if r['year'] == y and r['senior_high_school_code'] in QU3}
        b = {c: wq_mean(c, y) for c in schools if wq_mean(c, y) is not None}
        if set(a) != set(b):
            ren_ok = False
    rep('C8b 归并前后「该校该年均分」集合一一对应', ren_ok,
        '2022 年旧名行的均分已挂到规范名，数值不变')

    # ================= C4 内部一致 =================
    print('\n--- C4 内部一致（独立重算）---')
    bad_q, bad_m, bad_vp = [], [], []
    for c in schools:
        r = wmap[c]
        for y in YEARS:
            q3 = sum(Q.get((c, cd, int(y)), 0) for cd in QU3)
            got = int(f(r[f'quota3_{y}']) or 0) if r[f'quota3_{y}'] != '' else 0
            if q3 != got:
                bad_q.append((c, y, q3, got))
            vp = len([cd for cd in QU3 if (c, cd, int(y)) in S])
            gv = int(f(r[f'valid_pairs_{y}']) or 0) if r[f'valid_pairs_{y}'] != '' else 0
            if vp != gv:
                bad_vp.append((c, y, vp, gv))
            wv = wq_mean(c, y)
            gm = f(r[f'mean_score_base3_wq_{y}'])
            if (wv is None) != (gm is None) or (wv is not None and abs(wv - gm) > 5e-4):
                bad_m.append((c, y, round(wv, 4) if wv else None, gm))
    rep('C4a quota3_y = 3 条区属线名额之和', not bad_q,
        f'{len(schools) * 5} 格比对，{len(bad_q)} 处不一致{bad_q[:3]}')
    rep('C4b mean_score_base3_wq_y = 名额加权复算', not bad_m,
        f'{len(bad_m)} 处不一致{bad_m[:3]}')
    rep('C4c valid_pairs_y = 该年有分数的区属线数', not bad_vp, f'{len(bad_vp)} 处{bad_vp[:3]}')
    # 逐年 score_/quota_ 逐格 vs 原始表
    bad_s = [(c, cd, y, wmap[c][f'score_{SHORT[cd]}_{y}'],
              '' if (c, cd, y) not in S else str(S[(c, cd, y)]))
             for c in schools for cd in ALL8 for y in YEARS
             if str(wmap[c][f'score_{SHORT[cd]}_{y}']).strip()
             != ('' if (c, cd, y) not in S else str(S[(c, cd, y)]))]
    bad_q2 = [(c, cd, y, wmap[c][f'quota_{SHORT[cd]}_{y}'],
               '' if (c, cd, y) not in Q else str(Q[(c, cd, y)]))
              for c in schools for cd in ALL8 for y in YEARS
              if str(wmap[c][f'quota_{SHORT[cd]}_{y}']).strip()
              != ('' if (c, cd, y) not in Q else str(Q[(c, cd, y)]))]
    rep('C4d 宽表 score_* 逐格 = 分数线原始表（1600 格）', not bad_s,
        f'{len(bad_s)} 处{bad_s[:3]}')
    rep('C4e 宽表 quota_* 逐格 = 计划原始表（1600 格）', not bad_q2,
        f'{len(bad_q2)} 处{bad_q2[:3]}')

    # ================= C5 空值语义 =================
    print('\n--- C5 空值语义 ---')
    AGG = ['quota3_avg', 'quota_all_avg', 'rel_avg', 'SEN', 'shift_wq_eq',
           'mean_rank_base3_wq_avg', 'mean_rank_base3_wq_median',
           'mean_rank_base3_wq_var', 'mean_rank_base3_eq_avg',
           'mean_rank_base3_w_linear', 'mean_rank_base3_w_exp',
           'P_wq', 'rank_P_wq', 'P_eq', 'rank_P_eq',
           'Z_wq', 'rank_Z_wq', 'ZR_wq', 'rank_ZR_wq',
           'Z_wq_comb', 'rank_Z_wq_comb', 'ZR_wq_comb', 'rank_ZR_wq_comb']
    for g in ('all', 'head', 'tail', 'comb'):
        AGG += [f'P_wq_{g}', f'rank_P_wq_{g}', f'P_eq_{g}', f'rank_P_eq_{g}']
    for k in ('lin', 'exp', 'recent3'):
        AGG += [f'P_{k}', f'rank_P_{k}']
    viol = [(r['junior_high_school'], r['row_type'], col, r[col])
            for _, r in W.iterrows() if r['row_type'] != 'ranked'
            for col in AGG if str(r[col]).strip() != '']
    rep('C5a row_type≠ranked 的多年聚合列全为空字符串', not viol,
        f'应空 {12 * len(AGG)} 格，实测 {len(viol)} 格非空')
    grp = {}
    for n, rt, col, v in viol:
        grp.setdefault((rt, col), []).append((n, v))
    for k_, v_ in sorted(grp.items()):
        print(f'    [越界] {k_[0]} × 列 `{k_[1]}`：{len(v_)} 所非空 → 例 {v_[0]}')
    zl = [(n, col) for n in wmap for col in AGG if wmap[n]['row_type'] != 'ranked'
          and str(wmap[n][col]).strip() in ('0', '0.0', 'nan', 'NaN', 'None')]
    rep('C5b 非入榜行的聚合列无 0/NaN 冒充空值', not zl, f'{len(zl)} 处{zl[:5]}')
    lost = [(c, y) for c in schools if wmap[c]['row_type'] != 'ranked'
            for y in YEARS if wmap[c][f'valid_pairs_{y}'] != '0'
            and wmap[c][f'mean_score_base3_wq_{y}'] == '']
    rep('C5c 非入榜行逐年诊断列保留（新校逐年均分/位次未被清空）', not lost,
        f'{len(lost)} 处缺失；例：' + str([(c, wmap[c]['mean_score_base3_wq_2026'])
                                         for c in NEW4]))
    nbad = [(n, col, wmap[n][col]) for n in NEW4 for col in AGG
            if str(wmap[n][col]).strip() != '']
    rep('C5d/A5 4 所新校聚合列全为空（A5）', not nbad, f'{len(nbad)} 处非空{nbad[:6]}')
    v2 = [(r['junior_high_school'], c) for _, r in S2.iterrows()
          for c in ('Z_eq', 'ZR_eq') if r['row_type'] != 'ranked' and str(r[c]).strip() != '']
    rep('C5e rank-标准化 的 Z_eq/ZR_eq 对非入榜行为空', not v2, f'{len(v2)} 处{v2[:3]}')
    tb = [(r['junior_high_school'], c) for _, r in T.iterrows()
          for c in AGG if c in T.columns and r['row_type'] != 'ranked'
          and str(r[c]).strip() != '']
    rep('C5f 总表 row_type=new_school 行的聚合列全为空', not tb, f'{len(tb)} 处{tb[:6]}')

    # ================= C6 无静默改数 =================
    print('\n--- C6 无静默改数（与 git HEAD 逐格 diff）---')
    REN = {v: k for k, v in ALIAS.items()}          # 旧名 -> 规范名
    RAW_COLS = [c for c in BW.columns
                if c.startswith('score_') or c.startswith('quota_')
                or c.startswith('mean_score_base3_') or c.startswith('rank_base3_')
                or c.startswith('valid_pairs_') or c.startswith('quota3_')
                or c.startswith('rel_')
                or (c.startswith(('P_eq_', 'P_wq_', 'Z_eq_', 'Z_wq_', 'ZR_eq_', 'ZR_wq_'))
                    and c[-5:-1].isdigit())]
    diffs = []
    for old, new in REN.items():
        b, n = bmap.get(old), wmap.get(new)
        if b is None or n is None:
            diffs.append(('MISSING', old, new, '', ''))
            continue
        for c in RAW_COLS:
            if str(b[c]).strip() != str(n[c]).strip():
                diffs.append((new, c, b[c], n[c]))
    rep('C6a 归并校逐年原始值迁移到规范名后逐格一致', not diffs,
        f'{len(RAW_COLS)} 列 × 3 组归并 = {len(RAW_COLS) * 3} 格；{len(diffs)} 处不一致'
        f'{diffs[:4]}')

    AGG_C = ([c for c in BW.columns if c in W.columns] - RAW_COLS
             - ['junior_high_school', 'junior_high_school_former_names',
                'junior_high_school_code', 'ownership', 'row_type', 'ranked',
                'years_included', 'years_list']
             - [c for c in BW.columns if c.startswith('rank_') or c.startswith('shift_')])
    vd, rd_ = [], []
    for name, n in wmap.items():
        if name in REN.values() or name not in bmap:
            continue
        b = bmap[name]
        for c in AGG_C:
            if str(b[c]).strip() != str(n[c]).strip():
                vd.append((name, c, b[c], n[c]))
        for c in BW.columns:
            if (c.startswith('rank_') or c.startswith('shift_')) and c in W.columns \
                    and str(b[c]).strip() != str(n[c]).strip():
                rd_.append((name, c, b[c], n[c]))
    rep('C6b/A4 除 3 组归并校外，其余行「多年聚合值列」与基线零差异', not vd,
        f'{len(AGG_C)} 列 × {len(wmap) - 3} 行；{len(vd)} 处差异{vd[:4]}')
    print(f'    [info] rank_*/shift_*（名次重排允许变）：{len(rd_)} 处 → 例 {rd_[:3]}')
    nr = [d for d in vd if wmap[d[0]]['row_type'] != 'ranked']
    rk = [d for d in vd if wmap[d[0]]['row_type'] == 'ranked']
    allblank = all(str(wmap[d[0]][d[1]]).strip() == '' for d in nr)
    rep('C6c 值列差异全部是「非入榜行被清空」（design 3.5 允许），入榜行零差异',
        len(nr) == len(vd) and allblank and not rk,
        f'共 {len(vd)} 处：非入榜行 {len(nr)} 处（均变为空：{allblank}）｜'
        f'入榜行 {len(rk)} 处{"：" + str(rk[:3]) if rk else ""}')
    rep('C6d 仅 3 个旧名行消失、无新增校',
        set(bmap) - set(wmap) == set(REN) and not (set(wmap) - set(bmap)),
        f'消失 {sorted(set(bmap) - set(wmap))}｜新增 {sorted(set(wmap) - set(bmap))}')
    # 其余 5 张表也逐格 diff
    print('    -- 其余 5 张产物表 vs git HEAD --')
    for fn, key in [('趋势分析-嘉定区-2022-2026.csv', 'junior_high_school'),
                    ('rank-标准化-嘉定区-2022-2026.csv', 'junior_high_school'),
                    ('rank-多口径总表-嘉定区-2022-2026.csv', 'junior_high_school'),
                    ('rank-加权敏感性-嘉定区-2022-2026.csv', 'junior_high_school'),
                    ('单线视角-嘉定区-2022-2026.csv', None)]:
        b0 = rd(f'{BASE}/{fn}')
        n0 = rd(f'{D_A}/{fn}')
        shared = [c for c in b0.columns if c in n0.columns]
        if key:
            bm = {canon(r[key]): r for _, r in b0.iterrows()}
            nm = {r[key]: r for _, r in n0.iterrows()}
            only_new = set(nm) - set(bm)
            only_old = set(bm) - set(nm)
            d = [(k_, c, bm[k_][c], nm[k_][c]) for k_ in nm if k_ in bm
                 for c in shared if str(bm[k_][c]).strip() != str(nm[k_][c]).strip()]
            print(f'      {fn}: {len(b0)}→{len(n0)} 行，{len(d)} 格差异，'
                  f'消失 {sorted(only_old)}，新增 {sorted(only_new)}'
                  f'{"" if not d else " → " + str(d[:3])}')
        else:
            bkey = ['junior_high_school', 'senior_high_school_code']
            bm = {(r[bkey[0]], r[bkey[1]]): r for _, r in b0.iterrows()}
            nm = {(r[bkey[0]], r[bkey[1]]): r for _, r in n0.iterrows()}
            d = [(k_, c, bm[k_][c], nm[k_][c]) for k_ in nm if k_ in bm
                 for c in shared if str(bm[k_][c]).strip() != str(nm[k_][c]).strip()]
            rep(f'C6e 单线视角 vs 基线零差异', not d,
                f'{len(nm)} 行 × {len(shared)} 列；{len(d)} 处差异{d[:3]}')

    # ================= A3 归并校 =================
    print('\n--- A3 归并校 P_wq（独立重算 vs CSV vs F3 预测）---')

    def p_val(y, codes=QU3):
        vals = {c: wq_mean(c, y, codes) for c in schools}
        vals = {k: v for k, v in vals.items() if v is not None}
        n = len(vals)
        out = {}
        for c, v in vals.items():
            b = sum(1 for w in vals.values() if w > v)
            e = sum(1 for w in vals.values() if w == v)
            out[c] = 1 - ((b + (e + 1) / 2) - 1) / (n - 1)
        return out

    py = {y: p_val(y) for y in YEARS}
    for tgt, exp_p in (('交大附中附属嘉定德富中学', 0.777),
                       ('上海市嘉定区嘉二实验学校', 0.247)):
        agg = float(np.mean([py[y][tgt] for y in YEARS]))
        got = f(wmap[tgt]['P_wq'])
        rep(f'A3 {tgt}', abs(agg - got) < 1e-5 and abs(got - exp_p) < 0.002,
            f'独立重算={agg:.6f}｜CSV={got}｜F3 预测={exp_p}｜'
            f'基线={bmap[tgt]["P_wq"]} rank {bmap[tgt]["rank_P_wq"]}→'
            f'{wmap[tgt]["rank_P_wq"]}')
    order_new = sorted([c for c in wmap if wmap[c]['rank_P_wq'] != ''],
                       key=lambda c: int(wmap[c]['rank_P_wq']))
    order_old = sorted([c for c in bmap if bmap[c]['rank_P_wq'] != ''],
                       key=lambda c: int(bmap[c]['rank_P_wq']))
    rep('A3b 第一梯队 5 所成员不变（仅次序变化）',
        set(order_new[:5]) == set(order_old[:5]),
        f'新前 5：{order_new[:5]}｜基线前 5：{order_old[:5]}')

    # ================= C11 唯一性 =================
    print('\n--- C11 唯一性 ---')
    rep('C11a 名录校名唯一', ROSTER['junior_high_school'].duplicated().sum() == 0,
        f'{len(ROSTER)} 行')
    rep('C11b 宽表校名唯一', W['junior_high_school'].duplicated().sum() == 0, f'{len(W)} 行')
    old_left = [n for n in ALIAS if n in set(wmap) | set(ROSTER['junior_high_school'])]
    rep('C11c 3 个旧名不再作为独立行存在', not old_left, f'{old_left}')
    fn = {r['junior_high_school']: r['junior_high_school_former_names']
          for _, r in ROSTER.iterrows() if r['junior_high_school_former_names']}
    rep('C11d former_names 非空恰好 3 条且方向正确', {canon(k): v for k, v in fn.items()} == ALIAS,
        f'{fn}')
    fw = {r['junior_high_school']: r['junior_high_school_former_names']
          for _, r in W.iterrows() if r['junior_high_school_former_names']}
    rep('C11e 宽表 former_names 与名录一致', fw == fn, f'{fw}')
    ft = {r['junior_high_school']: r['junior_high_school_former_names']
          for _, r in T.iterrows() if r['junior_high_school_former_names']}
    rep('C11f 总表 former_names 与名录一致', ft == fn, f'{ft}')
    # 显示名 = 最新年份写法：规范名应出现在最新有数据的年份
    for canon_n in ALIAS.values():
        ys = [y for y in YEARS if wmap[canon_n][f'valid_pairs_{y}'] != '0']
        hit = [y for y in YEARS if any(r['junior_high_school'] == canon_n
                                      for _, r in SC.iterrows() if r['year'] == y)]
        rep(f'C11g 显示名取最新年份写法：{canon_n}', bool(hit),
            f'分数线表用规范名的年份={hit}｜有数据年份={ys}')

    # ================= C12 误合并断言 =================
    print('\n--- C12 误合并断言（陷阱 8 高风险对）---')
    A, B = MUST_SEPARATE
    rep('C12a 两校均在宽表且为独立行', A in wmap and B in wmap,
        f'{A}: row_type={wmap[A]["row_type"]}/ownership={wmap[A]["ownership"]}/'
        f'years={wmap[A]["years_included"]}；'
        f'{B}: row_type={wmap[B]["row_type"]}/ownership={wmap[B]["ownership"]}/'
        f'years={wmap[B]["years_included"]}')
    rep('C12b 两校未被互相归并', ALIAS.get(A) != B and ALIAS.get(B) != A,
        f'ALIAS 不含「{A}→{B}」亦不含「{B}→{A}」')
    rep('C12c 两校逐年 rel 向量不同（非数据复制）',
        [wmap[A][f'rel_{y}'] for y in YEARS] != [wmap[B][f'rel_{y}'] for y in YEARS],
        f'{A}: {[wmap[A][f"rel_{y}"] for y in YEARS]}\n'
        f'              {B}: {[wmap[B][f"rel_{y}"] for y in YEARS]}')
    same = []
    for y in YEARS:
        va = [S[(A, cd, int(y))] for cd in ALL8 if (A, cd, int(y)) in S]
        vb = [S[(B, cd, int(y))] for cd in ALL8 if (B, cd, int(y)) in S]
        if va and vb and va == vb:
            same.append(y)
    rep('C12d 两校任一年 8 线分数向量不相同', not same, f'相同的年份：{same}')
    both = [y for y in YEARS if wq_mean(A, y) is not None and wq_mean(B, y) is not None]
    diff = [round(wq_mean(A, y) - wq_mean(B, y), 2) for y in both]
    rep('C12e 两校同时有数据的年份其区属 3 线均分明显不同', all(abs(d) > 1 for d in diff),
        f'{both} 年 A-B 差 {diff}')
    raw_rel = sorted({n for n in raw_names if '世外' in n or '外国语' in n})
    rep('C12f 原始分数线表含「世外/外国语」的校名恰为 3 个', len(raw_rel) == 3, f'{raw_rel}')
    # 名额结构（design 2.3 证据链 2）
    for nm, yrs in ((B, ['2024', '2025', '2026']),):
        s = {y: [Q.get((nm, cd, int(y)), 0) for cd in QU3] for y in yrs}
        print(f'    [证据链] {nm} 区属 3 线名额：' + '｜'.join(
            f'{y}={s[y]} (合计 {sum(s[y])})' for y in yrs))
    s_a = {y: [Q.get((A, cd, int(y)), 0) for cd in QU3] for y in YEARS}
    print(f'    [对照] {A} 区属 3 线名额：' + '｜'.join(
        f'{y}={s_a[y]}' for y in YEARS))

    # ================= C13 ownership =================
    print('\n--- C13 ownership 无空值 ---')
    empt = [c for c in wmap if str(wmap[c]['ownership']).strip() == '']
    rep('C13a 宽表 40 行 ownership 无空字符串', not empt, f'空值：{empt}')
    be = [c for c in wmap if wmap[c]['ownership'] not in ('公办', '民办', '待核实')]
    rep('C13b ownership 命中枚举 {公办,民办,待核实}', not be, f'{be}')
    rep('C13c 名录 ownership 无空且命中枚举',
        all(str(v).strip() in ('公办', '民办', '待核实') and str(v).strip() != ''
            for v in ROSTER['ownership']), f'{len(ROSTER)} 行')
    rep('C13d 上海嘉定区世外学校 ownership = 民办',
        wmap[B]['ownership'] == '民办' and RO.loc[B, 'ownership'] == '民办',
        f'宽表={wmap[B]["ownership"]}｜名录={RO.loc[B, "ownership"]}')
    priv = sorted([c for c in wmap if wmap[c]['row_type'] == 'excluded_private'])
    own_priv = sorted([c for c in wmap if wmap[c]['ownership'] == '民办'])
    rep('C13e excluded_private 集合 = ownership=民办 集合', priv == own_priv,
        f'{len(priv)} 所：{priv}')

    # ================= C14 =================
    print('\n--- C14 名录/宽表校数一致 ---')
    rep('C14a 名录 40 = 宽表 40', len(ROSTER) == len(W) == 40,
        f'名录 {len(ROSTER)}｜宽表 {len(W)}')
    rep('C14b 校名集合完全一致',
        set(ROSTER['junior_high_school']) == set(wmap),
        f'仅名录 {sorted(set(ROSTER["junior_high_school"]) - set(wmap))}｜'
        f'仅宽表 {sorted(set(wmap) - set(ROSTER["junior_high_school"]))}')
    om = [(n, RO.loc[n, 'ownership'], wmap[n]['ownership']) for n in wmap
          if RO.loc[n, 'ownership'] != wmap[n]['ownership']]
    rep('C14c ownership 逐校一致', not om, f'{om}')
    ym = [(n, RO.loc[n, 'years_included'], wmap[n]['years_included']) for n in wmap
          if RO.loc[n, 'years_included'] != wmap[n]['years_included']]
    rep('C14d years_included 逐校一致', not ym, f'{ym}')
    sm = [(n, RO.loc[n, 'score_years'].replace(';', ','), wmap[n]['years_list'])
          for n in wmap if RO.loc[n, 'score_years'] != wmap[n]['years_list']]
    rep('C14e 名录 score_years = 宽表 years_list', not sm, f'{sm[:3]}')
    n5 = sum(1 for n in wmap if wmap[n]['years_included'] == '5')
    rep('C14f 五年全勤 = 27 所（PRD R3 固定样本前提）', n5 == 27,
        f'{n5} 所；四年 1 所：'
        f'{[n for n in wmap if wmap[n]["years_included"] == "4"]}')

    # ================= C1 / C15 可追溯性 =================
    print('\n--- C1/C15 可追溯性 ---')
    for col in ['year', 'district', 'junior_high_school', 'senior_high_school',
                'min_score', 'source_doc', 'source_page']:
        ne = int((SC[col].astype(str).str.strip() == '').sum())
        rep(f'C1a 分数线.{col} 无空值', ne == 0, f'{ne}/{len(SC)}')
    for col in PL.columns:
        ne = int((PL[col].astype(str).str.strip() == '').sum())
        if ne:
            print(f'    [info] 计划表 {col} 空 {ne}/{len(PL)}')
    ce_s = int((SC['junior_high_school_code'].astype(str).str.strip() == '').sum())
    ce_p = int((PL['junior_high_school_code'].astype(str).str.strip() == '').sum())
    ce_w = int((W['junior_high_school_code'].astype(str).str.strip() == '').sum())
    rep('疑点1 宽表 junior_high_school_code 整列为空', ce_w == len(W),
        f'宽表 {ce_w}/{len(W)} 空；分数线 {ce_s}/{len(SC)} 空；计划 {ce_p}/{len(PL)} 空')
    reg = open(f'{D_S}/来源.md', encoding='utf-8').read()
    rep('疑点1b 「编号整列为空」限制已登记到 来源.md',
        'junior_high_school_code' in reg and '空' in reg,
        f'来源.md 含 junior_high_school_code：{"junior_high_school_code" in reg}')
    rep('疑点1c 陷阱 8「无编号可核」的替代证据链已登记',
        ('三重证据' in reg) or ('无编号' in reg) or ('编号' in reg and '无法' in reg),
        '来源.md 未见「三重证据链/无编号可核」说明')
    rep('C7a 3 组别名（6 个校名）已登记到 来源.md',
        all(k in reg for k in list(ALIAS) + list(ALIAS.values())),
        f'缺失 {[k for k in list(ALIAS) + list(ALIAS.values()) if k not in reg]}')
    rep('C7b 「官方 PDF 无更名声明」已记录', ('更名' in reg) or ('改名' in reg),
        f'来源.md 含「更名/改名」：{("更名" in reg) or ("改名" in reg)}')
    rep('来源.md 名录行数已由 44 所更新为 40 所', '40 所' in reg,
        f'来源.md 仍写「44 所」={"44 所" in reg}；含「40 所」={"40 所" in reg}')
    rep('来源.md 别名表待补事项已勾选', '[x] 建立各年共用的初中/高中名称别名表' in reg,
        f'[ ] 未勾选：{"[ ] 建立各年共用的初中/高中名称别名表" in reg}')
    rep('来源.md ownership 修正（世外 公办→民办）已登记', '民办' in reg,
        f'含「民办」：{"民办" in reg}（原表 line 42 仍写「办学性质为名称初判」）')
    # source_page 语义（陷阱 9）
    print('    -- source_page 值域（陷阱 9：不得为 PDF 对象号）--')
    reg_map = {'【嘉定】【2022】名额到校最低分数线.pdf': None,
               '【嘉定】【2023】名额到校最低分数线.pdf': None,
               '【嘉定】【2024】名额到校最低分数线.pdf': None,
               '【嘉定】【2025】名额到校最低分数线.pdf': None,
               '【嘉定】【2026】名额到校最低分数线.pdf': None}
    for fnm in reg_map:
        try:
            import fitz
            d = fitz.open(f'{D_S}/{fnm}')
            reg_map[fnm] = d.page_count
            d.close()
        except Exception as e:
            reg_map[fnm] = f'ERR {e}'
    for fnm, np_ in reg_map.items():
        sub = SC[SC['source_doc'] == fnm]
        if not len(sub):
            continue
        pages = sorted({int(v) for v in sub['source_page']})
        rep(f'C15a {fnm} source_page ≤ 实际页数({np_})',
            max(pages) <= (np_ if isinstance(np_, int) else 0),
            f'取值 {pages}｜实际 {np_} 页｜{len(sub)} 行')

    # ================= C9 固定样本 =================
    print('\n--- C9 固定样本可复现 ---')
    FIXED = sorted([c for c in wmap if wmap[c]['row_type'] == 'ranked'
                    and wmap[c]['years_included'] == '5'])
    rep('C9a 固定样本 = 28 入榜中五年全勤 = 27 所', len(FIXED) == 27,
        f'{len(FIXED)} 所；入榜 {int((W["row_type"] == "ranked").sum())} 所')
    med = {y: float(np.median([wq_mean(c, y) for c in schools
                               if wq_mean(c, y) is not None])) for y in YEARS}
    rel_bad = []
    for c in schools:
        for y in YEARS:
            v = wq_mean(c, y)
            g = f(wmap[c][f'rel_{y}'])
            if v is None:
                continue
            if g is None or abs((v - med[y]) - g) > 5e-4:
                rel_bad.append((c, y, round(v - med[y], 4), g))
    rep('C9b 40 所 × 5 年 rel 可从原始 CSV 独立复算', not rel_bad,
        f'{len(rel_bad)} 处不一致{rel_bad[:3]}')
    cv_bad = []
    for _, r in CVG.iterrows():
        y = r['year']
        xs = [wq_mean(c, y) for c in FIXED]
        if int(r['n_fixed']) != len(xs):
            cv_bad.append((y, 'n_fixed', len(xs), r['n_fixed']))
        pn = len([c for c in schools if wq_mean(c, y) is not None])
        if int(r['pool_n']) != pn:
            cv_bad.append((y, 'pool_n', pn, r['pool_n']))
        if abs(float(r['sigma']) - float(np.std(xs))) > 1e-5:
            cv_bad.append((y, 'sigma', round(float(np.std(xs)), 6), r['sigma']))
        if abs(float(r['pool_median']) - med[y]) > 1e-3:
            cv_bad.append((y, 'pool_median', round(med[y], 3), r['pool_median']))
        xs_sorted = sorted(xs)
        gini = sum((2 * i - len(xs) + 1) * v for i, v in enumerate(xs_sorted)) / \
            (len(xs) * sum(xs))
        if abs(float(r['gini']) - gini) > 1e-5:
            cv_bad.append((y, 'gini', round(gini, 6), r['gini']))
        q3 = len([1 for c in schools if wmap[c][f'valid_pairs_{y}'] != '0']) and \
            len([c for c in FIXED if wmap[c][f'valid_pairs_{y}'] != '0'])
        if int(r['outside_n']) != len([c for c in schools
                                       if c not in FIXED and wq_mean(c, y) is not None]):
            cv_bad.append((y, 'outside_n'))
    rep('C9c 收敛指标表 n_fixed/pool_n/sigma/pool_median/gini/outside_n 可独立复算',
        not cv_bad, f'{len(cv_bad)} 处{cv_bad[:4]}')
    rep('C9d 逐年 n_fixed 恒为 27', all(int(v) == 27 for v in CVG['n_fixed']),
        f'{list(CVG["n_fixed"])}')
    rep('C9e pool_n 逐年 = 27/28/35/38/39',
        [int(v) for v in CVG['pool_n']] == [27, 28, 35, 38, 39],
        f'{list(CVG["pool_n"])}')
    qq = CVD[CVD['metric'] == 'qq_slope']
    rep('C9f Q-Q 收敛斜率行存在且 n_obs=27',
        len(qq) == 1 and int(qq.iloc[0]['n_obs']) == 27,
        f'β={qq.iloc[0]["slope_b"] if len(qq) else None}｜n_obs='
        f'{qq.iloc[0]["n_obs"] if len(qq) else None}｜CI['
        f'{qq.iloc[0]["ci_lo"] if len(qq) else None},'
        f'{qq.iloc[0]["ci_hi"] if len(qq) else None}]')

    # ================= C10 分类规则 =================
    print('\n--- C10 分类规则可复现 ---')

    def theil_sen(xs, ys):
        sl = [(ys[j] - ys[i]) / (xs[j] - xs[i])
              for i in range(len(xs)) for j in range(i + 1, len(xs)) if xs[j] != xs[i]]
        return float(np.median(sl)) if sl else None

    def ols_slope(xs, ys):
        mx, my = float(np.mean(xs)), float(np.mean(ys))
        return float(sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
                     / sum((x - mx) ** 2 for x in xs))

    cls_bad, mk_bad = [], []
    m = len(CLS)
    for _, r in CLS.iterrows():
        n = r['junior_high_school']
        ys = [int(y) for y in YEARS if wmap[n][f'rel_{y}'] != '']
        rels = [f(wmap[n][f'rel_{y}']) for y in YEARS if wmap[n][f'rel_{y}'] != '']
        sen = theil_sen(ys, rels)
        so = ols_slope(list(range(len(rels))), rels)
        if abs(sen - f(r['sen'])) > 5e-4 or abs(so - f(r['sen_ols'])) > 5e-4:
            cls_bad.append((n, 'sen', round(sen, 4), r['sen'], round(so, 4), r['sen_ols']))
            continue
        Sv = sum((rels[j] > rels[i]) - (rels[j] < rels[i])
                 for i in range(len(rels)) for j in range(i + 1, len(rels)))
        if int(r['mk_S']) != Sv:
            mk_bad.append((n, 'mk_S', Sv, r['mk_S']))
        if abs(f(r['mk_p_bonferroni']) - min(1.0, f(r['mk_p']) * m)) > 5e-4:
            mk_bad.append((n, 'bonf'))
        if sen * so < 0:
            c_ = '方向不一'
        elif sen >= 1.10 and so > 0:
            c_ = '明显上升'
        elif sen <= -1.10 and so < 0:
            c_ = '明显下降'
        elif sen > 0 and so > 0:
            c_ = '温和上升'
        elif sen < 0 and so < 0:
            c_ = '温和下降'
        else:
            c_ = '无法判定'
        if c_ != r['trend_class']:
            cls_bad.append((n, 'class', c_, r['trend_class']))
        s3 = theil_sen([0, 1, 2], [f(wmap[n][f'rel_{y}']) for y in
                                    ['2024', '2025', '2026']
                                    if wmap[n][f'rel_{y}'] != '']) \
            if all(wmap[n][f'rel_{y}'] != '' for y in ['2024', '2025', '2026']) else None
        if s3 is not None and abs(s3 - f(r['sen_recent3'])) > 5e-4:
            mk_bad.append((n, 'sen_recent3', round(s3, 4), r['sen_recent3']))
    rep('C10a 28 所 sen / sen_ols / trend_class 可由宽表独立复算（阈值 1.10）',
        not cls_bad, f'{len(CLS)} 所 × 3 项；{len(cls_bad)} 处{cls_bad[:4]}')
    rep('C10b MK 的 S / Bonferroni p / sen_recent3 可复算', not mk_bad,
        f'{len(mk_bad)} 处{mk_bad[:4]}')
    rep('C10c 分类表行数 = 28', len(CLS) == 28, f'{len(CLS)} 行')
    rep('C10d 校正后无一显著（design 6.4 预注册结论）',
        all(r['sig_bonferroni'] == '否' for _, r in CLS.iterrows()),
        f'未校正 p<0.1：{int((CLS["sig_uncorrected"] == "是").sum())} 所｜'
        f'校正后：{int((CLS["sig_bonferroni"] == "是").sum())} 所')
    rep('C10e 4 所新校不进分类表', not [n for n in NEW4 if n in set(CLS['junior_high_school'])],
        f'分类表校名集合 = 宽表 row_type=ranked 集合：'
        f'{set(CLS["junior_high_school"]) == {c for c in wmap if wmap[c]["row_type"] == "ranked"}}')

    # ================= 疑点 2 ownership_basis =================
    print('\n--- 疑点 2 ownership_basis 是否逐校属实 ---')
    base_counts = ROSTER['ownership_basis'].value_counts()
    rep('疑点2 ownership_basis 已逐校差异化（非全表同一句）',
        len(base_counts) > 1 and base_counts.iloc[0] < len(ROSTER),
        f'{len(base_counts)} 种取值；最高频 {base_counts.iloc[0]} 次')
    print(f'    取值分布：{dict(base_counts)}')
    default_rows = [n for n in RO.index if RO.loc[n, 'ownership_basis'] ==
                    '嘉定区教育局官网「学校查询」页核实业办性质']
    print(f'    [info] 用默认依据（未单独核实）的 {len(default_rows)} 所：{default_rows}')
    ev = [n for n in RO.index if '官网' in RO.loc[n, 'ownership_basis']
          or '百科' in RO.loc[n, 'ownership_basis'] or '简章' in RO.loc[n, 'ownership_basis']
          or '名称含' in RO.loc[n, 'ownership_basis']]
    rep('疑点2b 每条 ownership_basis 均指明具体依据页面/来源', len(ev) == len(ROSTER),
        f'{len(ev)}/{len(ROSTER)} 条带具体依据；无依据：'
        f'{[n for n in RO.index if n not in ev]}')

    # ================= 疑点 3 民办 =================
    print('\n--- 疑点 3 民办校「新办」措辞 ---')
    rpt = open(f'{D_A}/分析报告.md', encoding='utf-8').read()
    bad = []
    for n in priv:
        for mm in re.finditer(re.escape(n), rpt):
            seg = rpt[max(0, mm.start() - 150):mm.end() + 150]
            if '新办' in seg and '非新办' not in seg and '并非新办' not in seg:
                bad.append((n, seg.replace('\n', ' ')[:220]))
    rep('疑点3 报告全文未把民办校表述为「新办」', not bad,
        f'{len(priv)} 所民办 × 全文检索；命中 {len(bad)} 处{bad[:1]}')
    nw = [(n, RO.loc[n, 'ownership_basis']) for n in priv
          if '新办' in RO.loc[n, 'ownership_basis']
          and '非新办' not in RO.loc[n, 'ownership_basis']]
    rep('疑点3b 名录中民办校 ownership_basis 未称「新办」', not nw, f'{nw}')
    # 新校类别命名：4 所新校确为新办（2021–2022 创办）
    print(f'    [info] 民办 {len(priv)} 所：{priv}')

    nfail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f'\n=== 汇总：{len(RESULTS)} 项检查，通过 {len(RESULTS) - nfail}，失败 {nfail} ===')
    for check, ok, msg in RESULTS:
        if not ok:
            print(f'  [FAIL] {check}: {msg}')
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main())
