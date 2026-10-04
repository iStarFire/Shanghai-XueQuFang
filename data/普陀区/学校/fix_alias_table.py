"""更新普陀初中校名别名表：写入 1.1 官方核实结论（4 校）。

核实来源（均为公开官方/主流媒体，2026-10-04 检索）：

1. 上海市光新学校（075044）
   性质：**暂停招生**（不是撤并）
   依据：《普陀公办招生变，速看》（2024 年普陀区公办初中招生调整）
   「初中规模变化不大，但光新学校今年初中部将暂停招生。」
   旁证：百度百科载光新学校为公办九年一贯制（2006 年由光新中学 + 光新二小合并组建），
   现址石泉路 39 号 —— **学校仍存在**，仅初中部停招。
   数据吻合：2024 年仍有毕业班出分数线，2025 年毕业班走完即无数据。

2. 上海市武宁中学（071042）
   性质：**并入同济大学第二附属中学**
   依据：上海市普陀区发改委《关于印发〈普陀区 2022 年上半年国民经济和社会发展计划
   执行情况〉的通知》（shpt.gov.cn，**2022-08-22**）
   「优化教育资源布局，恒德小学更名为新普陀小学西校，**武宁中学并入同济二附中**」；
   知乎（2022-02-21）佐证「武宁中学被同济二附中合并」。
   旁证：百度百科/上观新闻 —— 武宁中学 2024 年完成异地改扩建、迁东新路 186 号新校区，
   **学校本身仍存在**，是初中部并入。
   ⚠️ **不归并数据**：2022 年武宁与同济二附中**同年各有独立名额与分数线**，
   若把武宁 2022 归入同济二附中会造成该年重复计量。故武宁按 `exited` 处理。

3. 上海市兴陇中学（071048）
   性质：**2023 年 3 月更名**为「上海市曹杨第二中学附属实验中学」
   依据：界面新闻 / 今日头条（2023-03-25~27）「上海市曹杨二中教育集团高质量发展推进会
   暨**上海市兴陇中学更名揭牌仪式**举行，副区长王珏出席并致辞」。
   旁证：百度文库「前身为兴陇中学，2023 年更名并加入曹杨二中教育集团」。
   与数据一致：计划表中 071048 的年份严格互补（兴陇仅 2022、曹二实验 2023–2026），
   同一代码 + 年份互补 + 官方更名揭牌 ⇒ **改名成立**，已由 `build_v3.py` 的 ALIAS 归并。

4. 上海市晋元高级中学附属学校西校（075083）—— **本次新增行**
   性质：**非独立计量**，2022 年计划表中与晋元附校（075069，上海市晋元高级中学附属学校）**同一行**
   依据：【普陀】【2022】名额到校计划.pdf 第 2 页文本层 L52–L65
   `075069` / `075083` / 两个校名 / **仅一组名额（总计 49）**；
   其余 33 组均为「1 代码 + 1 校名 + 10 数字」。
   佐证：2022 年分数线表 35 所计划校中唯独缺西校（34 所）。
   量化：原 CSV 把该行名额重复记两遍，2022 合计 660 = PDF 权威值 611 + 49。
"""
import csv
import io
from pathlib import Path

