# 执行清单：普陀报告重构

## 2.3 计算

- [ ] `analysis/普陀区公办初中名额分配到校分析/工具/multi_metric_pt.py`
  - 三组（all / head / tail）逐年 P：从原始分数线重算
  - 自校验：`P_all` vs `rank-标准化-普陀区-2022-2026.csv` 的 `P`（容差 5e-4）
  - 从既有 CSV 读入：Z / ZR / 均名 / P_lin / P_exp / P_recent3 及其名次
  - 计算 `P_comb`、`rank_comb`；输出 `rank-多口径总表-普陀区-2022-2026.csv`
  - 控制台打印：综合榜全 32 所、三组相关性、偏科最大的学校

## 2.3 报告重构

- [ ] 写汇编脚本（`/tmp/assemble_putuo.py`）：
  - 抽取旧块：局限声明、0 样本、A2、A3+A3.1、A5、A7、A8、A9.1–A9.4
  - 拼接新块：核心结论、1 章增补（口径直白解释）、2 章（表 2-1/2-2）、3 章引言与合并、5 章梅陇合并、附录框架
  - 抽取后打印各块行数 → 人工核对无丢块
- [ ] 新写块经 `write_to_file` 落成独立 md 片段，由汇编脚本拼接
- [ ] 全文旧编号引用（A1…A9）替换为新章节号

## 2.3 图片与网页

- [ ] `/tmp/build_rank_pt.py` 改为读多口径总表，列：综合名次 | 初中 | P综合 | 全身(名) | 头部(名) | 尾部(名) | 覆盖
- [ ] 重渲染 `排序表.png`
- [ ] 重跑 `工具/build_html_pt.py`，确认目录与章节

## 2.4 独立验证

- [ ] `validation/verify_multi_metric.py`：
  1. 三组 P 与 P_comb 独立复算（不同实现）
  2. `P_all` vs 既有主口径 CSV 逐值
  3. 名次与 CSV 一致
  4. 报告表 2-1/2-2 抽样正则核对（全 32 所）
- [ ] `validation/conclusion-review.md`

## 提交

- [ ] 报告 + index.html + 工具脚本 + 新 CSV + 任务文件
