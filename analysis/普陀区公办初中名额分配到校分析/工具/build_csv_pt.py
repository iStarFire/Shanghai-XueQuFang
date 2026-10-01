# -*- coding: utf-8 -*-
"""普陀区「名额分配到校最低分数线」五年长表落盘（2022–2026）。

schema 与徐汇一致（含 high_school_tier 区属/委属），source_page 记录物理页码。
高中「区属/委属」分类依据 2026 计划公示表头（委属：华二/上中/复附/交附/上师大；
区属：华二普陀/曹杨二中/晋元/宜川），与分数线表 9 所高中完全一致。
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scores_pt import extract_year

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D_SCHOOL = f"{BASE}/data/普陀区/学校"
OUT = f"{D_SCHOOL}/名额到校最低分数线-普陀区-2022-2026.csv"
YEARS = [2022, 2023, 2024, 2025, 2026]

TIER = {
    '华东师范大学第二附属中学': '委属',
    '上海市上海中学': '委属',
    '复旦大学附属中学': '委属',
    '上海交通大学附属中学': '委属',
    '上海师范大学附属中学': '委属',
    '华东师范大学第二附属中学（普陀校区）': '区属',
    '上海市曹杨第二中学': '区属',
    '上海市晋元高级中学': '区属',
    '上海市宜川中学': '区属',
}
FULL = 800.0

def main():
    all_rows = []
    for y in YEARS:
        src = f'【普陀】【{y}】名额到校最低分数线.pdf'
        rows = extract_year(y, f'{D_SCHOOL}/{src}')
        for pno, v in rows:
            tier = TIER.get(v[1], '')
            if not tier:
                print(f'  ⚠ 未知高中（学年 {y}）: {v[1]!r}')
            all_rows.append([y, '普陀区', v[0], '', v[1], '', tier,
                             v[2], FULL, '', '', ''] + v[3:] + [src, pno])
        print(f'{y}: {len(rows)} 行')
    cols = ['year', 'district', 'junior_high_school', 'junior_high_school_code',
            'senior_high_school', 'senior_high_school_code', 'high_school_tier',
            'min_score', 'score_full_mark', 'score_rate', 'is_tie_privilege',
            'comprehensive_eval', 'last_chinese_math_english', 'last_math',
            'last_chinese', 'last_comprehensive_test', 'source_doc', 'source_page']
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in all_rows:
            r[9] = f'{float(r[7])/FULL:.6f}' if r[7] else ''
            w.writerow(r)
    print(f'写出 {OUT}：{len(all_rows)} 行')

if __name__ == '__main__':
    main()
