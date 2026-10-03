# -*- coding: utf-8 -*-
"""2.5 生成嘉定区名额到校排序表 PNG（fitz 渲染，无外部依赖）。"""
import csv
import os

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
A = f'{ROOT}/analysis/嘉定区公办初中名额分配到校分析'
OUT = f'{ROOT}/target/小红书/嘉定区名额分配到校分析'
os.makedirs(OUT, exist_ok=True)
FONT = 'china-ss'


def cn(s):
    return (s.replace('上海市嘉定区', '').replace('上海市', '')
             .replace('实验中学', '实验').replace('中学', '中'))


rows = list(csv.DictReader(open(f'{A}/rank-标准化-嘉定区-2022-2026.csv', encoding='utf-8-sig')))
W, RH, TOP = 560, 30, 96
H = TOP + 34 + RH * len(rows) + 46
doc = fitz.open()
pg = doc.new_page(width=W, height=H)


def txt(x, y, s, size=11, color=(0.1, 0.1, 0.12), bold=False):
    pg.insert_text((x, y), s, fontname='china-ss' if not bold else 'china-ss',
                   fontsize=size, color=color)


txt(24, 40, '嘉定区初中「名额分配到校」排名', 19)
txt(24, 60, '2022–2026 五年 · 名额加权区属市重点线口径 · 分位 P 主排序', 10.5,
    (0.35, 0.35, 0.4))
txt(24, 78, '名额加权 P｜相对当年全区中位的均名分｜区属年均名额｜Sen 斜率（趋势）', 9.5,
    (0.5, 0.5, 0.55))
cols = [24, 76, 300, 372, 442, 500]
head = ['#', '初中（5 年全勤 / n≥4）', 'P', '均名', '名额', 'SEN']
pg.draw_rect(fitz.Rect(20, TOP, W - 20, TOP + 26), color=(0.85, 0.87, 0.9), fill=(0.96, 0.97, 0.98))
for x, t in zip(cols, head):
    txt(x, TOP + 18, t, 10.5, (0.2, 0.2, 0.25))
y = TOP + 26
for i, r in enumerate(rows, 1):
    if i % 2 == 0:
        pg.draw_rect(fitz.Rect(20, y, W - 20, y + RH), color=None, fill=(0.985, 0.985, 0.99))
    txt(cols[0] + 4, y + 20, str(r['rank_P_wq']), 10.5, (0.45, 0.45, 0.5))
    txt(cols[1], y + 20, cn(r['junior_high_school']), 11)
    txt(cols[2], y + 20, f"{float(r['P_wq']):.3f}", 11)
    txt(cols[3], y + 20, f"{float(r['rel_avg']):+.2f}", 11)
    txt(cols[4], y + 20, f"{float(r['quota_avg']):.1f}", 11)
    sen = r['SEN']
    txt(cols[5], y + 20, (f"{float(sen):+.2f}" if sen else '—'), 10.5,
        (0.2, 0.4, 0.2) if sen and float(sen) > 0 else ((0.65, 0.25, 0.2) if sen else (0.5, 0.5, 0.5)))
    y += RH
pg.draw_line(fitz.Point(20, y + 6), fitz.Point(W - 20, y + 6), color=(0.85, 0.87, 0.9))
txt(24, y + 26, '口径：当年到校均分 = 当年全部区属市重点线（嘉定一中 / 交大附中嘉定分校 / 上师大附中嘉定新城分校）的',
    9, (0.45, 0.45, 0.5))
txt(24, y + 38, '计划名额加权平均；分位 P 为当年全区池内分位，5 年平均。样本 = 有分数年数 ≥ 4 的 28 所初中。', 9,
    (0.45, 0.45, 0.5))
pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2))
path = f'{OUT}/排序表.png'
pix.save(path)
doc.close()
print(f'已生成 {path}（{pix.width}×{pix.height}）')
