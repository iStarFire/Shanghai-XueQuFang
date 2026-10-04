# -*- coding: utf-8 -*-
"""扫描报告中所有数字引用，与 CSV 实际值逐项对照，找出「用了旧数字」的结论。

背景：2026-10-03 排名池口径从「含民办」改为「仅公办」，全部 P 值 / 位次 / 名次
都变了。上一轮同步了表格与部分叙述，但**不可能保证 919 行正文里的每个数字都改对**。
本脚本不猜测，而是把报告里出现的具体数字与 CSV 实际值机械比对。

用法：python3 verify_report_numbers_jd.py
"""
import csv
import os
import re

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = f'{D}/分析报告.md'


def load(n):
    return list(csv.DictReader(open(f'{D}/{n}', encoding='utf-8-sig')))


W = {r['junior_high_school']: r for r in load('宽表-初中水平-嘉定区-2022-2026.csv')}
M = {r['junior_high_school']: r for r in load('rank-多口径总表-嘉定区-2022-2026.csv')}
S = {r['junior_high_school']: r for r in load('趋势分类-嘉定区-2022-2026.csv')}
rep = open(REP, encoding='utf-8').read()
lines = rep.split('\n')

SH = ('上海师范大学附属第五嘉定实验学校', '交大附中附属嘉定洪德中学',
      '同济大学附属嘉定实验中学', '上海市嘉定区嘉一实验初级中学',
      '同济大学附属实验中学', '上海外国语大学嘉定外国语学校',
      '上海市嘉定区新城实验中学', '交大附中附属嘉定德富中学')


def short(n):
    return n.replace('上海市嘉定区', '').replace('上海市', '').replace('上海', '')


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


bad = []       # (行号, 片段, 说明)
checked = 0

# ---------- 1) 头部指标行：P_wq / SEN / 名次 ----------
for i, ln in enumerate(lines, 1):
    m = re.search(r'\*\*(.+?)\*\*｜主口径第 (\d+) 名，P_wq=([\d.]+)，名额均 ([\d.]+)，SEN=([-\d.]+)（(.+?)）', ln)
    if not m:
        continue
    disp, rk, pw, qa, sen, cls = m.groups()
    full = next((k for k in W if short(k) == disp), None)
    if not full:
        bad.append((i, disp, '校名匹配不到宽表'))
        continue
    checked += 1
    # 一律按**报告实际显示精度**比对：报告 SEN 用 2 位小数、P_wq 用 3 位、
    # 名额用 1 位。按 CSV 原始精度比对会把正确四舍五入误判为不一致。
    for label, got, exp in (('名次', int(rk), int(M[full]['rank_P_wq_all'])),
                            ('P_wq', round(float(pw), 3), round(float(M[full]['P_wq_all']), 3)),
                            ('名额', round(float(qa), 1), round(float(W[full]['quota3_avg']), 1)),
                            ('SEN', round(float(sen), 2), round(float(S[full]['sen']), 2)),
                            ('趋势', cls, S[full]['trend_class'])):
        if got != exp:
            bad.append((i, disp, f'{label} 报告={got} 实际={exp}'))

# ---------- 2) 「名次（变化）」列 ----------
for i, ln in enumerate(lines, 1):
    if not re.match(r'^\| \d+ \| ', ln):
        continue
    cells = [c.strip() for c in ln.strip('|').split('|')]
    if len(cells) < 14:
        continue
    disp = cells[1].replace('^', '').strip()
    full = next((k for k in M if short(k) == disp), None)
    if not full:
        continue
    base = int(M[full]['rank_P_wq_all'])
    for col, key in ((11, 'rank_P_recent3'), (12, 'rank_P_recent2')):
        m = re.match(r'\*\*(\d+)\*\*（([+\-−]?\d+)）', cells[col])
        if not m:
            continue
        checked += 1
        rk_act = int(M[full][key])
        d_rep = int(m.group(2).replace('−', '-'))
        if int(m.group(1)) != rk_act:
            bad.append((i, disp, f'第{col}列名次 报告={m.group(1)} 实际={rk_act}'))
        if d_rep != base - rk_act:
            bad.append((i, disp, f'第{col}列变化 报告={d_rep:+d} 实际={base - rk_act:+d}'))

# ---------- 3) 逐年位次链「位次 a → b → c」 ----------
for i, ln in enumerate(lines, 1):
    m = re.search(r'位次 ((?:\*\*)?\d+(?:\*\*)?(?: → (?:\*\*)?\d+(?:\*\*)?)+)', ln)
    if not m:
        continue
    disp = None
    for k in W:
        if short(k) and short(k) in ln:
            disp = k
            break
    if not disp:
        continue
    nums = [int(x.replace('**', '')) for x in re.findall(r'\d+', m.group(1))]
    ycount = len(nums)
    if ycount == 5:
        ys = ['2022', '2023', '2024', '2025', '2026']
    elif ycount == 4:
        ys = ['2023', '2024', '2025', '2026']
    else:
        continue
    # 只在段落首行声明了该校名时才校验（避免误伤其他校的位次串）
    if short(disp) not in ln:
        continue
    checked += 1
    for y, got in zip(ys, nums):
        exp = W[disp].get(f'rank_base3_wq_{y}', '')
        e = num(exp)
        if e is not None and int(e) != got:
            bad.append((i, short(disp), f'{y} 位次 报告={got} 实际={int(e)}'))

# ---------- 4) 主表 P_wq 值 ----------
for i, ln in enumerate(lines, 1):
    if not re.match(r'^\| \d+ \| ', ln):
        continue
    cells = [c.strip() for c in ln.strip('|').split('|')]
    if len(cells) < 15:
        continue
    disp = cells[1].replace('^', '').strip()
    full = next((k for k in M if short(k) == disp), None)
    if not full:
        continue
    p = num(cells[3])
    if p is None:
        continue
    checked += 1
    if abs(p - float(M[full]['P_wq_all'])) > 0.0006:
        bad.append((i, disp, f'主表 P_wq 报告={p} 实际={float(M[full]["P_wq_all"]):.3f}'))

print(f'机械比对 {checked} 处数字引用')
if not bad:
    print('✅ 全部一致，未发现旧数字残留')
else:
    print(f'❌ 发现 {len(bad)} 处不一致：\n')
    for i, who, why in bad:
        print(f'  L{i:<4} {who:<24} {why}')
