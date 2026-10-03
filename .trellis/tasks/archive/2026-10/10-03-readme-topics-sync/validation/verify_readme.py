# -*- coding: utf-8 -*-
"""README ↔ 仓库实际结构一致性门禁。

防止 README 的「分析课题列表」「目录结构树」「构建脚本表」再次与仓库脱节。
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
        print(f'  [OK] {name}')
    else:
        FAIL += 1
        MSGS.append(f'{name}: 重算={got} 期望={exp}')
        print(f'  [!!] {name}: 重算={got} 期望={exp}')


ROOT = find_root()
os.chdir(ROOT)
rd = io.open('README.md', encoding='utf-8').read()
topics = [n for n in sorted(os.listdir('analysis'))
          if os.path.isdir(f'analysis/{n}') and not n.startswith('.')]
districts = [n for n in sorted(os.listdir('data'))
             if os.path.isdir(f'data/{n}') and not n.startswith('.')]

print('=' * 62)
print('[1] 分析课题列表')
print('=' * 62)
sec = rd[rd.index('## 分析课题'):rd.index('## 目录结构')]
items = re.findall(r'^- \[([^\]]+)\]\((https://[^)]+)\)$', sec, re.M)
ck('列表条目数 = analysis/ 下课题目录数', len(items), len(topics))
ck('每个课题目录都在列表中', [t for t in topics if t not in [i[0] for i in items]], [])
ck('列表中没有不存在的目录', [i[0] for i in items if not os.path.isdir(f'analysis/{i[0]}')], [])
ck('列表内无重复', len({i[0] for i in items}), len(items))
BASE = 'https://istarfire.github.io/Shanghai-XueQuFang/analysis/'
bad_enc, dead = [], []
for name, url in items:
    enc = urllib.parse.quote(name)
    if url != f'{BASE}{enc}/index.html':
        bad_enc.append(name)
    if not os.path.exists(f'analysis/{name}/index.html'):
        dead.append(name)
ck('Pages 链接的 URL 编码全部正确', bad_enc, [])
ck('所有 Pages 链接对应的 index.html 真实存在', dead, [])

print('=' * 62)
print('[2] 同步机制说明')
print('=' * 62)
ck('已声明 README 列表需手动维护', 'README 的课题列表 | ❌ **手动**' in sec, True)
ck('已声明站点入口页卡片自动更新', '课题卡片 | ✅ 自动' in sec, True)
ck('不再声称「本列表…会自动更新」', '本列表与站点入口页会自动更新' not in rd, True)
ck('根目录实际不存在 工具/ 目录', os.path.isdir('工具'), False)
ck('README 已声明根目录没有统一 工具/', '根目录没有统一的 `工具/`' in sec, True)
ck('含 v1 旧脚本覆盖宽表的警告', 'build_wide_pt.py' in sec and '摧毁原始数据列' in sec, True)
paths = re.findall(r'`(analysis/[^`]+\.py)`', sec)
ck('脚本表里的路径全部真实存在', [p for p in paths if not os.path.exists(p)], [])
ck('脚本表已覆盖全部课题（生成网页脚本）',
   sorted({p.split('/')[1] for p in paths if 'build_html' in p}), topics)

print('=' * 62)
print('[3] 目录结构树')
print('=' * 62)
tree = rd[rd.index('## 目录结构'):]
tree = tree[:tree.index('```', tree.index('```') + 3)]
ck('data/ 段含每个实际行政区', [d for d in districts if f'│   ├── {d}/' not in tree
   and f'│   └── {d}/' not in tree], [])
ck('data/ 段不含尚未创建的 _全市/', ('_全市/' in tree), False)
ck('analysis/ 段含每个课题目录', [t for t in topics if t not in tree], [])
ck('analysis/ 段不再只列徐汇一个', tree.count('区公办初中名额分配到校分析/') >= len(topics), True)
ck('来源.md 画在主题目录下（区级不应有）',
   bool(re.search(r'^│   │   │   └── 来源\.md', tree, re.M)), True)
ck('来源.md 未被误画在区级',
   bool(re.search(r'^│   │   └── 来源\.md', tree, re.M)), False)
real_rel = [f'{d}/{t}/来源.md' for d in districts for t in os.listdir(f'data/{d}')
            if os.path.isdir(f'data/{d}/{t}') and os.path.exists(f'data/{d}/{t}/来源.md')]
ck('每个主题目录都有 来源.md（实际值）', len(real_rel) > 0, True)

print('=' * 62)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
