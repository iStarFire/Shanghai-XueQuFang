# -*- coding: utf-8 -*-
"""普陀区「名额分配到校计划」多年份提取与合并落盘（2022–2026）。

- 2022/2024/2025/2026：PDF 文本层（PyMuPDF，表头列名按 x 位置归位）
- 2023：图片版（无文本层）——由 `plan_2023_manual.csv`（人工读图转录，另经交叉校验）并入
输出：名额到校计划-普陀区-2022-2026.csv（长表）
"""
import csv, os, re, glob
import fitz

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{BASE}/data/普陀区/学校"
OUT = f"{D}/名额到校计划-普陀区-2022-2026.csv"
YEARS_TXT = [2022, 2024, 2025, 2026]

FULL = {
    '华二': ('华东师范大学第二附属中学', '委属'),
    '上中': ('上海市上海中学', '委属'),
    '复附': ('复旦大学附属中学', '委属'),
    '交附': ('上海交通大学附属中学', '委属'),
    '上师大': ('上海师范大学附属中学', '委属'),
    '华二普陀': ('华东师范大学第二附属中学（普陀校区）', '区属'),
    '二中': ('上海市曹杨第二中学', '区属'),
    '晋元': ('上海市晋元高级中学', '区属'),
    '宜川': ('上海市宜川中学', '区属'),
}

def extract_text_year(year):
    """锚点法：以 6 位学校代码行为锚，数字按 y 最近归属（各年版式基线偏移不同，行聚类不可靠）。"""
    doc = fitz.open(f'{D}/【普陀】【{year}】名额到校计划.pdf')
    rows = []
    for pno in range(len(doc)):
        pg = doc[pno]
        H = pg.rect.height
        words = [(H - w[1], w[0], w[4]) for w in pg.get_text('words')
                 if w[4].strip() and w[0] >= 0 and '转载' not in w[4] and '许可' not in w[4]]
        codes = [(y, x, t) for y, x, t in words if re.fullmatch(r'\d{6}', t) and x < 120]
        nums = [(y, x, int(t)) for y, x, t in words if re.fullmatch(r'\d{1,3}', t) and x > 300]
        names = [(y, x, t) for y, x, t in words
                 if x < 300 and not re.fullmatch(r'\d{1,6}', t) and len(t) >= 2]
        heads = {}
        for y, x, t in words:
            if t in FULL and x > 300:
                heads[t] = x
        for cy, cx, code in codes:
            cand = [(y, x, t) for y, x, t in names if abs(y - cy) <= 8]
            name = max(cand, key=lambda p: len(p[2]))[2] if cand else ''
            name = re.sub(r'\d+$', '', name)
            cols = {}
            for ny, nx, v in nums:
                if abs(ny - cy) > 8:
                    continue
                best = min(heads, key=lambda h: abs(heads[h] - nx))
                if abs(heads[best] - nx) <= 22:
                    cols[best] = v
                else:
                    cols['总计'] = v
            if sum(cols.get(k, 0) for k in FULL) != cols.get('总计', -1):
                print(f'  ⚠ {year} 总计不符: {code} {name} {cols}')
            rows.append((pno + 1, code, name, cols))
    return rows

def main():
    out = []
    report = []
    for year in YEARS_TXT:
        rows = extract_text_year(year)
        report.append((year, len(rows)))
        for pno, code, name, cols in rows:
            total = cols.get('总计', sum(v for k, v in cols.items() if k != '总计'))
            s = sum(cols.get(k, 0) for k in FULL)
            if s != total:
                print(f'  ⚠ {year} 总计不符: {code} {name} cols={cols} 合计={s} 总计={total}')
            for short, (full, tier) in FULL.items():
                out.append([year, code, name, short, full, '', tier,
                            cols.get(short, 0),
                            f'【普陀】【{year}】名额到校计划.pdf' if year != 2023 else
                            '【普陀】【2023】名额到校计划.pdf（人工读图转录）', pno])
    # ---- 并入 2023（人工读图转录）----
    man = list(csv.DictReader(open(f'{D}/名额到校计划-普陀区-2023-人工转录.csv', encoding='utf-8-sig')))
    short_of = {'huayer': '华二', 'shangzhong': '上中', 'fufu': '复附', 'jiaofu': '交附',
                'shangshida': '上师大', 'huayer_putuo': '华二普陀', 'erzhong': '二中',
                'jinyuan': '晋元', 'yichuan': '宜川'}
    for r in man:
        vals = {short_of[k]: int(r[k]) for k in short_of}
        if sum(vals.values()) != int(r['total']):
            print(f'  ⚠ 2023 人工转录总计不符: {r["junior_high_school"]} {vals} != {r["total"]}')
        for short, (full, tier) in FULL.items():
            out.append([2023, r['junior_high_school_code'], r['junior_high_school'],
                        short, full, '', tier, vals[short],
                        '【普陀】【2023】名额到校计划.pdf（人工读图转录，'
                        '转录文件：名额到校计划-普陀区-2023-人工转录.csv）', ''])
    print('文本版年份行数:', report, '| 2023 人工转录行数:', len(man))
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['year', 'junior_high_school_code', 'junior_high_school',
                    'senior_high_school_short', 'senior_high_school',
                    'senior_high_school_code', 'senior_high_school_tier', 'quota',
                    'source_doc', 'source_page'])
        w.writerows(out)
    print(f'写出 {OUT}: {len(out)} 行（暂缺 2023，待人工转录并入）')

if __name__ == '__main__':
    main()
