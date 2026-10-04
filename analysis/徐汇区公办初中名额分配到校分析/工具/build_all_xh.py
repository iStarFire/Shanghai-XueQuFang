#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6.5 编排器：固定顺序跑全部生成脚本，并连跑 3 遍验证 md5 一致。

⛔ 顺序不可随意改（普陀踩过「生成顺序依赖」）：
   1) build_v3_xh.py     宽表（依赖 源 CSV + xh_common）
   2) build_main_xh.py   主表（依赖 宽表）
   3) build_tables_xh.py 三张新表（依赖 宽表）
   4) build_report_tables_xh.py 不写盘，仅供报告拼表

用法：
  python3 build_all_xh.py          # 跑 1 遍
  python3 build_all_xh.py --x3     # 连跑 3 遍并比对 md5（6.5 判定用）
"""
import hashlib
import subprocess
import sys
from pathlib import Path

T = Path(__file__).resolve().parent
A = T.parent
STEPS = [
    ('build_v3_xh.py', '宽表'),
    ('build_main_xh.py', '主表'),
    ('build_tables_xh.py', '收敛与趋势三表'),
]
CSVS = [
    '宽表-初中水平-徐汇区-2022-2026.csv',
    'rank-多口径总表-徐汇区-2022-2026.csv',
    '收敛指标-徐汇区-2022-2026.csv',
    '收敛趋势检验-徐汇区-2022-2026.csv',
    '趋势分类-徐汇区-2022-2026.csv',
]
#: 不由本管线产出、但同目录存在的 CSV（阶段 0 基线参照，必须**逐字节不变**）
UNTOUCHED = [
    'rank-加权敏感性-徐汇区-2022-2026.csv',
    'rank-标准化-徐汇区-2022-2026.csv',
    'rank-稳健性-徐汇区-2022-2026.csv',
    '趋势分析-徐汇区-2022-2026.csv',
    '缺分对清单.csv',
]


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def run_once(tag):
    print('\n===== 第 %s 遍 =====' % tag)
    for script, what in STEPS:
        r = subprocess.run([sys.executable, str(T / script)],
                           capture_output=True, text=True, cwd=str(A))
        if r.returncode != 0:
            print('❌ %s（%s）失败：' % (script, what))
            print(r.stdout[-1500:])
            print(r.stderr[-800:])
            sys.exit(1)
        print('  ✅ %-22s %s' % (script, what))


def snapshot():
    return {c: md5(A / c) for c in CSVS}


def main():
    n = 3 if '--x3' in sys.argv else 1
    base_untracked = {c: md5(A / c) for c in UNTOUCHED if (A / c).exists()}
    snaps = []
    for i in range(1, n + 1):
        run_once(str(i))
        snaps.append(snapshot())
    ok = all(s == snaps[0] for s in snaps)
    print('\n===== md5 比对（%d 遍）=====' % n)
    for c in CSVS:
        same = len({s[c] for s in snaps}) == 1
        print('  %s %s  %s' % ('✅' if same else '❌', c, snaps[0][c][:12]))
    after_untracked = {c: md5(A / c) for c in UNTOUCHED if (A / c).exists()}
    untouched_ok = base_untracked == after_untracked
    print('\n  管线外的 CSV（须逐字节不变）：%s'
          % ('✅ 全部不变' if untouched_ok else '❌ 有变化：%s'
             % [c for c in after_untracked if base_untracked.get(c) != after_untracked[c]]))
    if not ok or not untouched_ok:
        sys.exit(1)
    print('\n✅ 编排完成：%d 遍 md5 一致，管线外 CSV 未受影响' % n)


if __name__ == '__main__':
    main()
