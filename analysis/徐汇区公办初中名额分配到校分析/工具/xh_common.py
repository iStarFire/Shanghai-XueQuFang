#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""徐汇分析：生成脚本与校验脚本**共用的算法实现**。

与普陀 `工具/pt_common.py` **同源**（内容有意保持一致，便于三区横向核对）。
若修改本文件，请同步普陀那份（`analysis/普陀区公办初中名额分配到校分析/工具/pt_common.py`）。

## 为什么要共享
`implement.md` 6.1 要求「校验脚本**与生成脚本共用平均秩实现**」。
校验脚本若自己重写一套秩算法，即使逻辑写错也会与生成脚本「一致」，
形成**假门禁**（用同一种错误验证自己）。故抽出本模块，两侧都 import。

## 内容
- `midrank(pairs)`：当年位次（**平均秩**，并列同名次）。
  定义 rank(v) = #{w > v} + (#{w == v} + 1) / 2 —— 与旧管线 `build_wide.py`
  的 `rank_of` 同一口径（`1 + hi + (eq-1)/2` 是等价写法）。
- `weighted_mean(pairs)`：名额加权均分 `Σ(分×名额)/Σ名额`。
- `p_from_rank(r, n)`：分位 `P = 1 − (r − 1)/(n − 1)`，越大越强。
"""
import statistics as st

__all__ = ['midrank', 'weighted_mean', 'p_from_rank']


def midrank(pairs):
    """当年位次 = 平均秩（降序，并列同名次）。

    pairs: [(key, value), ...]，value 为 None 的项请先过滤。key 可为任意可哈希对象
    （生成侧用 `(code, year)` 元组，故本函数不要求 key 是字符串）。
    """
    xs = [v for _, v in pairs]
    return {c: sum(1 for w in xs if w > v) + (sum(1 for w in xs if w == v) + 1) / 2
            for c, v in pairs}


def weighted_mean(pairs):
    """名额加权均分。pairs: [(score, quota), ...]；总名额为 0 时返回 None。"""
    num = sum(s * q for s, q in pairs)
    den = sum(q for _, q in pairs)
    return num / den if den else None


def p_from_rank(r, n):
    """分位 P = 1 − (r − 1)/(n − 1)；n <= 1 时无定义（返回 None）。"""
    return 1 - (r - 1) / (n - 1) if n and n > 1 else None


def mean(xs):
    """算术平均；空序列返回 None（不返回 0，避免「无数据」被当成「均值为 0」）。"""
    return st.fmean(xs) if xs else None
