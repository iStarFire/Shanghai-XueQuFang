#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""普陀分析：生成脚本与校验脚本**共用的算法实现**。

## 为什么要共享
`implement.md` 6.1 要求「三层校验脚本**与生成脚本共用平均秩实现**」。
若校验脚本自己重写一套秩算法，即使逻辑写错也会与生成脚本「一致」，
形成**假门禁**（用同一种错误验证自己）。故把关键算法抽到本模块，
生成侧与校验侧都 `import`，从结构上排除「两套实现」。

## 共用内容
- `midrank(pairs)`：当年位次（**平均秩**，并列同名次）。生成侧用于
  `rank_base4_eq_{y}` / `rank_base4_wq_{y}`，校验侧用于独立复算同一列。
  定义：rank(v) = #{w > v} + (#{w == v} + 1) / 2
- `weighted_mean(pairs)`：名额加权均分。
- `p_from_rank(r, n)`：分位 P = 1 − (r − 1)/(n − 1)。
"""
import statistics as st

__all__ = ['midrank', 'weighted_mean', 'p_from_rank']


def midrank(pairs):
    """当年位次 = 平均秩（降序，并列同名次）。

    pairs: [(key, value), ...]，value 为 None 的项请先过滤。
    返回 {key: rank}。rank = #{w > v} + (#{w == v} + 1) / 2
    """
    xs = [v for _, v in pairs]
    out = {}
    for c, v in pairs:
        b = sum(1 for w in xs if w > v)
        e = sum(1 for w in xs if w == v)
        out[c] = b + (e + 1) / 2
    return out


def weighted_mean(pairs):
    """名额加权均分。pairs: [(score, quota), ...]；总名额为 0 时返回 None。"""
    num = sum(s * q for s, q in pairs)
    den = sum(q for _, q in pairs)
    return num / den if den else None


def p_from_rank(r, n):
    """分位 P = 1 − (r − 1)/(n − 1)；n <= 1 时无定义。"""
    return 1 - (r - 1) / (n - 1) if n and n > 1 else None
