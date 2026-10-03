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


# 计划表：用于「委属本部 vs 区属分校」消歧（碎片截断时仅凭文字无法区分）
PLAN_QUOTA = {}
_pq = os.path.join(D, '名额到校计划-嘉定区-2023-2026.csv')
_pq2 = os.path.join(D, '名额到校计划-嘉定区-2022-图片转录.csv')
for _p in (_pq, _pq2):
    if os.path.exists(_p):
        with open(_p, encoding='utf-8-sig') as _f:
            for _r in csv.DictReader(_f):
                PLAN_QUOTA.setdefault((int(_r['year']), _r['junior_high_school']), set()).add(
                    _r['senior_high_school_code'])
# 截断对：短名 -> 长名（仅长名侧为区属线时才算歧义）
TRUNC_PAIRS = [('上海师范大学附属中学', '上海师范大学附属中学嘉定新城分校'),
               ('上海交通大学附属中学', '上海交通大学附属中学嘉定分校')]
CODE2NAME = {v[0]: k for k, v in HS_CANON.items()}


def canon_hs(s, year=None, sch=None):
    s = _denoise(cl(s))
    # 先做「本部 / 分校」消歧：短名恰好命中委属线时，须再看当年该校区属线是否有名额
    if year and sch:
        q = PLAN_QUOTA.get((year, sch), set())
        for short, lng in TRUNC_PAIRS:
            if short in s:
                c_short = next(c for c, n in CODE2NAME.items() if n == short)
                c_long = next(c for c, n in CODE2NAME.items() if n == lng)
                if c_long in q and c_short not in q:
                    return c_long, '区属', lng
    if s in HS_CANON:
        return HS_CANON[s][0], HS_CANON[s][1], s
    hit = [k for k in HS_CANON if k in s or s in k]
    if hit:
        k = max(hit, key=len)
        return HS_CANON[k][0], HS_CANON[k][1], k
    # 名称被截断（如「上海师范大学附属中学」实为「…嘉定新城分校」）：
    # 若该校当年在区属线有名额而委属线没有 → 判为区属线
    if year and sch:
        q = PLAN_QUOTA.get((year, sch), set())
        for short, lng in TRUNC_PAIRS:
            if short in s:
                c_short = next(c for c, n in CODE2NAME.items() if n == short)
                c_long = next(c for c, n in CODE2NAME.items() if n == lng)
                if c_long in q and c_short not in q:
                    return c_long, '区属', lng
                if c_short in q:
                    return c_short, HS_CANON[c_short][1], short
    return None, None, s


def num(t):
    try:
        return float(t)
    except ValueError:
        return None


NOISE = ('上海市教育考试院', '教育考试院')


def _denoise(t):
    for n in NOISE:
        t = t.replace(n, '')
    return t


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
    blob = _denoise(blob)          # 仅移除页脚「上海市教育考试院」，不动校名用字
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
    # 2023 版式校名续段在 x=70（初中列），故窗口取 xs-200（2023→88 / 2025→100），
    # 仍小于招生学校列起点（128~211），两列不串。
    jhi, hlo, hhi = xs - 200, xs - 220, xs - 40

    n_anchor = n_bad = 0
    bad_rows = []
    retry = []
    for pno, pg in enumerate(doc, 1):
        b = {}
        for w in pg.get_text('words'):
            b.setdefault(round(w[1] / 3.0), []).append(w)
        ks = sorted(b)
        yof = {k: min(w[1] for w in b[k]) for k in b}

        def col_same(k, lo, hi):
            return [cl(w[4]) for w in sorted(b[k], key=lambda w: w[0])
                    if lo <= w[0] <= hi and re.search(r'[\u4e00-\u9fff]', w[4])]

        def win(y0, lo, hi):
            """分数锚点 ±12px 窗口内、指定列区间的中文 token（页眉页脚噪声由规范名匹配过滤）。"""
            out = []
            for k in b:
                if abs(yof[k] - y0) > 7:
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
            if True:
                jblob = ''.join(win(y0, 0, jhi))
                jr = match_junior(jblob)
                # 少数行 PDF 把「初中名 + 招生名」合并为单 token → 用初中名剩余部分兜底
                leftover = jblob.replace(jr, '', 1) if jr else ''
                code, tier, hname = canon_hs(leftover + ''.join(win(y0, hlo, hhi)), y, jr)
                if code is None:
                    code, tier, hname = canon_hs(''.join(win(y0 + 8, hlo, hhi))
                                                + leftover + ''.join(win(y0, hlo, hhi)))
            if not jr:
                jr = last_jr                      # 同页最近一次有效初中名（校名写在分数线上一行）
            elif code is not None:
                last_jr = jr
            if not jr or code is None:
                n_bad += 1
                bad_rows.append((pno, jr, win(y0, hlo, hhi), sc))
                continue
            rows.append([y, '嘉定区', jr, None, hname, code, tier, sc, 800.0,
                         f'【嘉定】【{y}】名额到校最低分数线.pdf', pno])
    doc.close()
    diag[y] = (n_anchor, n_bad, bad_rows)

