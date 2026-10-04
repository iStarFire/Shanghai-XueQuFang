#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.1 门禁：校验脚本与生成脚本**共用**平均秩实现（防假门禁）。

## 问题
若 `verify_*.py` 自己重写一份平均秩 / 分位 / 加权均分，即使逻辑写错也会与
`build_v3.py` 「一致」，形成**假门禁** —— 用同一种错误验证自己，校验失去独立性。

## 判定
1. `pt_common.py` 存在且导出 `midrank` / `p_from_rank` / `weighted_mean`；
2. `build_v3.py` **import** 该模块，且**不再内联** `b = sum(1 for w in xs if w > v)`
   这类平均秩实现（内联 = 未共用）；
3. 每个 `verify_*.py` 若涉及秩/分位/均分，同样必须 import，且不得内联；
4. `midrank` 对已知输入的输出正确（含并列用例）。
"""
import ast
import re
import sys
from pathlib import Path

T = Path(__file__).resolve().parent
COMMON = T / 'pt_common.py'
GEN = T / 'build_v3.py'
VERIFIERS = sorted(T.glob('verify_*.py'))

# 涉及秩/分位/均分 ⇒ 必须共用
# 只认「重算秩」的痕迹：调用/定义 midrank 等。
# 单纯**引用**宽表里已算好的 rank_base4_* / mean_rank_* 列**不需要**共用实现。
NEEDS = re.compile(r'midrank\s*\(|_rank_avg_tie\s*\(|p_from_rank\s*\(|weighted_mean\s*\(')


def imports_common(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == 'pt_common':
            return True
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == 'pt_common':
                    return True
    return False


def has_inline(src):
    """用 AST 检测内联平均秩：`sum(1 for w in X if w > v)` / `... if w == v)`。

    不用正则 —— 注释里写示例、以及 tokenize 拼接造成的空格差异都会让正则失准
    （曾因此让本门禁对真实内联完全失效）。AST 只看语法结构，注释与字符串天然不参与。
    """
    found = []
    for n in ast.walk(ast.parse(src)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'sum' and n.args
                and isinstance(n.args[0], ast.GeneratorExp)):
            continue
        gen = n.args[0]
        clause = ' '.join(ast.unparse(c) for c in gen.generators[0].ifs) \
            if gen.generators else ''
        if re.search(r'w\s*>\s*v', clause) or re.search(r'w\s*==\s*v', clause):
            found.append(ast.unparse(n)[:60])
    return found


def main():
    bad = []
    if not COMMON.exists():
        print('❌ 缺 工具/pt_common.py')
        return 1

    # 1) 共用模块本身可用且正确
    sys.path.insert(0, str(T))
    from pt_common import midrank, p_from_rank, weighted_mean
    cases = [
        ([('a', 10.0), ('b', 20.0), ('c', 30.0)], {'a': 3.0, 'b': 2.0, 'c': 1.0}),
        ([('a', 5.0), ('b', 5.0), ('c', 9.0)], {'a': 2.5, 'b': 2.5, 'c': 1.0}),
        ([('a', 1.0), ('b', 1.0), ('c', 1.0)], {'a': 2.0, 'b': 2.0, 'c': 2.0}),
    ]
    for pairs, want in cases:
        got = midrank(pairs)
        if got != want:
            bad.append(f'midrank({pairs}) = {got}，应为 {want}')
    if abs(p_from_rank(1, 32) - 1.0) > 1e-12 or abs(p_from_rank(32, 32)) > 1e-12:
        bad.append('p_from_rank 端点值不对')
    if abs(weighted_mean([(700.0, 3), (600.0, 1)]) - 675.0) > 1e-9:
        bad.append('weighted_mean 不对')
    print(f'1) pt_common 存在，midrank/p_from_rank/weighted_mean '
          f'通过 {len(cases)} 个用例（含全并列）')

    # 2) 生成脚本共用
    gsrc = GEN.read_text(encoding='utf-8')
    if not imports_common(ast.parse(gsrc)):
        bad.append('build_v3.py 未 import pt_common')
    inl = has_inline(gsrc)
    if inl:
        bad.append(f'build_v3.py 仍内联平均秩实现：{inl}')
    print(f'2) build_v3.py：import={"✅" if imports_common(ast.parse(gsrc)) else "❌"}'
          f'  内联平均秩={"❌ " + str(inl) if inl else "✅ 无"}')

    # 3) 校验脚本共用
    print('3) 校验脚本：')
    for v in VERIFIERS:
        if v.name == Path(__file__).name:
            print(f'   {v.name:<28} （门禁自身，跳过）')
            continue
        src = v.read_text(encoding='utf-8')
        tree = ast.parse(src)
        need = bool(NEEDS.search(src))
        imp = imports_common(tree)
        inl = has_inline(src)
        if need and not imp:
            bad.append(f'{v.name} 涉及秩/分位/均分但未 import pt_common')
        if inl:
            bad.append(f'{v.name} 内联平均秩实现：{inl}')
        print(f'   {v.name:<28} 需共用={"是" if need else "否":<2} '
              f'import={"✅" if imp else ("❌" if need else "—")} '
              f'内联={"❌" if inl else "✅"}')

    if bad:
        print(f'\n❌ 未通过 {len(bad)} 项：')
        for b in bad:
            print('   ', b)
        return 1
    print(f'\n✅ 共用性门禁通过：{len(VERIFIERS)} 个校验脚本 + 生成脚本'
          f'均使用 工具/pt_common.py 的同一份实现')
    return 0


if __name__ == '__main__':
    sys.exit(main())
