# -*- coding: utf-8 -*-
"""普陀区「名额分配到校计划」提取（2026 公示，PyMuPDF）。

表结构（横排 A4，2 页）：学校代码 | 学校名称 | 华二 | 上中 | 复附 | 交附 | 上师大
  | 华二普陀 | 二中 | 晋元 | 宜川 | 总计
口径：市实验性示范性高中名额分配综合评价录取招生计划分配到普陀区不选择生源学校。
输出长表：year, junior_high_school_code, junior_high_school, senior_high_school_short,
  senior_high_school, senior_high_school_code, quota, source_doc, source_page
"""
import csv, os, re
import fitz

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
PDF = f"{BASE}/data/普陀区/学校/【普陀】【2026】名额到校计划.pdf"
OUT = f"{BASE}/data/普陀区/学校/名额到校计划-普陀区-2026.csv"
SOURCE = "【普陀】【2026】名额到校计划.pdf"

# 列序（表头 x 从左到右），简名 → 全名与代码
COLS = [
    ('华二', '华东师范大学第二附属中学', '委属'),
    ('上中', '上海市上海中学', '委属'),
    ('复附', '复旦大学附属中学', '委属'),
    ('交附', '上海交通大学附属中学', '委属'),
    ('上师大', '上海师范大学附属中学', '委属'),
    ('华二普陀', '华东师范大学第二附属中学（普陀校区）', '区属'),
    ('二中', '上海市曹杨第二中学', '区属'),
    ('晋元', '上海市晋元高级中学', '区属'),
    ('宜川', '上海市宜川中学', '区属'),
]

def extract():
    doc = fitz.open(PDF)
    rows = []
    for pno in range(len(doc)):
        pg = doc[pno]
        H = pg.rect.height
        words = [(H - w[1], w[0], w[4]) for w in pg.get_text('words')
                 if w[4].strip() and '转载' not in w[4]]   # 过滤页内水印碎片
        lines = []
        for y, x, t in sorted(words, key=lambda p: (-p[0], p[1])):
            if lines and abs(lines[-1][0] - y) <= 3:
                lines[-1][1].append((x, t))
            else:
                lines.append((y, [(x, t)]))
        for y, cells in lines:
            joined = ''.join(t for _, t in sorted(cells))
            m = re.match(r'^(\d{6})(.+?)((?:\d{1,2}){9}\d{1,2})$', joined)
            if not m:
                continue
            code, name = m.group(1), m.group(2)
            name = name.replace('未经许可，不得转载', '')      # 页内水印串
            # 数字单元只取 1–3 位（6 位学校代码已单独捕获，排除）
            nums = [t for x, t in sorted(cells) if re.fullmatch(r'\d{1,3}', t)]
            if len(nums) != 10:            # 9 名额 + 总计
                continue
            quota = nums
            total = int(quota[-1])
            if sum(int(v) for v in quota[:-1]) != total:
                print(f'  ⚠ 总计校验失败: {name} {quota}')
            rows.append((pno + 1, code, name, quota))
    return rows

if __name__ == '__main__':
    rows = extract()
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['year', 'junior_high_school_code', 'junior_high_school',
                    'senior_high_school_short', 'senior_high_school',
                    'senior_high_school_code', 'senior_high_school_tier', 'quota',
                    'source_doc', 'source_page'])
        for pno, code, name, quota in rows:
            for i, (short, full, tier) in enumerate(COLS):
                w.writerow([2026, code, name, short, full, '', tier, quota[i],
                            SOURCE, pno])
    print(f'写出 {OUT}：{len(rows)} 所初中 × 9 所高中 = {len(rows)*9} 行')
    for pno, code, name, quota in rows[:3]:
        print(' ', code, name, quota)
