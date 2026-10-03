# -*- coding: utf-8 -*-
"""仓库入口页门禁：根 index.html 必须存在且为每个课题生成卡片。

背景（2026-10-03）：根 index.html 是 GitHub Pages 入口，曾被静默删除并随
`git add -A` 提交，站点照常发布但首页空白，无任何报错。本门禁防回归。
"""
import io
import os
import re
import sys
import urllib.parse

PASS, FAIL, MSGS = 0, 0, []


def find_root(marker='analysis'):
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, marker)) and os.path.isdir(os.path.join(d, 'data')):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            raise RuntimeError('未找到仓库根')
        d = nd


def ck(name, got, exp):
    global PASS, FAIL
    if got == exp:
        PASS += 1
        print(f'  [OK] {name}: {got}')
    else:
        FAIL += 1
        MSGS.append(f'{name}: 重算={got} 期望={exp}')
        print(f'  [!!] {name}: 重算={got} 期望={exp}')


ROOT = find_root()
idx = f'{ROOT}/index.html'
topics = [n for n in sorted(os.listdir(f'{ROOT}/analysis'))
          if os.path.isdir(f'{ROOT}/analysis/{n}') and not n.startswith('.')]

print('=' * 62)
print('根入口页 index.html')
print('=' * 62)
ck('根 index.html 存在', os.path.exists(idx), True)
if not os.path.exists(idx):
    print('总计 1 项检查，不通过 1 项')
    print('  - 根 index.html 缺失：重跑任一课题的 build_html 脚本即可重建'
          '（脚本会扫描 analysis/*/index.html 生成卡片）')
    sys.exit(1)
h = io.open(idx, encoding='utf-8').read()
cards = re.findall(r'href="(analysis/([^/"]+)/index\.html)"', h)
ck('字符数 > 3000（非空壳）', len(h) > 3000, True)
ck('卡片数 = analysis/ 下课题目录数', len(cards), len(topics))
ck('每个课题都有卡片', sorted(c[1] for c in cards), topics)
ck('卡片指向的页面均存在（href 需 URL 解码后按文件系统检查）',
   [c[0] for c in cards
    if not os.path.exists(f'{ROOT}/{urllib.parse.unquote(c[0])}')], [])
ck('含 <title>（页面标题未退化）', bool(re.search(r'<title>.+</title>', h)), True)
ck('卡片标题文本齐全', len(re.findall(r'<h3[^>]*>', h)) >= len(topics), True)

print('=' * 62)
print(f'课题清单（{len(topics)} 个）')
print('=' * 62)
for t in topics:
    print(f'  - {t}')
print('=' * 62)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
