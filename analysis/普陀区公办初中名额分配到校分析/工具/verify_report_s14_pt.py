#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5.4 门禁：报告 1.4「被排除的四类学校」小节的表格必须与宽表逐格一致。

为什么需要：1.4 的表格是**手写**进报告的（不像第 2 章由脚本生成），
一旦宽表重算而报告未同步，校数、名额、均分就会静默失配。
本脚本把 1.4 逐行比对，任何一格不符即失败。

覆盖：11 所被排除学校（民办 5 / 短样本 4 / 退出 2）的
      4 线名额、4 线均分（2 位小数）、P_wq；退出类无 P_wq 列故跳过。
"""
import csv
import re
import sys
from pathlib import Path

A = Path(__file__).resolve().parents[1]
R = A / '分析报告.md'
W = A / '宽表-初中水平-普陀区-2022-2026.csv'
YEARS = ['2022', '2023', '2024', '2025', '2026']

# 1.4 中逐行列出的 11 所（校名须与宽表一致，不允许简称）
NAMES = [
    '上海兰田中学', '上海华东师范大学附属进华中学', '上海培佳双语学校',
    '上海安生学校', '民办新黄浦实验学校',
    '普陀区梅陇实验中学', '甘泉外国语中学', '金鼎学校',
    '上海音乐学院附属安师实验中学',
    '光新学校', '武宁中学',
]
NO_P = {'光新学校', '武宁中学'}          # 退出类表格无 P_wq 列


def main():
    txt = R.read_text(encoding='utf-8')
    if '### 1.4 被排除的四类学校' not in txt:
        print('❌ 报告缺少 1.4 小节')
        return 1
    sec = txt[txt.index('### 1.4 被排除的四类学校'):txt.index('## 2 排名总表')]
    wide = {r['junior_high_school']: r for r in csv.DictReader(W.open(encoding='utf-8-sig'))}

    bad, cells = [], 0
    for short in NAMES:
        key = next((k for k in wide if k.replace('上海市', '') == short
                    or k.endswith(short)), None)
        if key is None:
            bad.append(f'{short}: 宽表中无此校（报告用了简称或错名）')
            continue
        r = wide[key]
        line = next((l for l in sec.split('\n')
                     if l.startswith('|') and short in l), None)
        if line is None:
            bad.append(f'{short}: 1.4 无对应表格行')
            continue
        exp_q = ' / '.join(r.get(f'quota4_{y}', '') or '0' for y in YEARS)
        exp_m = ' / '.join(
            f"{float(r[f'mean_score_base4_wq_{y}']):.2f}"
            if r.get(f'mean_score_base4_wq_{y}') not in ('', None) else '—'
            for y in YEARS)
        if exp_q not in line:
            bad.append(f'{short}: 4 线名额 应为 [{exp_q}]')
        else:
            cells += 5
        if exp_m not in line:
            bad.append(f'{short}: 4 线均分 应为 [{exp_m}]')
        else:
            cells += 5
        if short not in NO_P and r.get('P_wq'):
            p = f"{float(r['P_wq']):.3f}"
            if p not in line:
                bad.append(f'{short}: P_wq 应为 [{p}]')
            else:
                cells += 1

    # 类别计数：宽表侧与报告侧**都要**对上（缺一不可）
    from collections import Counter
    cnt = Counter(r['row_type'] for r in wide.values())
    for lab, rt in [('民办', 'excluded_private'), ('短样本', 'short_sample'),
                    ('退出', 'exited'), ('新开办', None)]:
        n = cnt.get(rt, 0) if rt else 0
        # 报告侧：从 1.4 的小节标题里读出校数
        m = re.search(rf'#### 1\.4\.\d+ {lab}（(\d+) 所', sec)
        if not m:
            bad.append(f'1.4 缺「{lab}」小节或标题未写校数')
            continue
        rep_n = int(m.group(1))
        if rep_n != n:
            bad.append(f'{lab} 校数：报告写 {rep_n}，宽表实为 {n}')
        cells += 1
    # 入榜 32 所也要在 1.1 表里对上
    m = re.search(r'\| `ranked` \| \*\*(\d+)\*\*', txt)
    if not m or int(m.group(1)) != cnt.get('ranked', 0):
        bad.append(f"ranked 校数：报告 1.1 写 {m.group(1) if m else '未找到'}，"
                   f"宽表实为 {cnt.get('ranked', 0)}")
    else:
        cells += 1
    # 四类互斥穷尽：43 = 32 + 5 + 4 + 2
    if sum(cnt.get(k, 0) for k in
           ('ranked', 'short_sample', 'exited', 'excluded_private')) != len(wide):
        bad.append('row_type 四类之和 ≠ 宽表行数，四类不互斥穷尽')

    print(f'1.4 逐格核对：{len(NAMES)} 所 × 3 类字段 = {len(NAMES) * 11} 格，'
          f'实际比对 {cells} 格（含类别计数）')
    if bad:
        print(f'❌ 不一致 {len(bad)} 处：')
        for b in bad:
            print('   ', b)
        return 1
    print('✅ 1.4 表格与宽表逐格一致（名额 / 均分 2 位小数 / P_wq），类别计数一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
