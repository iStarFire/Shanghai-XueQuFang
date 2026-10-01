# -*- coding: utf-8 -*-
"""普陀区「名额分配到校」最低分数线提取（PyMuPDF 逐字符版 v3）。

工具变更记录：
- v0：复用徐汇自研 ex3.py —— 普陀 2024 版式下两行校名被拆开且续行丢失（已证实 PDF 文本层完整）。
- v1/v2：PyMuPDF words —— MuPDF 的 word 切分把「初中续行 + 高中首行」连成一个词，串列。
- v3（当前）：rawdict 逐字符 + 行聚类 + 锚点行归并（字符级分带，杜绝词级串列）；
  水印「上海市教育考试院」按 span 过滤（ex3 时代由 OCG 跳过逻辑处理）。
"""
import sys, re, os
import fitz

WATERMARK = '上海市教育考试院'
BANDS = {
 2022: [200, 370, 440, 478, 508, 532],   # 实测标定：初中<200 | 高中200-370 | 最低分370-440 | 语数外440-478 | 数学478-508 | 语文508-532 | 综测≥532
 2023: [130, 290, 375, 425, 455, 490, 525],
 2024: [130, 290, 375, 425, 455, 490, 525],
 2025: [130, 290, 375, 425, 458, 480, 508, 535],
 2026: [130, 290, 375, 425, 458, 480, 508, 535],
}
NAMES = {
 2022: ['junior_high_school','senior_high_school','min_score',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2023: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2024: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'last_chinese_math_english','last_math','last_chinese','last_comprehensive_test'],
 2025: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'comprehensive_eval','last_chinese_math_english','last_math','last_chinese',
        'last_comprehensive_test'],
 2026: ['junior_high_school','senior_high_school','min_score','is_tie_privilege',
        'comprehensive_eval','last_chinese_math_english','last_math','last_chinese',
        'last_comprehensive_test'],
}
NUM = re.compile(r'^-?\d+(?:\.\d+)?$')
ROW_TOL = 3.0
JOIN_TOL = 12.0

def band_of(x, bands):
    i = 0
    while i < len(bands) and x >= bands[i]:
        i += 1
    return i

def page_chars(page, bands):
    """rawdict → 逐字符 (y, x, ch)，跳过水印 span；返回聚类后的视觉行列表。"""
    raw = page.get_text('rawdict')
    H = page.rect.height
    chars = []
    for blk in raw.get('blocks', []):
        for ln in blk.get('lines', []):
            d = ln.get('dir', (1, 0))          # 只保留水平文本：排除斜向「上海市教育考试院」
            if abs(d[0] - 1) > 0.01 or abs(d[1]) > 0.01:
                continue                       # 印章与竖排「注」列均被此条排除
            for sp in ln.get('spans', []):
                for ch in sp.get('chars', []):
                    x, y = ch['origin']
                    # 普陀 PDF 的文本坐标 y 自底向上：显示 y = 页高 − 原始 y
                    # （实测：'洵' origin y=119.94 → 显示 722.06，与 ex3 一致）
                    chars.append((H - y, x, ch['c']))
    chars.sort(key=lambda c: (-c[0], c[1]))
    lines = []
    for y, x, t in chars:
        if lines and abs(lines[-1][0] - y) <= ROW_TOL:
            lines[-1][1].append((x, t))
        else:
            lines.append((y, [(x, t)]))
    out = []
    for y, cs in lines:
        cols = {}
        for x, t in cs:
            i = band_of(x, bands)
            if i < len(bands) + 1:
                cols[i] = (cols.get(i, '') + t).strip()
        out.append((y, cols))
    return out

def extract_year(year, path):
    bands = BANDS[year]
    ncol = len(NAMES[year])
    doc = fitz.open(path)
    out = []
    for pno in range(len(doc)):
        lines = page_chars(doc[pno], bands)
        anchors = [i for i, (y, c) in enumerate(lines) if NUM.match(c.get(2, '') or '')]
        if not anchors:
            continue
        merged = {i: dict(lines[i][1]) for i in anchors}
        ys = {i: lines[i][0] for i in anchors}
        for i, (y, c) in enumerate(lines):
            if i in merged:
                continue
            if not any(k in c for k in (0, 1)):
                continue
            near = min(anchors, key=lambda a: abs(ys[a] - y))
            if abs(ys[near] - y) > JOIN_TOL:
                continue
            for k in (0, 1):
                if k in c:
                    if y < ys[near]:
                        merged[near][k] = (merged[near].get(k, '') + c[k]).strip()
                    else:
                        merged[near][k] = (c[k] + merged[near].get(k, '')).strip()
        for i in anchors:
            c = merged[i]
            vals = [c.get(j, '') for j in range(ncol)]
            if not vals[0] or not vals[1]:
                continue
            out.append((pno + 1, vals))
    return out

if __name__ == '__main__':
    year = int(sys.argv[1]); path = sys.argv[2]
    rows = extract_year(year, path)
    jhs = set(v[0] for _, v in rows); shs = set(v[1] for _, v in rows)
    print(f'=== {year}: {len(rows)} 行, {len(jhs)} 初中, {len(shs)} 高中 ===')
    print('  高中:', ' | '.join(sorted(shs)))
    print('  可疑初中名:', sorted(n for n in jhs if len(n) < 6 or len(n) > 22))
    for pno, v in rows[:2]:
        print('  ', ' | '.join(x or '·' for x in v))
