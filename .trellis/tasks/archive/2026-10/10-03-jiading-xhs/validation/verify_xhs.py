# -*- coding: utf-8 -*-
"""嘉定小红书素材门禁：图片完整性、配色区分、文案数字与宽表一致。"""
import csv
import io
import os
import re
import struct
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
        print(f'  [OK] {name}: {got}')
    else:
        FAIL += 1
        MSGS.append(f'{name}: 重算={got} 期望={exp}')
        print(f'  [!!] {name}: 重算={got} 期望={exp}')


ROOT = find_root()
OUT = f'{ROOT}/target/小红书/嘉定区名额分配到校分析'
NAMES = ['主图-排名表', '子图1-名额与位次', '子图2-切点深度', '子图3-无收敛',
         '子图4-残差个案', '子图5-有效边界', '长图']
XH = ['#FF3B5C', '#FF6F91', '#FFE9EE', '#FFF1F4']      # 徐汇粉红系
TEAL = ['#0F766E', '#14B8A6', '#F0FDFA']              # 嘉定蓝绿系


def png_size(p):
    d = open(p, 'rb').read(33)
    return struct.unpack('>II', d[16:24])


def load(p, d=None):
    with open(f'{d or ROOT}/analysis/嘉定区公办初中名额分配到校分析/{p}',
              encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


print('=' * 62)
print('[1] 素材完整性')
print('=' * 62)
ck('7 张 PNG 齐全', [n for n in NAMES if not os.path.exists(f'{OUT}/{n}.png')], [])
ck('7 份 HTML 源齐全', [n for n in NAMES if not os.path.exists(f'{OUT}/{n}.html')], [])
ck('文案.md 存在', os.path.exists(f'{OUT}/文案.md'), True)
ck('PNG 宽度全为 1080', sorted({png_size(f'{OUT}/{n}.png')[0] for n in NAMES}), [1080])
hts = {n: png_size(f'{OUT}/{n}.png')[1] for n in NAMES}
ck('主图为完整排名表（>2000px）', hts['主图-排名表'] > 2000, True)
ck('长图远长于单图（>6000px）', hts['长图'] > 6000, True)
ck('子图高度均在合理区间',
   [n for n in NAMES[1:6] if not (900 < hts[n] < 2600)], [])

print('=' * 62)
print('[2] 配色：必须是蓝绿 teal，且不含徐汇粉红')
print('=' * 62)
for n in NAMES:
    h = io.open(f'{OUT}/{n}.html', encoding='utf-8').read()
    ck(f'{n} 使用 teal 主色', all(c in h for c in TEAL), True)
    ck(f'{n} 不含徐汇粉红', [c for c in XH if c in h], [])

print('=' * 62)
print('[3] 主图排名表 ↔ 宽表逐行一致')
print('=' * 62)
SH = lambda x: x.replace('上海市嘉定区', '').replace('上海市', '')
W = load('宽表-初中水平-嘉定区-2022-2026.csv')
TB = sorted([r for r in W if r['ranked'] == '1'], key=lambda r: int(r['rank_P_wq']))
main = io.open(f'{OUT}/主图-排名表.html', encoding='utf-8').read()
rows = re.findall(r'<tr( class="top")?><td>(\d+)</td><td class="c2">([^<]+)</td>'
                  r'<td>([\d.]+)</td><td>([+−][\d.]+)</td><td>([\d.]+)</td>'
                  r'<td>([+−][\d.]+)</td></tr>', main)
ck('主表行数 = 入榜数', len(rows), len(TB))
bad = []
for i, (top, rk, nm, P, rel, q, sen) in enumerate(rows):
    r = TB[i]
    if int(rk) != int(r['rank_P_wq']) or nm != SH(r['junior_high_school']):
        bad.append((rk, nm))
    if abs(float(P) - round(float(r['P_wq']), 3)) > 1e-9:
        bad.append((nm, 'P', P, r['P_wq']))
    if abs(float(rel.replace('−', '-')) - round(float(r['rel_avg']), 2)) > 1e-9:
        bad.append((nm, 'rel', rel, r['rel_avg']))
    if abs(float(q) - round(float(r['quota3_avg']), 1)) > 1e-9:
        bad.append((nm, '名额', q, r['quota3_avg']))
    if abs(float(sen.replace('−', '-')) - round(float(r['SEN']), 2)) > 1e-9:
        bad.append((nm, 'SEN', sen, r['SEN']))
    if bool(top) != (int(r['rank_P_wq']) <= 5):
        bad.append((nm, '高亮', bool(top)))
ck('主表每行与宽表一致', bad, [])
ck('前 5 名高亮数', len([r for r in rows if r[0]]), 5)

print('=' * 62)
print('[4] 文案数字 ↔ 宽表/趋势表一致')
print('=' * 62)
doc = io.open(f'{OUT}/文案.md', encoding='utf-8').read()
TR = {r['junior_high_school']: r for r in load('趋势分析-嘉定区-2022-2026.csv')}
n_rank = len(TB)
n_all = len(W)
n_priv = len([r for r in W if r['ownership'] == '民办'])
n_f5 = len([r for r in W if r['years_included'] == '5'])
r2 = [float(list(TR.values())[0][f'convB_r2_{y}']) for y in (2023, 2024, 2025, 2026)]
sen_min2 = sorted(float(v['sen_ols']) for v in TR.values())[:2]
for label, val in [('入榜所数', n_rank), ('全区所数', n_all), ('民办所数', n_priv),
                   ('五年全勤', n_f5), ('收敛 R² 下限', round(min(r2), 3)),
                   ('收敛 R² 上限', round(max(r2), 3))]:
    ck(f'文案含正确的{label} {val}', str(val) in doc, True)
ck('文案含 Spearman(名额,P)=+0.509', '+0.509' in doc, True)
ck('文案含同线内 −0.211', '−0.211' in doc, True)
for v in sen_min2:
    ck(f'文案含下滑校斜率 {v:.2f}', f'{v:.2f}'.replace('-', '−') in doc, True)
ck('文案含区内名额 317→599', '317' in doc and '599' in doc, True)
ck('文案声明口径边界（前 4%–7%）', '4%–7%' in doc, True)
ck('文案声明不是绝对好坏', '不是学校绝对好坏' in doc or '不能当学校绝对好坏' in doc, True)
ck('文案含 10 个标签', len(re.findall(r'#\S+', doc.split('## 标签')[1].split('##')[0])),
   10)
ck('配色说明标注 teal', 'teal' in doc, True)
for n in NAMES:
    ck(f'文案引用了 {n}', n.split('-')[0] in doc, True)

print('=' * 62)
print('[5] 长图完整性')
print('=' * 62)
lg = io.open(f'{OUT}/长图.html', encoding='utf-8').read()
ck('长图含全部 6 个板块标题',
   [t for t in ['排名表', '名额与位次', '切点深度', '趋势与收敛', '残差个案', '有效边界']
    if f'>{t}<' not in lg], [])
ck('长图含 28 所校名', len([r for r in TB if SH(r['junior_high_school']) in lg]), len(TB))
ck('长图含网页版链接', 'istarfire.github.io' in lg, True)

print('=' * 62)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
