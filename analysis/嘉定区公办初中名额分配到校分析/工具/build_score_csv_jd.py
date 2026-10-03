# -*- coding: utf-8 -*-
"""2.1 嘉定区名额到校最低分数线 -> CSV。

规则：
  1) 列坐标由表头 token 精确定位（各年 x 不同，逐年探测）
  2) 记录锚点 = 「录取最低分」列的数值格；初中名/招生学校名取 y 邻域 ±16 内的列内 token 并拼接
     （校名与高中名常跨两行，如「…嘉定分」+「校」）
  3) 招生学校名归一：把换行碎片拼回全名后与 NAME_ALIAS 对照
输出：data/嘉定区/学校/名额到校最低分数线-嘉定区-2022-2026.csv
"""
import csv, os, re
import fitz

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), 'data', '嘉定区', '学校')
YEARS = [2022, 2023, 2024, 2025, 2026]
QUARTER = {'142001', '142002', '142004'}
HS_CANON = {
    '上海市嘉定区第一中学': ('142001', '区属'),
    '上海交通大学附属中学嘉定分校': ('142002', '区属'),
    '上海师范大学附属中学嘉定新城分校': ('142004', '区属'),
    '上海市上海中学': ('042032', '委属'),
    '上海交通大学附属中学': ('102056', '委属'),
    '复旦大学附属中学': ('102057', '委属'),
    '华东师范大学第二附属中学': ('152003', '委属'),
    '上海师范大学附属中学': ('152006', '委属'),
}


def cl(s):
    return re.sub(r'\s+', '', s)


def canon_hs(s):
    s = cl(s)
    if s in HS_CANON:
        return HS_CANON[s][0], HS_CANON[s][1], s
    hit = [k for k in HS_CANON if k in s or s in k]
    if hit:
        k = max(hit, key=len)
        return HS_CANON[k][0], HS_CANON[k][1], k
    return None, None, s


def num(t):
    try:
        return float(t)
    except ValueError:
        return None


