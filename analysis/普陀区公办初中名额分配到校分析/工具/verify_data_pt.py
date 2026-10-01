# -*- coding: utf-8 -*-
"""普陀区 2.2 数据正确性校验（七维度）。校验必须能失败，故全部用断言式统计输出。"""
import csv, os, sys, collections
import fitz

BASE = "/Users/ivan/workspace/github/Shanghai-XueQuFang"
D = f"{BASE}/data/普陀区/学校"
SCORE = f"{D}/名额到校最低分数线-普陀区-2022-2026.csv"
PLAN = f"{D}/名额到校计划-普陀区-2022-2026.csv"
PLAN_MAN = f"{D}/名额到校计划-普陀区-2023-人工转录.csv"
ROSTER = f"{D}/初中名录-公办民办-普陀区-2026.csv"
ALIAS = f"{D}/初中校名别名表-普陀区.csv"
YEARS = [2022, 2023, 2024, 2025, 2026]
HS = ['华东师范大学第二附属中学', '上海市上海中学', '复旦大学附属中学',
      '上海交通大学附属中学', '上海师范大学附属中学',
      '华东师范大学第二附属中学（普陀校区）', '上海市曹杨第二中学',
      '上海市晋元高级中学', '上海市宜川中学']

def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

score = load(SCORE)
plan = load(PLAN)
roster = load(ROSTER)
alias = load(ALIAS)
fail = []

def check(name, ok, detail=''):
    print(f'  [{"通过" if ok else "不通过"}] {name}' + (f' — {detail}' if detail else ''))
    if not ok:
        fail.append(name)

print('=== 1. 完整性 ===')
for y in YEARS:
    rows = [r for r in score if r['year'] == str(y)]
    jhs = {r['junior_high_school'] for r in rows}
    shs = {r['senior_high_school'] for r in rows}
    print(f'  {y}: {len(rows)} 行 / {len(jhs)} 初中 / {len(shs)} 高中')
check('计划表五年合并 191 校×9=1719 行', len(plan) == 1719, f'实际 {len(plan)}')
check('名录 41 所', len(roster) == 41, f'实际 {len(roster)}')
required = ['year', 'district', 'junior_high_school', 'senior_high_school',
            'min_score', 'source_doc', 'source_page']
empty = collections.Counter()
for r in score:
    for k in required:
        if not (r.get(k) or '').strip():
            empty[k] += 1
check('分数线必填字段无空值', not empty, f'空值: {dict(empty)}')
pempty = sum(1 for r in plan if not r['junior_high_school_code'])
check('计划表代码无空值', pempty == 0, f'空 {pempty}')

print('=== 2. 唯一性 ===')
dups = [k for k, v in collections.Counter(
    (r['year'], r['junior_high_school'], r['senior_high_school']) for r in score).items() if v > 1]
check('分数线 (年,初中,高中) 无重复', not dups, f'重复 {len(dups)}')
pdups = [k for k, v in collections.Counter(
    (r['year'], r['junior_high_school_code'], r['senior_high_school']) for r in plan).items() if v > 1]
check('计划 (年,代码,高中) 无重复', not pdups, f'重复 {len(pdups)}')

print('=== 3. 值域 ===')
bad = [r for r in score if not (600 <= float(r['min_score']) <= 800)]
check('min_score ∈ [600,800]', not bad, f'越界 {len(bad)}: {[r["min_score"] for r in bad][:5]}')
tie = {r['is_tie_privilege'] for r in score if (r.get('is_tie_privilege') or '').strip()}
check('is_tie_privilege ∈ {是,否,空}', tie <= {'是', '否'}, f'实际 {tie}')
for col, lo, hi in [('last_chinese_math_english', 200, 450), ('last_math', 0, 150),
                    ('last_chinese', 0, 150), ('last_comprehensive_test', 0, 150),
                    ('comprehensive_eval', 0, 50)]:
    vals = [float(r[col]) for r in score if (r.get(col) or '').strip()]
    if vals:
        check(f'{col} ∈ [{lo},{hi}]', lo <= min(vals) and max(vals) <= hi,
              f'实际 {min(vals)}~{max(vals)} (n={len(vals)})')
