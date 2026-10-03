#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦区名额到校最低分数线 PDF 抽取器（版面自适应）。

修正旧抽取器的两个错误假设：
1. 同行桶假设：PDF 中名称垂直居中、分数贴基线，两者 y 差约 3px，
   要求「同一 y 桶」会随机丢掉约一半记录。改为「同页最近 y 配对」。
2. 固定列边界假设：5 年 PDF 版式不同，2024 起招生学校名落入 x<110 区域。
   改为逐年从表头锚点探测列边界。

用法：
  python3 extract_score_hp.py --probe          # 步骤 1：版面探测
  python3 extract_score_hp.py --year 2023      # 抽取单年并打印前若干条
  python3 extract_score_hp.py --all --write    # 重建 CSV
  python3 extract_score_hp.py --all --report   # 与旧 CSV 对账（不写盘）
"""
import argparse
import csv
import os
import re
import statistics as st
import sys
from collections import Counter

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/黄浦区/学校'
YEARS = ['2022', '2023', '2024', '2025', '2026']
NUM = re.compile(r'^\d+(\.\d+)?$')

# 样板文字：标题 / 水印 / 表头 / 注，允许出现在「未匹配残留」里
BOILER = [
    '上海市高中学校“名额分配到校”招生录取最低分数线', '名额分配到校', '黄浦区',
    '招生录取最低分数线', '注：', '录取最低分均含综合考查成绩', '下表录取最低分中均含综合考查成绩',
    '综合考查成绩', '满分为50分', '综合素质评价成绩均为50分', '均为50分',
    '初中学校', '招生学校', '语数外', '数学', '语文', '综合测试', '是否同', '分优待',
    '末位录取考生成绩', '含学业考总成绩', '和综合考查成绩', '（含学业考总成绩',
]
WATERMARK = ['上海市教育考试院', '市教育考试院', '教育考试院', '考试院', '育考试院']


def is_num(t):
    return bool(NUM.match(t))


def load_rows(pdf):
    """按 round(y/3) 分桶；桶只用于收集同一物理行的词，不用于判断是否同一记录。"""
    doc = fitz.open(pdf)
    pages = []
    for p in doc:
        buckets = {}
        for w in p.get_text('words'):
            buckets.setdefault(round(w[1] / 3), []).append(w)
        rows = [(k * 3, [(round(w[0]), w[4]) for w in sorted(buckets[k], key=lambda w: w[0])])
                for k in sorted(buckets)]
        pages.append(rows)
    doc.close()
    return pages


def probe_layout(pdf):
    """探测列边界：优先用表头锚点，缺失时用数值 x 聚类兜底。"""
    pages = load_rows(pdf)
    anchors = {}
    for rows in pages[:1]:
        for y, cells in rows:
            for x, t in cells:
                for key, needle in (('junior', '初中学校'), ('senior', '招生学校'),
                                    ('min', '录取最低分'), ('tie', '是否同'), ('tie2', '分优待')):
                    if t == needle and key not in anchors:
                        anchors[key] = (x, y)
                # 2022 的四个科目表头合并成一个文本串「语数外数学语文综合测试」
                if '语数外' in t and 'subjects_merged' not in anchors:
                    anchors['subjects_merged'] = (x, y)
    # 数值 x 聚类（只用数据区：y > 表头 y）
    hdr_y = max((v[1] for v in anchors.values()), default=0)
    xs = [x for rows in pages for y, cells in rows if y > hdr_y + 12
          for x, t in cells if is_num(t)]
    cl = Counter(round(x / 10) * 10 for x in xs)
    # 取 5 个最大的簇（录取最低分 + 4 科目）；排除零星簇
    top = [c for c, n in sorted(cl.items(), key=lambda kv: -kv[1])[:6] if n >= 8]
    return {'pages': len(pages), 'anchors': anchors, 'hdr_y': hdr_y,
            'num_clusters': sorted(top), 'cluster_n': {c: cl[c] for c in sorted(top)}}


def detect_score_cols(pdf):
    """探测分数列的 x 中心与**字段角色**。

    列角色按**取值特征**判定，不靠表头文字（2022 的科目表头合并成一串
    「语数外数学语文综合测试」，2025/2026 的表头被水印遮挡无法逐个定位），
    也不能靠「取最大的 5 簇」——2025/2026 有 6 列（多一个「综合素质评价」），
    取 5 簇会把它当成语数外，导致后面科目列右移一位且「综合测试」整列丢失。
    """
    pages = load_rows(pdf)
    # 只取数据区（排除表头与页眉），否则杂值会污染「恒为 50」的判定
    hdr = 0
    for rows in pages[:1]:
        for y, cells in rows:
            for _, t in cells:
                if t in ('初中学校', '招生学校', '录取最低分'):
                    hdr = max(hdr, y)
    pts = [(x, float(t)) for rows in pages for y, cells in rows
           for x, t in cells if is_num(t) and y > hdr + 15]
    cl = Counter(round(x / 6) * 6 for x, _ in pts)
    # 合并相邻簇（同一列的数字可能落在 6px 内不同起点，如 2024 语数外 432/438）；
    # 合并后取**计数最多**的子簇作中心（取 min 会把 2025 的 552 拉到 546）
    groups = []
    for c in sorted(cl):
        if groups and c - groups[-1][-1][0] <= 8:
            groups[-1].append((c, cl[c]))
        else:
            groups.append([(c, cl[c])])
    groups = [g for g in groups if sum(n for _, n in g) >= 20]
    if len(groups) < 5:
        raise SystemExit(f'分数列聚类只有 {len(groups)} 个，版面未识别')
    cols, roles = _assign_roles(groups, pts)
    return cols, pages, roles


def _center(g):
    return max(g, key=lambda z: z[1])[0]


def _assign_roles(groups, pts):
    """按取值特征分配列角色，返回 (cols, roles)。

    规则（自洽且可校验）：
      - 最左列 = 录取最低分（取值 650–770，远高于其他列）
      - 恒为 50 的列 = 综合素质评价（2025/2026 专有；2022/2023 无此列，
        2024 官方在注中写明「均为 50 分」但无该列）
      - 剩余 4 列按 x 升序 = 语数外、数学、语文、综合测试
    """
    cols = [_center(g) for g in groups]
    vals = []
    for g in groups:
        keys = {cc for cc, _ in g}
        vals.append([v for x, v in pts if round(x / 6) * 6 in keys])
    roles = [None] * len(cols)
    roles[0] = 'min_score'
    rest = list(range(1, len(cols)))
    for i in rest:
        v = vals[i]
        if v and max(v) == min(v) == 50:
            roles[i] = 's综合评价'
            rest.remove(i)
            break
    if len(rest) != 4:
        raise SystemExit(f'剔除综合素质评价后剩 {len(rest)} 个科目列（应为 4）：{cols}')
    for i, r in zip(rest, ['yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive']):
        roles[i] = r
    return cols, roles


def extract_year(year, pool, senior_pool):
    pdf = f'{D}/【黄浦】【{year}】名额到校最低分数线.pdf'
    cols, pages, roles = detect_score_cols(pdf)
    anchors = probe_layout(pdf)['anchors']
    x_score = cols[0]
    # 列归属：容差取相邻列最小间距的一半（减 1 防边界命中两列）
    # 固定 ±16 会在 2025/2026（列距 30px）产生重叠区，把数字判给相邻列
    gap = min(b - a for a, b in zip(cols, cols[1:]))
    tol = max(4, gap // 2 - 1)
    tie_x = anchors.get('tie', anchors.get('tie2', (None, None)))[0]
    ROLE = {r: i for i, r in enumerate(roles) if r}

    def which(x):
        for i, c in enumerate(cols):
            if abs(x - c) <= tol:
                return i
        return None
    recs = []
    for pi, rows in enumerate(pages):
        for y, cells in rows:
            vals = {}
            for x, t in cells:
                if is_num(t):
                    k = which(x)
                    if k is not None:
                        vals[k] = t
            if len(vals) == len(roles):
                tie = ''
                if tie_x is not None:
                    tie = next((t for x, t in cells
                                if abs(x - tie_x) <= 24 and t in ('否', '是')), '')
                # 按**角色**取值，不按列序：2025/2026 是 6 列布局，列序 ≠ 字段序
                recs.append({'pg': pi + 1, 'y': y, 'tie': tie,
                             'nums': [vals[i] for i in range(len(roles))],
                             'min_score': vals[ROLE['min_score']],
                             's综合评价': vals[ROLE['s综合评价']] if 's综合评价' in ROLE else '',
                             'yw_sx': vals[ROLE['yw_sx']],
                             'yw_math': vals[ROLE['yw_math']],
                             'yw_chinese': vals[ROLE['yw_chinese']],
                             'yw_comprehensive': vals[ROLE['yw_comprehensive']]})
    recs.sort(key=lambda r: (r['pg'], r['y']))
    # 名称配对：按**内容**匹配，不按 x 分割。
    # 原因：长高中名（如「上海市格致中学（奉贤校区）」14 字 ≈ 155px 宽）会左移到
    # x≈85 < x_mid，任何基于 x 的初中/高中列分割都会把它误判进初中列。
    all_names = sorted(set(pool) | set(senior_pool), key=len, reverse=True)
    jp_set, sp_set = set(pool), set(senior_pool)
    n_j = n_s = 0
    for r in recs:
        # 名称配对：按**内容**匹配，不按 x 分割。
        # 原因：长高中名（如「上海市格致中学（奉贤校区）」14 字 ≈ 155px 宽）会左移到
        # x≈85，任何固定 x 边界都会把它误判进初中列。
        #
        # 也不能把窗口内片段按 (y,x) 直接拼成一个串：换行的 2 行初中名会被
        # 中间的高中名隔开，变成不连续串而匹配不到。
        #   y768: 上海外国语大学附属大境初级
        #   y774: 上海市格致中学          ← 高中名夹在中间
        #   y777: 中学                    ← 初中名第二行
        # 故先按 **x 起点的最大间隙**把片段分成两组（初中组 / 高中组），
        # 再在**组内按 y 顺序**拼接，最后分别对两个名字池做最长匹配。
        frags = []
        for ry, cells in pages[r['pg'] - 1]:
            if abs(ry - r['y']) <= 10:
                for x, t in cells:
                    if (not is_num(t) and t not in ('否', '是')
                            and t not in WATERMARK and x < x_score):
                        frags.append((x, ry, t))
        groups = _split_by_x_gap(frags)
        j = s = None
        for grp in groups:
            txt = ''.join(t for _, _, t in sorted(grp, key=lambda z: z[1]))
            i = 0
            while i < len(txt):
                m = next((nm for nm in all_names if txt.startswith(nm, i)), None)
                if m is None:
                    i += 1
                    continue
                if m in jp_set and j is None:
                    j = m
                elif m in sp_set and s is None:
                    s = m
                i += len(m)
        r['junior'], r['senior'] = j, s
        # 更名 / 并入归一：保留原名到 junior_raw，便于写入 note 追溯
        r['junior_raw'] = j
        if j in JUNIOR_RENAMES:
            r['junior'] = JUNIOR_RENAMES[j]
        elif j in JUNIOR_MERGED_IN:
            r['junior'] = JUNIOR_MERGED_IN[j]
        n_j += j is not None
        n_s += s is not None
    for r in recs:
        r.setdefault('junior', None)
        r.setdefault('senior', None)
    return {'year': year, 'cols': cols, 'roles': roles, 'recs': recs,
            'n_junior': n_j, 'n_senior': n_s,
            'n_rec': len(recs), 'len_names': len(all_names)}


def _split_by_x_gap(frags, min_gap=30):
    """按 x 起点的最大间隙把片段分成两组（初中列 / 招生学校列）。

    片段形如 (x, y, text)。先按 x 排序，找最大相邻间隙；若间隙 < min_gap 则不分组
    （退化为单组，由调用方对整串做匹配）。
    """
    if len(frags) < 2:
        return [frags]
    fs = sorted(frags, key=lambda z: z[0])
    gaps = [(fs[i + 1][0] - fs[i][0], i) for i in range(len(fs) - 1)]
    g, idx = max(gaps)
    if g < min_gap:
        return [fs]
    return [fs[:idx + 1], fs[idx + 1:]]


def _junior_stream(pages, x_min, x_mid):
    """（已废弃：名称匹配改为按内容，不再按 x 分割列）"""
    return '', []


# 初中更名 / 合并登记
# 1) 纯更名：2022 官方分数线表用「上海市兴业中学」，2023 起改称
#    「上海交通大学附属黄浦实验中学」。归一后跨年才是同一所学校。
JUNIOR_RENAMES = {
    '上海市兴业中学': '上海交通大学附属黄浦实验中学',
}
# 2) 并入他校但生源序列独立：2024 年「上海市黄浦学校」不再单独招生，
#    官方分数线表把它的 9 条记录写作「上海市大同初级中学（原黄浦学校）」。
#    **不能并入大同初级中学**——那是另一批生源，混并会让趋势分析失真。
#    归一到「上海市黄浦学校」，使 2022/2023/2024 构成连续序列（2025 起无数据）。
JUNIOR_MERGED_IN = {
    '上海市大同初级中学（原黄浦学校）': '上海市黄浦学校',
}
# 官方文档中带括号注释的校名（2024 起），需作为独立池条目才能被最长匹配优先命中。
# 若只登记无「上海市」前缀的短名，贪心会在位置 0 先命中更短的「上海市大同初级中学」，
# 从而把并入的那批记录错并进大同（实测 2024 大同会变成 18 条 = 9+9）。
JUNIOR_ANNOTATED = ['上海市大同初级中学（原黄浦学校）']


def name_pools():
    """返回 (初中名池, 高中名池)，均按长度降序。

    高中名池**只含全称**：计划表 2024 整年用简称（格致奉贤/卢高/光明/华二附中…），
    简称如「光明」是初中名「上海市光明初级中学」的子串，混入后会污染匹配。
    分数线 PDF 五年均用全称，故按全称建池即可。
    """
    j, s = set(), set()
    with open(f'{D}/名额到校计划-黄浦区-2022-2026.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            j.add(r['junior_high_school'])
            s.add(r['senior_high_school'])
    # 计划表把 2024 的并入条目记作无前缀的「大同初级中学（原黄浦学校）」，
    # 分数线 PDF 则带「上海市」前缀；两者都加入池，并归一到「上海市黄浦学校」。
    j |= set(JUNIOR_ANNOTATED) | set(JUNIOR_MERGED_IN)
    # 曾用名 / 更名（PDF 中出现的旧写法）
    j |= {'大同初级中学（原黄浦学校）', '上海市兴业中学'}
    s = {n for n in s if len(n) >= 5}   # 剔除「光明」「向明」「大同」等简称
    return (sorted(j, key=len, reverse=True), sorted(s, key=len, reverse=True))


def junior_pool():
    """（保留兼容）初中名池"""
    return name_pools()[0]
    # 曾用名 / 更名（PDF 中出现的旧写法）
    names |= {'大同初级中学（原黄浦学校）', '上海市兴业中学'}
    return sorted((n for n in names if '民办' not in n or True), key=len, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', action='store_true')
    ap.add_argument('--year')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--baseline', help='对账基线 CSV（默认 /tmp/黄浦分数线-旧.csv）')
    a = ap.parse_args()
    jpool, spool = name_pools()

    if a.probe:
        print('=== 步骤 1：版面探测 ===')
        for y in YEARS:
            L = probe_layout(f'{D}/【黄浦】【{y}】名额到校最低分数线.pdf')
            cols, _, roles = detect_score_cols(f'{D}/【黄浦】【{y}】名额到校最低分数线.pdf')
            print(f'  {y}: {L["pages"]} 页 | 分数列 {len(cols)} 个')
            for c, r in zip(cols, roles):
                print(f'      x={c}: {r}')
            print(f'      同分优待列: {"有" if ("tie" in L["anchors"] or "tie2" in L["anchors"]) else "无（官方缺列）"}')
        return

    if a.year:
        r = extract_year(a.year, jpool, spool)
        print(f'{a.year}: 记录 {r["n_rec"]} 条 | 初中名配上 {r["n_junior"]} | '
              f'高中名配上 {r["n_senior"]}')
        for c, ro in zip(r['cols'], r['roles']):
            print(f'    列 x={c}: {ro}')
        for x in r['recs'][:4]:
            print(f'    {x["junior"]} | {x["senior"]} | 最低分{x["min_score"]} '
                  f'语数外{x["yw_sx"]} 数学{x["yw_math"]} 语文{x["yw_chinese"]} '
                  f'综合{x["yw_comprehensive"]} 综评{x["s综合评价"]} | p{x["pg"]}')
        bad = [x for x in r['recs'] if not x['junior'] or not x['senior']]
        if bad:
            print(f'  ⚠ 未配齐 {len(bad)} 条，样例: {[(b["junior"], b["senior"], b["nums"][0]) for b in bad[:5]]}')
        return

    if a.all:
        allr = {y: extract_year(y, jpool, spool) for y in YEARS}
        if a.report:
            _report(allr, a.baseline)
        if a.write:
            _write(allr)
        return

    ap.print_help()


def _report(allr, baseline=None):
    print('\n=== 新抽取 vs 基线 CSV 对账 ===')
    # 必须用**重抽前的原始 CSV** 作基线；若拿重抽后的自己比，等于自己比自己，
    # 恒为「差异 0」，对账形同虚设（2026-10 踩过：--write 后再 --report 即如此）。
    old = baseline or '/tmp/黄浦分数线-旧.csv'
    print(f'  基线：{old}')
    with open(old, encoding='utf-8-sig') as f:
        O = list(csv.DictReader(f))
    gnew = ngap = dsame = 0
    print(f"{'年':<6}{'新记录':>7}{'旧记录':>7}{'新增':>6}{'缺失':>6}{'分数不同':>9}{'初中':>6}{'名齐':>6}")
    for y in YEARS:
        R = allr[y]
        newk = {(r['junior'], r['senior']) for r in R['recs'] if r['junior'] and r['senior']}
        oldy = [r for r in O if r['year'] == y]
        oldk = {(r['junior_high_school'], r['senior_high_school']) for r in oldy}
        add, miss = newk - oldk, oldk - newk
        nm = {}
        for r in R['recs']:
            if r['junior'] and r['senior']:
                nm.setdefault((r['junior'], r['senior']), r['min_score'])
        om = {(r['junior_high_school'], r['senior_high_school']): r['min_score'] for r in oldy}
        diff = [k for k in newk & oldk
                if k[0] and k[1] and abs(float(nm[k]) - float(om[k])) > 1e-9]
        bad_sub = [r for r in R['recs'] if not (r['yw_sx'] and r['yw_math']
                   and r['yw_chinese'] and r['yw_comprehensive'])]
        gnew += len(add); ngap += len(miss); dsame += len(diff)
        nq = sum(1 for r in R['recs'] if r['junior'] and r['senior'])
        if bad_sub:
            print(f'      ⚠ 科目分缺列 {len(bad_sub)} 条')
        print(f'{y:<6}{r_count(R):>7}{len(oldy):>7}{len(add):>6}{len(miss):>6}'
              f'{len(diff):>9}{len({r["junior"] for r in R["recs"] if r["junior"]}):>6}{nq:>6}')
        if miss:
            print(f'      缺失 {len(miss)}: {sorted(miss)[:3]}')
        if diff:
            print(f'      分数不同 {len(diff)}: ' + '; '.join(
                f'{k[0][-6:]}|{k[1][-6:]} 新{nm[k]} 旧{om[k]}' for k in diff[:4]))
    print(f'\n合计：新增 {gnew} | 缺失 {ngap}（应 0）| 分数不同 {dsame}（应 0）')


def r_count(R):
    return R['n_rec']


def _write(allr):
    import shutil
    src = f'{D}/名额到校最低分数线-黄浦区-2022-2026.csv'
    shutil.copy(src, '/tmp/黄浦分数线-旧.csv')
    with open(src, encoding='utf-8-sig') as f:
        cols = next(csv.reader(f))
    rows = []
    for y in YEARS:
        R = allr[y]
        for r in R['recs']:
            rows.append({'year': y, 'district': '黄浦区',
                         'junior_high_school': r['junior'] or '',
                         'junior_high_school_code': '',
                         'senior_high_school': r['senior'] or '',
                         'senior_high_school_code': '',
                         'min_score': r['min_score'],
                         'score_full_mark': '800',
                         'is_tie_preferred': r['tie'],
                         's综合评价': (r['s综合评价'] or
                                  ('50' if y == '2024' else '')),
                         'yw_sx': r['yw_sx'], 'yw_math': r['yw_math'],
                         'yw_chinese': r['yw_chinese'],
                         'yw_comprehensive': r['yw_comprehensive'],
                         'source_doc': f'【黄浦】【{y}】名额到校最低分数线.pdf',
                         'source_page': r['pg'],
                         'note': ('2022 官方表无「是否同分优待」与「综合素质评价」列，'
                                  '综合素质评价按官方注明 50 填入' if y == '2022' else
                                  '2024 官方表无「综合素质评价」列，官方注明均为 50 分' if y == '2024' else
                                  '2023 官方表无「综合素质评价」列' if y == '2023' else '')})
    with open(src, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f'已写入 {src}：{len(rows)} 行（备份在 /tmp/黄浦分数线-旧.csv）')


if __name__ == '__main__':
    main()
