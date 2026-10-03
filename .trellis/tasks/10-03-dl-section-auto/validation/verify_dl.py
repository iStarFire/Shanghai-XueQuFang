# -*- coding: utf-8 -*-
"""各课题网页版下载区门禁。

教训（2026-10）：普陀的 build_dl() 清单整段复制自徐汇，os.path.exists 把不存在的
文件全过滤掉，6 个 CSV 的下载入口全部消失。根因是硬编码清单，已改为自动扫描目录。
本门禁确保交付物与下载入口不再脱节。
"""
import io
import os
import re
import sys

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


os.chdir(find_root())
topics = [n for n in sorted(os.listdir('analysis'))
          if os.path.isdir(f'analysis/{n}') and not n.startswith('.')]
SHORT = {t: t.replace('区公办初中名额分配到校分析', '区') for t in topics}
print('=' * 62)
print('下载区 vs 目录内交付物')
print('=' * 62)
for t in topics:
    topic = f'analysis/{t}'
    idx = f'{topic}/index.html'
    if not os.path.exists(idx):
        ck(f'{t} index.html 存在', False, True)
        continue
    page = io.open(idx, encoding='utf-8').read()
    m = re.search(r'<div class="dl">(.*?)</div>', page, re.S)
    hrefs = re.findall(r'href="([^"]+)"', m.group(1) if m else '')
    dl = sorted(f for f in os.listdir(topic)
                if os.path.isfile(f'{topic}/{f}') and not f.startswith('.')
                and f != 'index.html' and (f.endswith('.csv') or f.endswith('.md')))
    ck(f'{t}：下载项数 == 交付物数（{len(dl)}）', len(hrefs), len(dl))
    ck(f'{t}：无交付物缺少下载入口', sorted(set(dl) - set(hrefs)), [])
    ck(f'{t}：下载区无多余入口', sorted(set(hrefs) - set(dl)), [])
    ck(f'{t}：链接全部指向真实文件',
       [h for h in hrefs if not os.path.exists(f'{topic}/{h}')], [])
    others = [h for h in hrefs if any(k in h for k in ('徐汇', '普陀', '嘉定'))
              and SHORT[t] not in h]
    ck(f'{t}：下载区不含他区文件', others, [])

print('=' * 62)
print('构建脚本已改为自动扫描（不得回退为硬编码清单）')
print('=' * 62)
for t in topics:
    sdir = f'{topic}/工具' if False else f'analysis/{t}/工具'
    scripts = [f for f in os.listdir(sdir) if f.startswith('build_html')]
    ck(f'{t}：找到构建脚本', len(scripts) >= 1, True)
    for sc in scripts:
        src = io.open(f'{sdir}/{sc}', encoding='utf-8').read()
        ck(f'{t}/{sc}：使用 DL_LABELS 自动发现', 'DL_LABELS' in src, True)
        ck(f'{t}/{sc}：不再用 os.path.exists 过滤硬编码清单',
           bool(re.search(r"os\.path\.exists\(f'\{TOPIC\}/\{f\}'\)", src)), False)

print('=' * 62)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