def load_junior_canon():
    """初中规范名集合：计划 CSV（2023-2026）+ 各年分数线中出现的完整校名。"""
    names = set()
    pc = os.path.join(D, '名额到校计划-嘉定区-2023-2026.csv')
    if os.path.exists(pc):
        with open(pc, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['junior_high_school']:
                    names.add(r['junior_high_school'])
    return names


JUNIOR_CANON = load_junior_canon()


def match_junior(blob):
    hit = [n for n in JUNIOR_CANON if n in blob]
    if hit:
        return max(hit, key=len)
    s = blob
    while s:
        if s.endswith(('中学', '学校')) and len(s) >= 6:
            return s
        s = s[:-1]
    return None


rows = []
diag = {}
for y in YEARS:
    path = os.path.join(D, f'【嘉定】【{y}】名额到校最低分数线.pdf')
    doc = fitz.open(path)
    xj = xl = xs = xt = None
    for p in doc:
        for w in p.get_text('words'):
            if w[4] == '初中学校':
                xj = w[0]
            elif w[4] == '招生学校':
                xl = w[0]
            elif w[4] == '录取最低分':
                xs = w[0]
            elif '语数外' in w[4] and xt is None:   # 2022 表头合并为「语数外数学语文综合测试」
                xt = w[0]
    # 列窗口由表头 x 推导（表头与数据左对齐，但偏移固定）：
    #   初中名 x < xs-220 < 招生学校名 x < xs-40 < 录取最低分 x ≈ xs
    assert None not in (xj, xl, xs), f'{y} 表头定位失败'
    jhi, hlo, hhi = xs - 220, xs - 220, xs - 40

    n_anchor = n_bad = 0
    bad_rows = []
    retry = []
    for pno, pg in enumerate(doc, 1):
        b = {}
        for w in pg.get_text('words'):
            b.setdefault(round(w[1] / 3.0), []).append(w)
        ks = sorted(b)
        yof = {k: min(w[1] for w in b[k]) for k in b}

        def win(y0, lo, hi):
            """分数锚点 ±12px 窗口内、指定列区间的中文 token（页眉页脚噪声由规范名匹配过滤）。"""
            out = []
            for k in b:
                if abs(yof[k] - y0) > 12:
                    continue
                for w in sorted(b[k], key=lambda w: w[0]):
                    if lo <= w[0] <= hi and re.search(r'[\u4e00-\u9fff]', w[4]):
                        out.append(cl(w[4]))
            return out

        last_jr = None
        for k in sorted(b):
            row = sorted(b[k], key=lambda w: w[0])
            y0 = yof[k]
            sc = next((num(w[4]) for w in row
                       if abs(w[0] - xs) <= 20 and num(w[4]) is not None and w[4] != '0'), None)
            if sc is None:
                continue
            n_anchor += 1
            jr = match_junior(''.join(win(y0, 0, jhi)))
            code, tier, hname = canon_hs(''.join(win(y0, hlo, hhi)))
            if code is None:                      # 同页宽窗重试一次
                code, tier, hname = canon_hs(''.join(win(y0 + 8, hlo, hhi))
                                            + ''.join(win(y0, hlo, hhi)))
            if not jr:
                jr = last_jr                      # 同页最近一次有效初中名（校名写在分数线上一行）
            elif code is not None:
                last_jr = jr
            if not jr or code is None:
                n_bad += 1
                bad_rows.append((pno, jr, win(y0, hlo, hhi), sc))
                continue
            rows.append([y, '嘉定区', jr, None, hname, code, tier, sc, 750.0,
                         f'【嘉定】【{y}】名额到校最低分数线.pdf', pno])
    doc.close()
    diag[y] = (n_anchor, n_bad, bad_rows)

# 去重：同一 (年, 校, 线) 只保留文档中首次出现的一行
seen = {}
dropped = []
for r in rows:
    key = (r[0], r[2], r[5])
    if key in seen:
        dropped.append((key, r[7], r[10]))
    else:
        seen[key] = r
rows = list(seen.values())
print('去重：移除', len(dropped), '行')
for d in dropped:
    print('   重复被移除:', d)

# 与计划表交叉：抽出的 (年,校,线) 必须在计划中存在
pc = os.path.join(D, '名额到校计划-嘉定区-2023-2026.csv')
plan_pairs = set()
with open(pc, encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        plan_pairs.add((int(r['year']), r['junior_high_school'], r['senior_high_school_code']))
orphan = [(r[0], r[2], r[5]) for r in rows
          if (r[0], r[2], r[5]) not in plan_pairs]
print('无计划对应的分数线对:', len(orphan), orphan[:8])
miss = sorted(plan_pairs - {(r[0], r[2], r[5]) for r in rows})
print('有计划但无分数的对:', len(miss), miss[:8])

out = os.path.join(D, '名额到校最低分数线-嘉定区-2022-2026.csv')
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['year', 'district', 'junior_high_school', 'junior_high_school_code',
                'senior_high_school', 'senior_high_school_code', 'high_school_tier',
                'min_score', 'score_full_mark', 'source_doc', 'source_page'])
    w.writerows(rows)
print(f'写出 {len(rows)} 行 -> {out}')
for y in YEARS:
    a, bad, brs = diag[y]
    print(f'  {y}: 分数锚点 {a}，抽取失败 {bad}，写出 {sum(1 for r in rows if r[0] == y)}')
    for b in brs[:4]:
        print(f'      失败样本 p{b[0]} 初中={b[1]} 招生={b[2]} 分数={b[3]}')
import collections
print('  逐年线数:', {y: len({r[5] for r in rows if r[0] == y}) for y in YEARS})
print('  逐线覆盖:', {y: sorted({(r[5], r[6]) for r in rows if r[0] == y}) for y in [2022, 2026]})
import collections as _c
dup = [k for k, v in _c.Counter((r[0], r[2], r[5]) for r in rows).items() if v > 1]
print('  重复 (年,校,线) 对:', len(dup), dup[:5])
print('  分数范围:', {y: (min(r[7] for r in rows if r[0] == y), max(r[7] for r in rows if r[0] == y)) for y in YEARS})
