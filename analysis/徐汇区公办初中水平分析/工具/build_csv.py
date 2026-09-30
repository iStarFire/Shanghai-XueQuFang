"""生成「名额到校最低分数线」长表。

2026-09-30 修订：原版丢掉了 extract_year 返回的页码，且从未写出
junior_high_school_code / senior_high_school_code / high_school_tier /
source_doc / source_page 五列，与 design.md §3.2 不符、无法满足
「每格可回源到 PDF + 页码」的验收标准。本版补齐。

学校编号与区属/委属分层由计划长表按 (year, 校名) 联结得到——
分数线 PDF 本身不含学校编号，这是唯一合法来源；联结键由
`初中校名别名表-徐汇区.csv` 保证唯一。
"""
import sys, csv, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scores import extract_year, NAMES
from ex3 import page_texts

D = "/Users/ivan/workspace/github/Shanghai-XueQuFang/data/徐汇区/学校"
YEARS = [2022, 2023, 2024, 2025, 2026]
SUFFIX = re.compile(r'(中学|学校|学校南校|校)$')
# 上海中考满分（含综合素质评价 50 分），2022–2026 五年一致
FULL_MARK = {y: 800 for y in YEARS}
PLAN = f"{D}/名额到校计划-徐汇区-2022-2026.csv"


def load():
    """返回 {year: [(page, 初中名, 高中名, [字段值...]), ...]}，page 为 1 起页序。"""
    data = {}
    for y in YEARS:
        path = f"{D}/【徐汇】【{y}】名额到校最低分数线.pdf"
        # extract_year 的 pno 是 PDF 对象号；page_texts 的返回顺序已核实
        # 与 /Kids 真实页序一致，故用列表下标 +1 换算为页码
        order = [pn for pn, _ in page_texts(path)]
        rows = extract_year(y, path)
        data[y] = [(order.index(pno) + 1, v[0], v[1], v) for pno, v in rows]
    return data


def repair(data):
    """修复 2024 年「华东理工大学附属中学」等超长校名被矢量化截断的问题。"""
    good = set()
    for y in YEARS:
        for _pg, jh, _hh, v in data[y]:
            if len(jh) >= 6 and SUFFIX.search(jh):
                good.add(jh)
    fixes = {}
    for y in YEARS:
        out = []
        for pg, jh, hh, v in data[y]:
            if jh not in good:
                cand = sorted(n for n in good if n.startswith(jh))
                if len(cand) == 1:
                    fixes[jh] = cand[0]
                    v[0] = cand[0]
            out.append((pg, v[0], hh, v))
        data[y] = out
    return fixes


def code_maps():
    """从计划长表建立 (year, 校名) -> 编号 / 分层 的映射。"""
    jh_code, hh_code, hh_tier = {}, {}, {}
    for r in csv.DictReader(open(PLAN, encoding='utf-8-sig')):
        y = r['year']
        jh_code.setdefault((y, r['junior_high_school']), r['junior_high_school_code'])
        hh_code.setdefault((y, r['senior_high_school']), r['senior_high_school_code'])
        hh_tier.setdefault((y, r['senior_high_school']), r['high_school_tier'])
    return jh_code, hh_code, hh_tier


if __name__ == '__main__':
    data = load()
    total = sum(len(data[y]) for y in YEARS)
    print(f'修复前合计 {total} 行')
    fixes = repair(data)
    print(f'前缀修复 {len(fixes)} 处:', fixes)

    jh_code, hh_code, hh_tier = code_maps()
    miss_jh, miss_hh = [], []

    for y in YEARS:
        rows = data[y]
        print(f'{y}: {len(rows)} 行, {len(set(r[1] for r in rows))} 初中, '
              f'{len(set(r[2] for r in rows))} 高中')
        bad = [n for n in set(r[1] for r in rows)
               if len(n) < 6 or not SUFFIX.search(n)]
        if bad:
            print('   仍可疑:', bad)

    FIELDS = NAMES[2025]          # 9 列统一 schema
    # score_full_mark 逐年登记（design.md §3.2）；上海中考 2022–2026 均为
    # 语数外 450 + 综合测试 150 + 其他科目 150 + 综合素质评价 50 = 800
    HEAD = (['year', 'district', 'junior_high_school', 'junior_high_school_code',
             'senior_high_school', 'senior_high_school_code', 'high_school_tier',
             'min_score', 'score_full_mark', 'score_rate']
            + [f for f in FIELDS if f not in ('junior_high_school',
                                              'senior_high_school', 'min_score')]
            + ['source_doc', 'source_page'])
    TAIL = [f for f in FIELDS if f not in ('junior_high_school',
                                           'senior_high_school', 'min_score')]
    out = f"{D}/名额到校最低分数线-徐汇区-2022-2026.csv"
    n = 0
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        for y in YEARS:
            doc = f'【徐汇】【{y}】名额到校最低分数线.pdf'
            for pg, jh, hh, v in data[y]:
                rec = dict(zip(NAMES[y], v))      # 按字段名对齐，不按位置
                jc = jh_code.get((str(y), jh))
                hc = hh_code.get((str(y), hh))
                ht = hh_tier.get((str(y), hh))
                if jc is None:
                    miss_jh.append((y, jh))
                if hc is None:
                    miss_hh.append((y, hh))
                ms = rec.get('min_score', '')
                full = FULL_MARK[y]
                rate = f'{float(ms) / full:.6f}' if ms else ''
                w.writerow([y, '徐汇区', jh, jc or '', hh, hc or '', ht or '',
                            ms, full, rate]
                           + [rec.get(k, '') for k in TAIL] + [doc, pg])
                n += 1
    print(f'已写出: {out}')
    print(f'  行数 {n}  列数 {len(HEAD)}')
    print(f'  初中编号未联结 {len(set(miss_jh))} 种 {sorted(set(miss_jh))[:5]}')
    print(f'  高中编号未联结 {len(set(miss_hh))} 种 {sorted(set(miss_hh))[:5]}')
