# -*- coding: utf-8 -*-
"""2.3 黄浦区名额分配到校计划：5 份 PDF → 统一字段 CSV。

表头几何（坐标实测）：名称在上、6 位代码紧邻其下（Δy 6–12px，Δx≈0），
故按 x 邻近配对「代码 → 名称」，不可按阅读顺序（会错位）。
数据行几何：初中代码在最左（x≈115），初中名在其下方的同一 x（x≈107），
N 个名额数分别与表头 N 个代码列对齐（偏移 +8px 左右）。
每页有斜向水印「未经允许，不得转载」，需按 x 位置而非阅读顺序排除。
"""
import csv
import os
import re
from collections import defaultdict

import fitz

import alias_hp

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/黄浦区/学校'
YEARS = [2022, 2023, 2024, 2025, 2026]
CODE = re.compile(r'^\(?(\d{6})\)?$')
JUNIOR = re.compile(r'^01(\d{4})$')
NOISE = ('未经允许', '不得转载', '转载', '得载', '学校代码', '名称', '注：',
         '计划安排', '公示', '黄浦区名额分配', '根据', '沪教委', '黄教基')


def buckets(path, ytol=3.0):
    doc = fitz.open(path)
    out = []
    for pi, pg in enumerate(doc):
        b = defaultdict(list)
        for w in pg.get_text('words'):
            b[round(w[1] / ytol)].append(w)
        for k in sorted(b):
            ws = sorted(b[k], key=lambda w: w[0])
            out.append((pi + 1, min(w[1] for w in ws), [(w[0], w[4]) for w in ws]))
    doc.close()
    return out


def extract(year):
    R = buckets(f'{D}/【黄浦】【{year}】名额到校计划.pdf')
    code_row = None
    for pg, y, cs in R:
        codes = [(x, CODE.match(t).group(1)) for x, t in cs if CODE.match(t)]
        if len(codes) >= 6:
            code_row = (pg, y, sorted(codes))
            break
    if not code_row:
        return [], []
    _, cy, cols = code_row
    # 名称：在代码行上下 22px 内、按 x 邻近（±22px）配对，排除水印噪声
    names = {}
    for pg, y, cs in R:
        if abs(y - cy) > 22:
            continue
        for x, t in cs:
            if CODE.match(t) or any(n in t for n in NOISE) or len(t) > 14:
                continue
            near = min(cols, key=lambda c: abs(c[0] - x))
            if abs(near[0] - x) <= 22:
                names.setdefault(near[1], t)
    colx = [x for x, _ in cols]
    first_x = min(colx)
    left = first_x - 30          # 校名列与数字列的分界（2022 校名第二段 x=100，首列 x=138）

    def is_name_cell(x, t):
        return (x < left and not CODE.match(t) and not t.isdigit()
                and not any(n in t for n in NOISE) and 1 < len(t) <= 20)

    # ---- 第一遍：代码 → 校名（校名可能拆 1–2 行，落在代码行下方）----
    seq = [(pg, y, cs) for pg, y, cs in R
           if any(JUNIOR.match(t) for x, t in cs if x < left)]
    name_of = {}
    for i, (pg, cy, cs) in enumerate(seq):
        code = next(JUNIOR.match(t).group(0) for x, t in cs
                    if x < left and JUNIOR.match(t))
        stop = cy + 30
        for j in range(i + 1, len(seq)):        # 同页下一代码的 y 为界
            if seq[j][0] != pg:
                break
            stop = min(stop, seq[j][1])
        # 用 cy-4 而非 cy：2024 年校名首段与代码同在一个 y 桶
        parts = [(y, x, t) for pg2, y, cs2 in R if pg2 == pg and cy - 4 < y < stop
                 for x, t in cs2 if is_name_cell(x, t)]
        name_of[code] = ''.join(t for _, _, t in sorted(parts))

    # ---- 第二遍：按列对齐抽名额 ----
    recs = []
    cur = None
    for pg, y, cs in R:
        jm = next((JUNIOR.match(t).group(0) for x, t in cs
                   if x < left and JUNIOR.match(t)), None)
        if jm:
            cur = jm
            continue
        if cur is None:
            continue
        nums = [(x, int(t)) for x, t in cs if t.isdigit() and x > left]
        if len(nums) < len(colx) - 1:
            continue
        for x, code in cols:
            near = min(nums, key=lambda nt: abs(nt[0] - x))
            if abs(near[0] - x) > 45:
                continue
            recs.append({'year': year, 'district': '黄浦区',
                         'junior_high_school_code': cur,
                         'junior_high_school': name_of.get(cur, ''),
                         'senior_high_school_code': code,
                         'senior_high_school': names.get(code, ''),
                         'quota': near[1],
                         'source_doc': f'【黄浦】【{year}】名额到校计划.pdf',
                         'source_page': pg})
        cur = None
    return recs, sorted((c, names.get(c, '')) for _, c in cols)


ALL, LINES = [], {}
for y in YEARS:
    r, ln = extract(y)
    LINES[y] = ln
    print(f'{y}: {len(r)} 条 | 招生学校 {len(ln)} 条 | 初中 {len({x["junior_high_school_code"] for x in r})} 所')
    ALL += r


# ---- 名称归一：按「校名」映射到分数线表的全称；代码原样保留为逐年字段 ----
_namefix = 0
for _r in ALL:
    _c = _r['junior_high_school_code']
    if _c in alias_hp.PLACEHOLDER_CODES:
        _r['is_placeholder_code'] = 1
        continue
    _r['is_placeholder_code'] = 0
    _full = alias_hp.canon_junior(_r['junior_high_school'])
    if _full != _r['junior_high_school']:
        _namefix += 1
    _r['junior_high_school'] = _full
    _lc = alias_hp.LINE_BY_NAME.get(_r['senior_high_school'], ('', ''))
    if _lc[0]:
        _r['senior_high_school_code'] = _lc[0]
        _r['senior_high_school'] = _lc[1]
print(f'名称归一：{_namefix}/{len(ALL)} 行按校名映射到全称（代码不作键，跨年不稳定）')
BAD = [r for r in ALL if r['is_placeholder_code']]
print(f'占位代码行 {len(BAD)} 条（{sorted({r["junior_high_school_code"] for r in BAD})}），已标记')

out = f'{D}/名额到校计划-黄浦区-2022-2026.csv'
cols_out = ['year', 'district', 'junior_high_school', 'junior_high_school_code',
            'senior_high_school', 'senior_high_school_code', 'quota',
            'source_doc', 'source_page', 'is_placeholder_code']
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols_out)
    w.writeheader()
    for r in ALL:
        w.writerow(r)
print('写出', out.split('/')[-1], f'共 {len(ALL)} 行')

print('\n逐年招生学校（代码 → 名称）：')
for y in YEARS:
    print(f'  {y}（{len(LINES[y])}）: ' + '、'.join(f'{c}→{n}' for c, n in LINES[y]))
print('\n逐年规模：')
for y in YEARS:
    rs = [r for r in ALL if r['year'] == y]
    print(f'  {y}: 初中 {len({r["junior_high_school_code"] for r in rs})} 所 | '
          f'非零名额 {len([r for r in rs if r["quota"] > 0])} 格 | 合计 {sum(r["quota"] for r in rs)}')
print('\n各年初中名单：')
for y in YEARS:
    js = sorted({(r['junior_high_school_code'], r['junior_high_school'])
                 for r in ALL if r['year'] == y})
    print(f'  {y}（{len(js)}）: ' + '、'.join(f'{c} {n}' for c, n in js))