# ---- 定向修复：计划中有名额但抽取未覆盖的 (校, 线)，回原 PDF 逐页定位 ----
plan_path = os.path.join(D, '名额到校计划-嘉定区-2023-2026.csv')
plan_pairs = {}
if os.path.exists(plan_path):
    with open(plan_path, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            plan_pairs[(int(r['year']), r['junior_high_school'], r['senior_high_school_code'])] = r['senior_high_school']
have = {(r[0], r[2], r[5]) for r in rows}
missing = [k for k in plan_pairs if k not in have]
print(f'定向修复：计划有名额但未覆盖 {len(missing)} 对')
for y in YEARS:
    src = [k for k in missing if k[0] == y]
    if not src:
        continue
    path = os.path.join(D, f'【嘉定】【{y}】名额到校最低分数线.pdf')
    doc = fitz.open(path)
    xs = None
    for pg in doc:
        for w in pg.get_text('words'):
            if w[4] == '录取最低分':
                xs = w[0]
    buckets = {}
    for pno, pg in enumerate(doc, 1):
        for w in pg.get_text('words'):
            buckets.setdefault((pno, round(w[1] / 3.0)), []).append(w)
    yof = {}
    for (pno, k), ws in buckets.items():
        yof[(pno, k)] = min(w[1] for w in ws)
    def near(pno, y0, lo, hi, tol=7):
        out = []
        for (p2, k) in buckets:
            if p2 != pno or abs(yof[(p2, k)] - y0) > tol:
                continue
            out += [cl(w[4]) for w in sorted(buckets[(p2, k)], key=lambda w: w[0])
                    if lo <= w[0] <= hi and re.search(r'[\u4e00-\u9fff]', w[4])]
        return out
    for (yy, sch, code) in src:
        hname = NAME_BY_CODE.get(code, '')
        hit = None
        for (pno, k) in sorted(buckets, key=lambda t: (t[0], yof[t])):
            ws = sorted(buckets[(pno, k)], key=lambda w: w[0])
            y0 = yof[(pno, k)]
            sc = next((num(w[4]) for w in ws
                       if abs(w[0] - xs) <= 20 and num(w[4]) is not None and w[4] != '0'), None)
            if sc is None:
                continue
            if match_junior(''.join(near(pno, y0, 0, 100))) != sch:
                continue
            if canon_hs(''.join(near(pno, y0, 100, 300)), y, sch)[0] == code:
                hit = (sc, pno)
                break
        if hit:
            code2, tier2, hname2 = canon_hs(hname, yy, sch) if hname else (code, '区属' if code in QUARTER else '委属', hname)
            rows.append([yy, '嘉定区', sch, None, hname2, code,
                         '区属' if code in QUARTER else '委属', hit[0], 800.0,
                         f'【嘉定】【{yy}】名额到校最低分数线.pdf', hit[1]])
            print(f'    修复 {yy} {sch} {hname2} {hit[0]} (p{hit[1]})')
    doc.close()

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
