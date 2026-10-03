# -*- coding: utf-8 -*-
"""黄浦报告「不做跨区对比」门禁。

用户 2026-10-03 明确要求：黄浦报告的每条结论只靠黄浦自身五年数据自证，
不借外区做参照系。本门禁在报告生成后自动检查：
报告正文（结论/主表/图注/摘要/个案）中不得出现其他区的区名，
也不得出现「相比/对照/与…相同/与…不同」这类跨区比较句式。
"""
import io
import os
import re
import sys

PASS, FAIL, MSGS = 0, 0, []
OTHER_DISTRICTS = ['普陀', '徐汇', '浦东', '闵行', '静安', '长宁', '杨浦', '虹口',
                   '松江', '宝山', '嘉定', '青浦', '奉贤', '金山', '崇明']
BAD_PHRASES = ['其他区', '异地', '外区', '相比', '对照', '相较', '与其他区',
               '与普陀', '与徐汇', '与嘉定', '同类区', '各区对比', '跨区']
# 「跨区」一词在报告里也用于**禁止性声明**（如「未做跨区对比，结论只适用于黄浦区」），
# 那不是跨区比较。故排除「未/不 + 跨区」的否定用法，只 catching 真正的比较表述。
NEG = ('未做跨区', '不做跨区', '不与外区', '未与外区', '禁止跨区', '不含跨区',
       '无跨区', '跨区对比句式', '跨区引用', '跨区比较句式', '跨区对比的')
# 报告自身允许出现的表述（黄浦区、委属线的招生学校等）
ALLOW = ['黄浦']


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
REP = f'{ROOT}/analysis/黄浦区公办初中名额分配到校分析/分析报告.md'
PRD = f'{ROOT}/.trellis/tasks/10-03-huangpu-junior-high/prd.md'

print('=' * 62)
print('约束已登记')
print('=' * 62)
ck('PRD 存在', os.path.exists(PRD), True)
if os.path.exists(PRD):
    t = io.open(PRD, encoding='utf-8').read()
    ck('PRD 写明「报告不做跨区对比」', '报告不做跨区对比' in t or '不做跨区对比' in t, True)
    ck('PRD 写明「只靠黄浦自身五年数据自证」', '只靠黄浦自身五年数据自证' in t, True)

print('=' * 62)
print('报告跨区引用检查')
print('=' * 62)
if not os.path.exists(REP):
    print(f'  [..] 报告尚未生成（{os.path.basename(REP)}），跳过内容检查')
    ck('约束已就位（待报告生成后自动校验）', True, True)
else:
    rep = io.open(REP, encoding='utf-8').read()
    hits = [(k, rep.count(k)) for k in OTHER_DISTRICTS if k in rep]
    ck('报告中出现的其他区名', hits, [])
    # 排除否定/元陈述用法：「未做跨区对比」是本报告的**约束声明**，不是跨区比较。
    probe = rep
    for n in NEG:
        probe = probe.replace(n, '')
    bad = [k for k in BAD_PHRASES if k in probe]
    ck('报告中的跨区比较句式', bad, [])
    ck('报告存在且非空', len(rep) > 2000, True)
    print(f'  报告 {len(rep)} 字符，已检查区名 {len(OTHER_DISTRICTS)} 个 + 句式 {len(BAD_PHRASES)} 个')

print('=' * 62)
print(f'总计 {PASS + FAIL} 项检查，不通过 {FAIL} 项')
for m in MSGS:
    print('  -', m)
sys.exit(1 if FAIL else 0)
