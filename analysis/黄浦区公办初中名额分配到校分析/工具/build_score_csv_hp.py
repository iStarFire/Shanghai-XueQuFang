# -*- coding: utf-8 -*-
"""2.3 黄浦区名额到校最低分数线：5 份 PDF → 统一字段 CSV。

版式（5 年一致）：初中学校 | 招生学校 | 录取最低分 | 是否同分优待 | 综合素质评价
                | 末位录取考生成绩：语数外 / 数学 / 语文 / 综合测试
列的 x 顺序与逻辑顺序一致，故按 x 排序后：
  前两个非数字单元 = 初中学校、招生学校；「否/是」= 是否同分优待；
  其余数字按出现年份的已知顺序绑定（见 NUMCOLS）。
跨年计入口径差异（2022/2023 综合考查、2024 起综合素质评价）由 source_doc 记录，不合并。
"""
import csv
import os
import re
from collections import defaultdict

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/黄浦区/学校'
YEARS = [2022, 2023, 2024, 2025, 2026]
# 各年数字列的逻辑顺序（不含是否同分优待）
NUMCOLS = {
    2022: ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
    2023: ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
    2024: ['min_score', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
    2025: ['min_score', 's综合评价', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
    2026: ['min_score', 's综合评价', 'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive'],
}
COMPREHENSIVE_NOTE = {
    2022: '录取最低分含学业考总成绩和综合考查成绩；无综合素质评价列',
    2023: '录取最低分含学业考总成绩和综合考查成绩；无综合素质评价列',
    2024: '录取最低分含学业考总成绩和综合素质评价成绩；表末注明综合素质评价均为 50 分',
    2025: '录取最低分含学业考总成绩和综合素质评价成绩；含综合素质评价列',
    2026: '录取最低分含学业考总成绩和综合素质评价成绩；含综合素质评价列',
}


def isnum(t):
    try:
        float(t)
        return True
    except ValueError:
        return False


def rows(path, ytol=3.0):
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


# 计划表由 build_plan_csv_hp.py 生成，是招生学校集合的权威来源（该 PDF 无水印）。
# 分数线 PDF 每页有斜向水印「上海市教育考试院」，会把碎片（如「试院」）挤进单元格，
# 故必须用计划表集合做白名单校验，而不是只靠「非数字 = 校名」的启发式。
import csv as _csv
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alias_hp

VALID = set(alias_hp.LINE_BY_NAME)
# 逐年「校名 → 初中代码」映射（取自计划表；代码跨年不稳定，故必须带 year）
CODE_OF = {}
with open(f'{D}/名额到校计划-黄浦区-2022-2026.csv', encoding='utf-8-sig') as f:
    for _r in _csv.DictReader(f):
        if _r['is_placeholder_code'] == '0':
            CODE_OF.setdefault((_r['year'], _r['junior_high_school']),
                               _r['junior_high_school_code'])
print(f'权威招生学校集合 {len(VALID)} 条｜逐年校名→代码映射 {len(CODE_OF)} 条')


def extract(year):
    path = f'{D}/【黄浦】【{year}】名额到校最低分数线.pdf'
    recs = []
    for pg, y, cs in rows(path):
        cells = [(x, t) for x, t in cs if t.strip()]
        if len(cells) < 5:
            continue
        txt = ''.join(t for _, t in cells)
        # 跳过表头与注释行
        if any(k in txt for k in ('初中学校', '招生学校', '录取最低分', '语数外',
                                 '是否同', '末位录取', '综合素质评价', '注：')):
            continue
        if '上海市教育考试院' in txt or '黄浦区' in txt:
            continue
        nonnum = [(x, t) for x, t in cells if not isnum(t)]
        tie = [t for _, t in nonnum if t in ('是', '否')]
        names = [(x, t) for x, t in nonnum if t not in ('是', '否')]
        if len(names) != 2:          # 校名 + 招生学校（「是/否」列不计入）
            continue
        junior, senior = names[0][1], names[1][1]
        # 白名单校验：剔除水印碎片造成的伪招生学校（如「试院」）
        if senior not in VALID:
            continue
        if not (junior.endswith('中学') or junior.endswith('学校')):
            continue
        nums = [(x, t) for x, t in cells if isnum(t)]
        cols = NUMCOLS[year]
        if len(nums) != len(cols):
            continue
        same = tie[0] if tie else ''
        _jfull = alias_hp.JUNIOR_ALIAS.get(junior, junior)
        _jc = CODE_OF.get((str(year), _jfull), '')
        _lc, _lfull = alias_hp.LINE_BY_NAME.get(senior, ('', senior))
        d = {'year': year, 'district': '黄浦区', 'junior_high_school': _jfull,
             'junior_high_school_code': _jc,
             'senior_high_school': _lfull,
             'senior_high_school_code': _lc,
             'is_tie_preferred': same,
             'source_doc': f'【黄浦】【{year}】名额到校最低分数线.pdf', 'source_page': pg,
             'note': COMPREHENSIVE_NOTE[year]}
        for (x, t), key in zip(nums, cols):
            d[key] = float(t)
        recs.append(d)
    return recs


ALL = []
for y in YEARS:
    r = extract(y)
    print(f'{y}: 抽出 {len(r)} 条')
    ALL += r

cols = ['year', 'district', 'junior_high_school', 'junior_high_school_code',
        'senior_high_school', 'senior_high_school_code', 'min_score',
        'score_full_mark', 'is_tie_preferred', 's综合评价',
        'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive',
        'source_doc', 'source_page', 'note']
# ---- 跨年前缀补全 ----
# 部分年份（2024 尤其明显）把校名排成 2 个 y 桶，按「首个非数字单元」取名会只拿到
# 前半段（如「中山学」「储能中」）。这里用「所有出现过的校名」互为前缀来补全，
# 只改名称、不动分数；补全后仍不完整的会单独打印出来人工确认。
_names = sorted({r['junior_high_school'] for r in ALL})
_fixed = 0
for r in ALL:
    n = r['junior_high_school']
    if n in _names:
        continue
    cand = [f for f in _names if f != n and f.startswith(n) and len(f) > len(n)]
    if cand:
        r['junior_high_school'] = cand[0]
        _fixed += 1
print(f'校名前缀补全：{_fixed} 行由截断名补为完整校名')
LEFT = sorted({r['junior_high_school'] for r in ALL
               if not any(f.startswith(r['junior_high_school']) or f == r['junior_high_school']
                          for f in _names)})
print(f'  仍不完整（需人工确认）：{LEFT if LEFT else "无"}')

out = f'{D}/名额到校最低分数线-黄浦区-2022-2026.csv'
cols = ['year', 'district', 'junior_high_school', 'junior_high_school_code',
        'senior_high_school', 'senior_high_school_code', 'min_score',
        'score_full_mark', 'is_tie_preferred', 's综合评价',
        'yw_sx', 'yw_math', 'yw_chinese', 'yw_comprehensive',
        'source_doc', 'source_page', 'note']
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    for r in sorted(ALL, key=lambda r: (r['year'], r['junior_high_school'],
                                        r['senior_high_school'])):
        w.writerow(r)
print('写出', out.split('/')[-1], f'共 {len(ALL)} 行')

print('\n逐年学校数与招生学校数：')
for y in YEARS:
    rs = [r for r in ALL if r['year'] == y]
    print(f'  {y}: 初中 {len({r["junior_high_school"] for r in rs})} 所 | '
          f'招生学校 {len({r["senior_high_school"] for r in rs})} 条 | 记录 {len(rs)}')
