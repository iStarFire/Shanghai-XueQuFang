"""在计划表 CSV 中标注「晋元西校并入晋元附校」，修正 2022 年名额重复计量。

依据（`【普陀】【2022】名额到校计划.pdf` 第 2 页，PyMuPDF 文本层 L52-L65）：
    '075069'
    '075083'
    '上海市晋元高级中学附属学校'
    '上海市晋元高级中学附属学校西校'
    '1' '0' '0' '0' '0' | '4' '15' '14' '15' | '49'
即该行含**两个学校代码、两个校名、但只有一组名额（总计 49）**。
对比其余 33 组均为「1 代码 + 1 校名 + 10 个数字」，可确认 49 是两校合计。

原 CSV 把这 10 个数字各写了一遍给 075069 与 075083，导致 2022 年
名额合计 660 = PDF 权威值 611 + 重复的 49。

分数线表 2022 年 35 所计划校中唯独缺西校（34 所），佐证西校不独立计量。
"""
import csv
import io
from pathlib import Path

P = Path('名额到校计划-普陀区-2022-2026.csv')
PDF_TOTAL_2022 = 611      # PDF 34 组「总计」列求和（晋元组按 1 组计）
XICODE = '075083'
MAINCODE = '075069'

with P.open(encoding='utf-8-sig') as _f:
    rows = list(csv.DictReader(_f))
old_cols = list(rows[0].keys())
assert 'merged_into' not in old_cols, 'merged_into 列已存在，本脚本不应重复执行'

hit = [r for r in rows if r['junior_high_school_code'] == XICODE]
assert hit, f'未找到西校（{XICODE}）行，数据结构已变'
assert {r['year'] for r in hit} == {'2022'}, \
    f'西校应仅 2022 出现，实际 {sorted({r["year"] for r in hit})}'

NOTE = ('2022 计划表该行含 075069+075083 两个代码、两个校名，'
        '名额 49 为两校合计；分数线仅以 075069 名义发布，本校不独立计量')

# ---- 全部在内存完成：加列 + 标注 + 断言 ----
new_cols = old_cols + ['merged_into', 'note']
for r in rows:
    if r['junior_high_school_code'] == XICODE:
        r['merged_into'] = MAINCODE
        r['note'] = NOTE
    else:
        r['merged_into'] = ''
        r['note'] = ''

# 断言 1：标注后 2022 名额合计仍为 660（原样保留，不删数据）
tot = sum(int(r['quota']) for r in rows if r['year'] == '2022')
assert tot == 660, f'标注改变了原始数据，2022 合计={tot}'

# 断言 2：排除西校后应等于 PDF 权威值
tot_excl = sum(int(r['quota']) for r in rows
               if r['year'] == '2022' and r['junior_high_school_code'] != XICODE)
assert tot_excl == PDF_TOTAL_2022, \
    f'排除西校后 2022 合计={tot_excl}，应等于 PDF 的 {PDF_TOTAL_2022}'

# 断言 3：列数与行数不变，仅新增 2 列
assert len(new_cols) == len(old_cols) + 2
assert len(rows) == 1719, f'行数变为 {len(rows)}'

buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=new_cols, lineterminator='\r\n')
w.writeheader()
w.writerows(rows)
out = buf.getvalue().encode('utf-8-sig')

# 落盘前最终自检：非空、行数正确
assert out.count(b'\n') == 1720, '输出行数异常'

P.write_bytes(out)
print(f'已标注 {len(hit)} 行西校为并入 {MAINCODE}（新增 merged_into / note 两列）')
print(f'2022 名额合计：原始 {tot}，排除西校后 {tot_excl} = PDF 权威值 {PDF_TOTAL_2022} ✓')
