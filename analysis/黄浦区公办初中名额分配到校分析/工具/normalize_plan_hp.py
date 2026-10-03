#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""黄浦区名额到校**计划表**校名归一。

计划表 2024 整年用高中简称（格致/卢高/华二附中…），导致：
  - 去重招生学校名 28 个，实际只有 15 所
  - 与分数线表 join 时 2024 整年接不上
  - 年初误以为「2024 新增了 12 所高中」

本脚本**按官方代码归一**，不按名字字符串匹配——简称「光明」既是高中
「上海市光明中学」的子串，也是初中「上海市光明初级中学」的子串，用名字
匹配必然误并。

三条互相独立的依据：
  A. 数据自带标记 is_placeholder_code=1（13 行，全在 2024）
  B. 同一 senior_high_school_code 下，2024 写简称、其余年份写全称
  C. 2024 计划表 PDF 头部「学校代码名称」对照表（运行时解析，用于交叉验证 B）

用法：
  python3 normalize_plan_hp.py --check    # 预览 + 交叉验证，不写盘
  python3 normalize_plan_hp.py --write    # 备份后原地改写
"""
import argparse
import csv
import os
import re
import shutil
from collections import Counter, defaultdict

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
D = f'{ROOT}/data/黄浦区/学校'
PL = f'{D}/名额到校计划-黄浦区-2022-2026.csv'
BAK = '/tmp/黄浦计划表-归一前.csv'
PDF2024 = f'{D}/【黄浦】【2024】名额到校计划.pdf'

# 初中临时代码 → (真实代码, 真实名称)
# 依据：分数线表 2024 官方写法「上海市大同初级中学（原黄浦学校）」，
# 且 015002 上海市黄浦学校 在 2022（名额 24）/2023（名额 26）存在，
# 017777 的 13 行名额合计 20 —— 规模相当，可判定为同一实体。
JUNIOR_CODE_MAP = {
    '017777': ('015002', '上海市黄浦学校'),
}


def load():
    with open(PL, encoding='utf-8-sig') as f:
        cols = next(csv.reader(f))
    with open(PL, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return rows, cols


def canonical_by_code(rows, name_key, code_key):
    """每个代码取「出现年数最多」的名称；并列时取字符数最多者。

    出现年数最多 = 规范名（2024 简称只出现 1 年，其余 4–5 年为全称）。
    """
    by_code = defaultdict(lambda: defaultdict(set))
    for r in rows:
        by_code[r[code_key]][r[name_key]].add(r['year'])
    out = {}
    for code, names in by_code.items():
        out[code] = max(names, key=lambda nm: (len(names[nm]), len(nm)))
    return out


def parse_2024_header(pdf):
    """从 2024 计划表 PDF 头部解析「学校代码名称」对照表 → {简称: 6位代码}。

    版式为名称行 + 紧邻的 (代码) 行，如「格致\\n(012001)」「大境\\n(012007 )」。
    """
    doc = fitz.open(pdf)
    txt = '\n'.join(p.get_text() for p in doc)
    doc.close()
    return {m.group(1): m.group(2)
            for m in re.finditer(r'^\s*(\S+?)\s*\n\s*\((\d{6})\s*\)\s*$', txt, re.M)}


def plan_normalize(rows):
    """返回 (新行列表, 替换清单)。不修改入参。"""
    can_s = canonical_by_code(rows, 'senior_high_school', 'senior_high_school_code')
    changes, out = [], []
    for r in rows:
        n = dict(r)
        note = r.get('note', '').strip()
        cs = can_s.get(r['senior_high_school_code'])
        if cs and r['senior_high_school'] != cs:
            changes.append({'kind': '高中简称', 'code': r['senior_high_school_code'],
                            'old': r['senior_high_school'], 'new': cs,
                            'year': r['year'], 'junior': r['junior_high_school'],
                            'quota': r['quota'], 'via': '同一代码下出现年数最多的名称'})
            n['senior_high_school'] = cs
            n['is_placeholder_code'] = '0'
            note = (note + f"；原为简称「{r['senior_high_school']}」，按官方代码 "
                          f"{r['senior_high_school_code']} 归一为「{cs}」").strip('；')
        jc = r['junior_high_school_code']
        if jc in JUNIOR_CODE_MAP:
            newcode, newname = JUNIOR_CODE_MAP[jc]
            changes.append({'kind': '初中临时代码', 'code': jc,
                            'old': f'{jc} {r["junior_high_school"]}',
                            'new': f'{newcode} {newname}', 'year': r['year'],
                            'junior': r['junior_high_school'], 'quota': r['quota'],
                            'via': '2024 并入大同初级中学，与分数线侧同一实体'})
            n['junior_high_school_code'] = newcode
            n['junior_high_school'] = newname
            note = (note + f"；原为临时代码 {jc}「{r['junior_high_school']}」，"
                          f"归一为「{newname}」").strip('；')
        if note:
            n['note'] = note
        out.append(n)
    return out, changes


def cross_check(changes):
    """独立交叉验证：按代码推断的简称映射 vs 2024 PDF 头部对照表。"""
    hdr = parse_2024_header(PDF2024)
    print(f'  PDF 头部解析到 {len(hdr)} 条对照: {hdr}')
    mine = {c['old']: c['code'] for c in changes if c['kind'] == '高中简称'}
    bad = []
    for short, code in sorted(mine.items()):
        got = hdr.get(short)
        ok = (got == code)
        if not ok:
            bad.append((short, code, got))
        print(f'    {"OK" if ok else "NG"} 简称「{short}」→ {code}｜PDF={got or "未找到"}')
    only = sorted(set(hdr) - set(mine))
    if only:
        print(f'  PDF 对照表中未被归一覆盖: {only}')
    return bad


def report(rows, out, changes):
    k = Counter(c['kind'] for c in changes)
    print(f'\n=== 将做的替换 {len(changes)} 行 ===')
    for kind, n in k.items():
        print(f'  {kind}: {n} 行')
    for c in changes:
        print(f"    {c['year']} {c['junior'][:14]:<16} {c['old'][:24]:<26} → "
              f"{c['new'][:26]:<28} 名额{c['quota']}")
    same = all(r['quota'] == n['quota'] and r['year'] == n['year']
               for r, n in zip(rows, out))
    print('\n=== 副作用检查 ===')
    print(f'  行数 {len(rows)} → {len(out)}｜quota 逐行相等: {same}')
    print(f'  名额总和 {sum(int(r["quota"]) for r in rows)} → '
          f'{sum(int(r["quota"]) for r in out)}')
    print(f'  is_placeholder_code=1 行数 '
          f'{sum(1 for r in rows if r["is_placeholder_code"] == "1")} → '
          f'{sum(1 for r in out if r["is_placeholder_code"] == "1")}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    rows, cols = load()
    print(f'读入 {len(rows)} 行，{len(cols)} 列')
    out, changes = plan_normalize(rows)
    report(rows, out, changes)
    print('\n=== 独立交叉验证（按代码推断 vs 2024 PDF 对照表）===')
    bad = cross_check(changes)
    if bad:
        print(f'\n交叉验证不一致 {len(bad)} 条，终止（不得写盘）: {bad}')
        return 1
    print('\n交叉验证通过')
    if not a.write:
        print('（--check：未写盘）')
        return 0
    if 'note' not in cols:
        cols.append('note')
    shutil.copy(PL, BAK)
    with open(PL, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f'\n已写入 {PL}（{len(out)} 行，备份在 {BAK}）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
