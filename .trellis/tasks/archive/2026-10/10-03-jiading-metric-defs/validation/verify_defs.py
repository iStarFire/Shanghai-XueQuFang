# -*- coding: utf-8 -*-
"""2.0 指标定义表门禁：9 个指标每行一条 + 3 处口径错误防回归。

数据侧 47 项复算见 archive/2026-10/10-03-jiading-wide-full/validation/verify_wide.py，
本轮未改动数据与主表数值，故不重复。
"""
import io
import os
import sys

METRICS = ['P_wq', 'rel 均名', '名额', 'SEN', '等权名次', 'Z 名次', '线性', '指数', '近 3 年']
COLS = ['rank_P_eq', 'rank_Z_wq', 'rank_P_lin', 'rank_P_exp', 'rank_P_recent3']
PASS, FAIL, MSGS = 0, 0, []


def find_root(marker=os.path.join('data', '嘉定区')):
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, marker)):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise RuntimeError('未找到仓库根')
        d = nd


def ck(name, got, exp):
    global PASS, FAIL
    if got == exp:
        PASS += 1
        print(f'  [OK] {name}')
    else:
        FAIL += 1
        MSGS.append(f'{name}: 重算={got} 期望={exp}')
        print(f'  [!!] {name}: 重算={got} 期望={exp}')


rep = io.open(f'{find_root()}/analysis/嘉定区公办初中名额分配到校分析/分析报告.md',
              encoding='utf-8').read()
sec2 = rep[rep.index('## 2 排名主表'):rep.index('## 3 结构分析')]
rows = [l for l in sec2.split('\n') if l.startswith('| **')]
body = '\n'.join(rows)
main_rows = [l for l in sec2.split('\n')
             if l.startswith('| ') and l.split('|')[1].strip().isdigit()]

print('=' * 60)
print('2.0 指标定义表')
print('=' * 60)
ck('2.0 存在小节', '### 2.0 表中 9 个指标怎么读' in sec2, True)
ck('定义表数据行数 = 9', len(rows), 9)
for m in METRICS:
    ck(f'含指标行「{m}」', any(l.startswith(f'| **{m}') for l in rows), True)
for c in COLS:
    ck(f'标注宽表列名 {c}', c in body, True)
ck('每个指标行都有 4 列（列名/定义/算法/读法）',
   all(l.count('|') == 5 for l in rows), True)
ck('SEN 定义为最小二乘斜率', '最小二乘回归' in body, True)
ck('SEN 未误写为 Sen 中位斜率', 'Sen 中位斜率' not in body, True)
ck('SEN 单位为「分/年」', '分/年' in body, True)
ck('P_wq 声明「不是分值可比」', '不是分值可比' in body, True)
ck('名额列声明「不等于办学水平」', '不等于办学水平' in body, True)
ck('时间权重三档互不混淆（5 倍/16 倍/丢弃两年）',
   all(k in body for k in ['5 倍', '16 倍', '丢弃 2022–2023']), True)

print('=' * 60)
print('3 处口径错误防回归')
print('=' * 60)
ck('章节标题为「名额加权主口径」', '## 2 排名主表（名额加权主口径' in rep, True)
ck('标题不再写「名额加权综合口径」', '名额加权综合口径' not in rep, True)
ck('正文列名与表头一致（不再单写 `P`）', '`P` = 5 年均分位' not in rep, True)
ck('不再出现「Sen 斜率」', 'Sen 斜率' not in rep, True)
ck('已说明 comb 口径不在本表', 'P_wq_comb' in sec2 and '不在本表' in sec2, True)
ck('主表内重复的「（宽表列名）」行已去除', '| （宽表列名） |' not in rep, True)
ck('主表仍为 28 行', len(main_rows), 28)

print('=' * 60)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