P = Path('初中校名别名表-普陀区.csv')
with P.open(encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
old_cols = list(rows[0].keys())
assert 'evidence' not in old_cols, 'evidence 列已存在，本脚本不应重复执行'

COLS = old_cols + ['evidence']

# ---- 结论表：canonical_name -> (status, evidence, remark) ----
CONCL = {
    '上海市光新学校': (
        '暂停招生',
        'external',
        '2024 年普陀区公办初中招生调整「光新学校今年初中部将暂停招生」；'
        '学校仍存在（公办九年一贯制，现址石泉路 39 号）。'
        '2024 年仍有毕业班出分数线，2025 年毕业班走完即无数据。**不是撤并**。',
    ),
    '上海市武宁中学': (
        '已并入',
        'external',
        '普陀区发改委 2022-08-22 文件「武宁中学并入同济二附中」；'
        '学校仍存在（2024 年迁东新路 186 号新校区），系初中部并入。'
        '⚠️ 不归并数据：2022 年两校同年各有独立名额与分数线，归并会造成重复计量。',
    ),
    '上海市兴陇中学': (
        '已归并',
        'external',
        '2023 年 3 月更名揭牌仪式（副区长王珏出席），改为「上海市曹杨第二中学附属实验中学」，'
        '并入曹杨二中教育集团。与计划表 071048 年份严格互补一致；'
        '已由 build_v3.py 的 ALIAS 归并为同一行 5 年数据。',
    ),
    '上海市晋元高级中学附属学校西校': (
        '非独立计量',
        'pdf_same_row',
        '2022 年计划表该行含 075069+075083 两个代码、两个校名，但**仅一组名额（总计 49）**；'
        '2022 年分数线表唯独缺此校。已加 merged_into=075069 标注并在 build_v3.py 排除，'
        '修正 2022 名额合计 660 → 611（= PDF 权威值）。',
    ),
}

# ---- 内存完成全部拼装与断言 ----
idx = {r['canonical_name']: r for r in rows}
# 西校本就不在别名表中（此前一直缺失），走下方新增路径，不参与存在性断言
NEW_ROWS = {'上海市晋元高级中学附属学校西校'}
missing = [k for k in CONCL if k not in idx and k not in NEW_ROWS]
assert not missing, f'别名表缺少这些行，需先补：{missing}'
assert len(missing) == 0, '原有三校必须在表中'

for r in rows:
    if r['canonical_name'] in CONCL:
        st, ev, rm = CONCL[r['canonical_name']]
        r['status'] = st
        r['evidence'] = ev
        r['remark'] = rm
    else:
        r['evidence'] = ''

# 西校若不在表中则新增（按 code 排序插入）
if NEW_ROWS & set(CONCL) - set(idx):
    st, ev, rm = CONCL['上海市晋元高级中学附属学校西校']
    rows.append({
        'school_code': '075083', 'canonical_name': '上海市晋元高级中学附属学校西校',
        'alias_name': '', 'status': st, 'evidence': ev, 'remark': rm,
        'source_doc': '名额到校计划-普陀区-2022-2026.csv',
    })

# 断言 1：三个原「待核实」行都不再是待核实
for nm in ('上海市光新学校', '上海市武宁中学', '上海市兴陇中学'):
    got = [r for r in rows if r['canonical_name'] == nm][0]
    assert '待核实' not in got['status'], f'{nm} 仍为待核实：{got["status"]}'
    assert got['evidence'] == 'external', f'{nm} 缺 external 证据'

# 断言 2：表内不再有任何「不得猜测映射」的过期判断
bad = [r['canonical_name'] for r in rows if '不得猜测映射' in r.get('remark', '')]
assert not bad, f'仍有过期的「不得猜测映射」：{bad}'

# 断言 3：西校行存在且标注非独立计量
xc = [r for r in rows if r['canonical_name'] == '上海市晋元高级中学附属学校西校']
assert len(xc) == 1 and xc[0]['evidence'] == 'pdf_same_row', '西校行标注有误'

# 断言 4：在用行数不变（41 所）
alive = sum(1 for r in rows if r['status'] == '在用')
assert alive == 41, f'在用行数变为 {alive}，应为 41'

buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=COLS, lineterminator='\r\n', extrasaction='ignore')
w.writeheader()
w.writerows(rows)
out = buf.getvalue().encode('utf-8-sig')
assert out.count(b'\n') == len(rows) + 1, '输出行数异常'
assert len(out) > 2000, '输出过小，疑似生成失败'

P.write_bytes(out)
print(f'别名表已更新：{len(rows)} 行 × {len(COLS)} 列（新增 evidence 列）')
print(f'  在用 {alive} 所；结论化 4 所（光新=暂停招生 / 武宁=已并入 / 兴陇=已归并 / 西校=非独立计量）')
print('  表内已无「不得猜测映射」的过期判断')
