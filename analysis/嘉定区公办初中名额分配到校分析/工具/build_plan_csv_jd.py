# -*- coding: utf-8 -*-
"""2.1 嘉定区名额到校招生计划 -> CSV。

来源形态逐年不同：
  2023 / 2024：区教育局公示页内嵌 HTML 表格
  2025 / 2026：区教育局公示页 PDF 附件（每条记录跨 3 行：校名段 / 代码+计划数段 / 校名续段）
  2022：官方页 404，仅有二手图片，本脚本不产出（缺口在报告中声明）

关键抽取规则（PDF）：
  1) 计划数 = 「本代码 x」与「下一代码 x」之间的第一个数字格（列位置逐行漂移，不能用固定坐标）
  2) 初中名 = 三行内 x<130 的中文片段拼接（校名常跨行），再与规范名集合匹配
输出：data/嘉定区/学校/名额到校计划-嘉定区-2023-2026.csv
"""
import csv, html, os, re
import fitz

D = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), 'data', '嘉定区', '学校')

NAME_BY_CODE = {
    '142001': '上海市嘉定区第一中学',
    '142002': '上海交通大学附属中学嘉定分校',
    '142004': '上海师范大学附属中学嘉定新城分校',
    '042032': '上海市上海中学',
    '102056': '上海交通大学附属中学',
    '102057': '复旦大学附属中学',
    '152003': '华东师范大学第二附属中学',
    '152006': '上海师范大学附属中学',
}
QUARTER = {'142001', '142002', '142004'}
TIER = {c: ('区属' if c in QUARTER else '委属') for c in NAME_BY_CODE}
CODE_RE = re.compile(r'^(?:042|102|142|152)\d{3}$')
PREFIX = ('上海市嘉定区', '上海市', '上海', '中科院', '交大', '同济')


def cl(s):
    return re.sub(r'\s+', '', html.unescape(s).replace('\xa0', ' ')).strip()


def name_ok(s):
    return s.endswith(('中学', '学校')) and s.startswith(PREFIX) and len(s) >= 6


def load_canon():
    """规范名集合 = 2023/2024 HTML 名单 + 各年分数线中的初中名。"""
    canon = set()
    for y in (2023, 2024):
        h = open(os.path.join(D, f'【嘉定】【{y}】名额到校计划.html'),
                 encoding='utf-8', errors='ignore').read()
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S):
            cs = [cl(re.sub(r'<[^>]+>', '', c))
                  for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
            if cs and cs[0] not in ('初中学校', '招生学校代码') and cs[0]:
                canon.add(cs[0])
    for y in (2022, 2023, 2024, 2025, 2026):
        doc = fitz.open(os.path.join(D, f'【嘉定】【{y}】名额到校最低分数线.pdf'))
        b = {}
        for p in doc:
            for w in p.get_text('words'):
                b.setdefault(round(w[1] / 3.0), []).append(w)
        for k in b:
            for w in sorted(b[k], key=lambda x: x[0]):
                t = cl(w[4])
                if w[0] < 130 and t.endswith(('中学', '学校')) and t.startswith(PREFIX):
                    canon.add(t)
        doc.close()
    return canon


def from_html(year, out):
    h = open(os.path.join(D, f'【嘉定】【{year}】名额到校计划.html'),
             encoding='utf-8', errors='ignore').read()
    best = ''
    for m in re.finditer(r'<table', h):
        end = h.find('</table>', m.start())
        seg = h[m.start():end]
        if '招生学校代码' in seg and len(seg) > len(best):
            best = seg
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', best, re.S):
        cs = [cl(re.sub(r'<[^>]+>', '', c))
              for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
        if not cs or cs[0] in ('初中学校', '招生学校代码') or not cs[0]:
            continue
        for i in range(1, len(cs) - 2, 3):
            code, name, quota = cs[i], cs[i + 1], cs[i + 2]
            if CODE_RE.match(code) and quota.isdigit():
                out.append((year, cs[0], code, NAME_BY_CODE.get(code) or name,
                            TIER[code], int(quota),
                            f'【嘉定】【{year}】名额到校计划.html', 1))


def from_pdf(year, canon, out):
    doc = fitz.open(os.path.join(D, f'【嘉定】【{year}】名额到校计划.pdf'))

    def match(blob):
        c = [n for n in canon if n in blob]
        if c:
            return max(c, key=len)
        s = blob
        while s:
            if name_ok(s):
                return s
            s = s[:-1]
        return None

    for pno, pg in enumerate(doc, 1):
        b = {}
        for w in pg.get_text('words'):
            b.setdefault(round(w[1] / 3.0), []).append(w)
        ks = sorted(b)

        def frag(j):
            if j < 0 or j >= len(ks):
                return ''
            return cl(''.join(w[4] for w in sorted(b[ks[j]], key=lambda w: w[0])
                              if w[0] < 130 and not CODE_RE.match(w[4])))

        for i, k in enumerate(ks):
            row = sorted(b[k], key=lambda w: w[0])
            codes = [(w[0], w[4]) for w in row if CODE_RE.match(w[4])]
            if not codes:
                continue
            nm = match(frag(i - 1) + frag(i) + frag(i + 1))
            nums = [(w[0], w[4]) for w in row if re.match(r'^\d{1,2}$', w[4])]
            for j, (cx, code) in enumerate(codes):
                hi = codes[j + 1][0] if j + 1 < len(codes) else cx + 130
                q = next((t for x, t in nums if cx < x < hi), None)
                if q is None:
                    continue          # 该 (校, 线) 无名额：计划表空格
                out.append((year, nm, code, NAME_BY_CODE[code], TIER[code], int(q),
                            f'【嘉定】【{year}】名额到校计划.pdf', pno))
    doc.close()


rows = []
for y in (2023, 2024):
    from_html(y, rows)
canon = load_canon()
for y in (2025, 2026):
    from_pdf(y, canon, rows)

path = os.path.join(D, '名额到校计划-嘉定区-2023-2026.csv')
with open(path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['year', 'junior_high_school', 'senior_high_school_code',
                'senior_high_school', 'senior_high_school_tier', 'quota',
                'source_doc', 'source_page'])
    w.writerows(rows)
print(f'写出 {len(rows)} 行 -> {path}')
import collections
print('逐年行数:', dict(collections.Counter(r[0] for r in rows)))
print('逐年初中数:', {y: len({r[1] for r in rows if r[0] == y}) for y in (2023, 2024, 2025, 2026)})
print('校名未匹配:', sorted({r[1] for r in rows if r[1] is None}) or '无')
print('区属线:', {y: sorted({r[2] for r in rows if r[0] == y and r[4] == '区属'}) for y in (2023, 2024, 2025, 2026)})
print('名额合计:', {y: sum(r[5] for r in rows if r[0] == y) for y in (2023, 2024, 2025, 2026)})
print('无名额(校,线)对数:', sum(1 for y in (2023, 2024, 2025, 2026)
                          for c in {r[1] for r in rows if r[0] == y}
                          for code in {r[2] for r in rows if r[0] == y and r[4] == '区属'}
                          if not any(r[0] == y and r[1] == c and r[2] == code for r in rows)))
