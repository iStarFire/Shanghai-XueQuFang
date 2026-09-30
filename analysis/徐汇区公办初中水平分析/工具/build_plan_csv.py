"""生成「名额到校招生计划」长表的 2022–2024 部分（文本解码年份）。

2026-09-30 修订：`source_page` 原先写的是 **PDF 对象号**（2022 得到 `6`/`14`、
2023 得到 `6`、2024 得到 `8`），不是页码，与分数线长表的同名列为真实页码不一致。
改为用 `page_texts` 的返回顺序换算真实页码（该顺序已逐份核对与 `/Kids` 页序相同）。

> 2025 / 2026 两年是扫描件，只能读图，其行由截图转录另行合并进
> `名额到校计划-徐汇区-2022-2026.csv`，`source_page` 记为 `截图`；
> 2025 的委属 5 列未转录，`source_page` 留空。
> 本脚本不产出最终文件，只产出 2022–2024 部分。
"""
import sys, csv, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import extract_plan
from ex3 import page_texts

D = "/Users/ivan/workspace/github/Shanghai-XueQuFang/data/徐汇区/学校"
HS = {
 '042001': ('上海市第二中学', '区属'),
 '042002': ('上海市第二中学（梅陇校区）', '区属'),
 '042008': ('上海市南洋模范中学', '区属'),
 '042032': ('上海市上海中学', '委属'),
 '042035': ('上海市位育中学', '区属'),
 '042036': ('复旦大学附属中学徐汇分校', '区属'),
 '043015': ('上海市南洋中学', '区属'),
 '102056': ('上海交通大学附属中学', '委属'),
 '102057': ('复旦大学附属中学', '委属'),
 '152003': ('华东师范大学第二附属中学', '委属'),
 '152006': ('上海师范大学附属中学', '委属'),
}

if __name__ == '__main__':
    out = []
    for year in (2022, 2023, 2024):
        path = f'{D}/【徐汇】【{year}】名额到校招生计划.pdf'
        obj2page = {pn: i + 1 for i, (pn, _) in enumerate(page_texts(path))}
        centers, rows = extract_plan(path)
        codes = [c for _, c in centers]        # 表头实际顺序
        print(f'{year}: {len(rows)} 行 × {len(centers)} 列  -> 码 {codes}'
              f'  页对象→页码 {obj2page}')
        for pno, seq, code, name, vals in rows:
            for k, z in enumerate(codes):
                if k >= len(vals): break
                v = vals[k]
                q = 0 if v in ('', '0') else int(v)
                nm, tier = HS[z]
                out.append([year, '徐汇区', name, code, nm, z, tier, q,
                            f'【徐汇】【{year}】名额到校招生计划.pdf',
                            str(obj2page[pno])])
    print('合计', len(out), '行')
    f = f"{D}/名额到校计划-徐汇区-2022-2024.csv"
    with open(f, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year','district','junior_high_school','junior_high_school_code',
                    'senior_high_school','senior_high_school_code','high_school_tier',
                    'quota_plan','source_doc','source_page'])
        w.writerows(out)
    print('已写出:', f)
