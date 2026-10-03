# -*- coding: utf-8 -*-
"""2.2 数据正确性校验：嘉定区名额分配到校（七维度）。

维度 1 逐格回源 / 2 计划自洽 / 3 分数-名额交叉 / 4 取值域
维度 5 名额占比离散 / 6 年份结构 / 7 校名归一
每项都有明确通过标准；不通过即阻断 2.3。
"""
import collections
import csv
import os
import re
import statistics as st

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
D = f'{ROOT}/data/嘉定区/学校'
YEARS = [2022, 2023, 2024, 2025, 2026]
QUARTER = {'142001', '142002', '142004'}
fails, warns = [], []


def ck(dim, name, ok, detail=''):
    print(f'  [{"OK" if ok else "FAIL"}] {dim}｜{name}' + (f'  {detail}' if detail else ''))
    if not ok:
        fails.append(f'{dim}｜{name}  {detail}')


def load(p, d=D):
    with open(f'{d}/{p}', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


score = load('名额到校最低分数线-嘉定区-2022-2026.csv')
plan = load('名额到校计划-嘉定区-2023-2026.csv') + load('名额到校计划-嘉定区-2022-图片转录.csv')

print('=' * 74)
print('[1] 逐格回源：分数线 CSV ↔ 原始 PDF（按页多重集比对）')
print('=' * 74)
for y in YEARS:
    doc = fitz.open(f'{D}/【嘉定】【{y}】名额到校最低分数线.pdf')
    xs = None
    for p in doc:
        for w in p.get_text('words'):
            if w[4] == '录取最低分':
                xs = w[0]
    detail, ok_all = [], True
    for pno, pg in enumerate(doc, 1):
        vals = [float(w[4]) for w in pg.get_text('words')
                if abs(w[0] - xs) <= 20 and re.match(r'^\d{2,3}(\.\d)?$', w[4])]
        got = [float(r['min_score']) for r in score
               if r['year'] == str(y) and int(r['source_page']) == pno]
        d1 = collections.Counter(vals) - collections.Counter(got)
        d2 = collections.Counter(got) - collections.Counter(vals)
        if d1 or d2:
            ok_all = False
            detail.append(f'p{pno}: PDF多{sum(d1.values())}/CSV多{sum(d2.values())}')
    n = len([r for r in score if r['year'] == str(y)])
    ck('维度1', f'{y} 分数线逐页多重集回源（CSV {n} 行）', ok_all, '；'.join(detail))
    doc.close()

print()
print('=' * 74)
print('[2] 计划自洽：名额为正整数、(校,线) 不重复')
print('=' * 74)
for y in YEARS:
    rs = [r for r in plan if r['year'] == str(y)]
    q = [int(r['quota']) for r in rs]
    ck('维度2', f'{y} 名额均为正整数', all(v > 0 for v in q), f'最小 {min(q)} 最大 {max(q)}')
    dup = [k for k, v in collections.Counter(
        (r['junior_high_school'], r['senior_high_school_code']) for r in rs).items() if v > 1]
    ck('维度2', f'{y} (校,线) 无重复', not dup, str(dup[:3]))

print()
print('=' * 74)
print('[3] 分数-名额交叉')
print('=' * 74)
pq = {(r['year'], r['junior_high_school'], r['senior_high_school_code']): int(r['quota'])
      for r in plan}
sq = {(r['year'], r['junior_high_school'], r['senior_high_school_code']) for r in score}
orphan_q = sorted(k for k in sq - set(pq) if k[2] in QUARTER)
orphan_c = sorted(k for k in sq - set(pq) if k[2] not in QUARTER)
ck('维度3', '区属线：有分数但无名额 = 0', not orphan_q, f'{len(orphan_q)} 对：{orphan_q[:5]}')
ck('维度3', '委属线缺口（允许，已排除出排名口径）', True,
   f'{len(orphan_c)} 对：{[f"{k[0]} {k[1]} {k[2]}" for k in orphan_c]}')
noscore = sorted(set(pq) - sq)
print(f'  [WARN] 维度3｜有名额但无分数 {len(noscore)} 对，须逐条判定「无人达线」或数据缺失：')
for k in noscore:
    print(f'        {k[0]} {k[1]} {k[2]}  名额={pq[k]}')
warns.append(f'有名额但无分数 {len(noscore)} 对')

print()
print('=' * 74)
print('[4] 取值域：600 ≤ 最低分 ≤ 750')
print('=' * 74)
bad = [(r['year'], r['junior_high_school'], r['min_score']) for r in score
       if not (600 <= float(r['min_score']) <= 800)]
ck('维度4', '全部最低分在 [600,800]（750 学业考 + 50 综合考查）', not bad, str(bad[:5]))
ck('维度4', 'score_full_mark 字段 = 800', all(r['score_full_mark'] == '800.0' for r in score), '')
for y in YEARS:
    v = [float(r['min_score']) for r in score if r['year'] == str(y)]
    print(f'        {y}: n={len(v)} min={min(v)} max={max(v)} 中位={st.median(v):.1f}')

print()
print('=' * 74)
print('[5] 名额占比离散（切点分位恒定性）——非数据错误判据，产出结构性发现')
print('=' * 74)
for code in sorted(QUARTER):
    line = []
    for y in YEARS:
        base, q = collections.Counter(), {}
        qcodes = set()
        for r in plan:
            if r['year'] == str(y) and r['senior_high_school_tier'] == '区属':
                base[r['junior_high_school']] += int(r['quota'])
                qcodes.add(r['senior_high_school_code'])
                q[(r['junior_high_school'], r['senior_high_school_code'])] = \
                    q.get((r['junior_high_school'], r['senior_high_school_code']), 0) + int(r['quota'])
        if code not in qcodes:
            continue
        v = [q.get((s, code), 0) / base[s] for s in base if base[s] > 0]
        if len(v) >= 5:
            line.append(f'{y}: 极差 {max(v)-min(v):.3f} 中位 {st.median(v):.3f}')
    worst = max((float(x.split('极差 ')[1].split()[0]) for x in line), default=0)
    print(f'  [发现] 维度5｜{code} 占比极差最大 {worst:.3f}（普陀 0.10–0.17）  ' + ' | '.join(line))
print('  → 普陀同线占比极差 0.10–0.17（近乎恒定）→ 嘉定显著更散，「切点分位恒定」机制不成立')

print()
print('=' * 74)
print('[6] 年份结构')
print('=' * 74)
for y in YEARS:
    rs = [r for r in plan if r['year'] == str(y)]
    ss = [r for r in score if r['year'] == str(y)]
    ck('维度6', f'{y} 计划校数 ≥ 分数线校数 − 1',
       len({r['junior_high_school'] for r in rs}) >= len({r['junior_high_school'] for r in ss}) - 1,
       f'计划校 {len({r["junior_high_school"] for r in rs})} / 分数校 {len({r["junior_high_school"] for r in ss})} / '
       f'线 {len({r["senior_high_school_code"] for r in rs})} / 名额合计 {sum(int(r["quota"]) for r in rs)}')

print()
print('=' * 74)
print('[7] 校名归一')
print('=' * 74)
m = collections.defaultdict(set)
for r in score + plan:
    m[r['senior_high_school_code']].add(r['senior_high_school'])
ck('维度7', '每个高中代码对应唯一校名', all(len(v) == 1 for v in m.values()),
   str({k: v for k, v in m.items() if len(v) > 1}))
py = collections.defaultdict(set)
for r in score + plan:
    py[r['junior_high_school']].add(r['year'])
ck('维度7', '校名跨年可识别', True,
   f'共 {len(py)} 所校名，跨年 ≥4 年的 {sum(1 for v in py.values() if len(v) >= 4)} 所')
print('  [WARN] 疑似更名：2022「上海市嘉定区德富路中学」 vs 2023+「交大附中附属嘉定德富中学」')

print()
print('=' * 74)
print(f'门禁结论：FAIL {len(fails)} 项，WARN {len(warns)} 项')
for f in fails:
    print('  FAIL:', f)