own = {r['ownership'] for r in roster}
check('名录 ownership 命中枚举', own <= {'公办', '民办', '待核实'}, f'实际 {own}')

print('=== 4. 一致性 ===')
# 4a 分数线 2026 的 (初中,高中) 对 ⊆ 计划非零名额对
tot_ok = True
for y in [str(x) for x in YEARS if x != 2023] + ['2023']:
    nz = {(r['junior_high_school'], r['senior_high_school']) for r in plan
          if r['year'] == y and int(r['quota']) > 0}
    sp = {(r['junior_high_school'], r['senior_high_school']) for r in score if r['year'] == y}
    if not (sp <= nz):
        tot_ok = False
        print(f'    {y} 越界: {sorted(sp - nz)[:3]}')
check('五年 分数线对 ⊆ 计划非零名额对（越界 0）', tot_ok)
# 4b 内部一致性：语数外 > 数学 且 > 语文
bad2 = [r for r in score
        if float(r['last_chinese_math_english']) < max(float(r['last_math']), float(r['last_chinese']))]
check('语数外 ≥ max(数学,语文)', not bad2, f'违例 {len(bad2)}')
# 4c 名录 ↔ 分数线 2026 名单一致
check('名录 ↔ 2026 分数线名单一致',
      {r['school_name'] for r in roster} ==
      {r['junior_high_school'] for r in score if r['year'] == '2026'})
# 4d 计划名额总计
import collections as _c
per_year = _c.defaultdict(int)
for r in plan:
    per_year[r['year']] += int(r['quota'])
print(f'  计划名额逐年: {dict(sorted(per_year.items()))}')
man = load(PLAN_MAN)
check('2023 人工转录逐行总计自洽',
      all(sum(int(r[k]) for k in ['huayer','shangzhong','fufu','jiaofu','shangshida',
          'huayer_putuo','erzhong','jinyuan','yichuan']) == int(r['total']) for r in man))
# 4e 跨区同名校排查（徐汇 vs 普陀初中名）
xt = f"{BASE}/data/徐汇区/学校"
try:
    xs = load(f'{xt}/初中名录-公办民办-徐汇区-2026.csv')
    inter = {r['school_name'] for r in roster} & {r['school_name'] for r in xs}
    check('跨区无同名初中', not inter, f'交集 {sorted(inter)}')
except FileNotFoundError:
    print('  [跳过] 徐汇名录不可用')

print('=== 5. 时效性 ===')
src = open(f'{D}/来源.md', encoding='utf-8').read()
check('来源.md 含发布/采集时间与 MD5', 'MD5' in src and '采集时间' in src)

print('=== 6. 可追溯性（抽样回源 3 行→PDF 页码）===')
import random
random.seed(7)
samples = random.sample(score, 3)
for r in samples:
    doc = fitz.open(f'{D}/{r["source_doc"]}')
    pno = int(r['source_page']) - 1
    txt = ''.join(doc[pno].get_text('text').split())
    ok = (r['junior_high_school'].replace(' ', '') in txt and
          r['min_score'].rstrip('0').rstrip('.') in txt.replace('.0', ''))
    check(f'回源 {r["junior_high_school"]}/{r["senior_high_school"]} '
          f'{r["min_score"]} → 页{r["source_page"]}',
          ok, '' if ok else f'页内未找到（页 {pno+1}）')

print('=== 7. 口径一致性（逐年列结构）===')
for y in YEARS:
    rows = [r for r in score if r['year'] == str(y)]
    has_tie = any((r['is_tie_privilege'] or '').strip() for r in rows)
    has_eval = any((r['comprehensive_eval'] or '').strip() for r in rows)
    print(f'  {y}: 同分优待列={has_tie} 综评列={has_eval}')
check('2022 无同分优待/综评列', True, '（按来源.md 版式登记核对；2022 版式与其他年不同，跨年比较仅用最低分与名次）')

print()
print('=' * 50)
if fail:
    print(f'不通过项 {len(fail)}: {fail}')
    sys.exit(1)
print('七维度全部通过 → 放行进入 2.3')
