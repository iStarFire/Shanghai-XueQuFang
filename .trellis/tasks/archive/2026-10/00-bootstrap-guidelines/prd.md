# 引导任务：校准数据规范并补齐来源登记

**你（AI）正在执行这个任务。使用者不会逐字阅读本文件。**

本项目由 `trellis init` 初始化，并已按**数据分析项目**改写为：

- 工作流：`.trellis/workflow.md`（Phase 1 规划 → Phase 2 采集/校验/分析/验证 → Phase 3 收尾）
- 规范：`.trellis/spec/`
  - `data/` —— 目录结构、来源登记、字段与口径
  - `quality/` —— 数据正确性校验（七个维度）
  - `analysis/` —— 分析方法与结论可靠性验证（九个维度）
  - `guides/` —— 跨领域思考指南
- 子代理：`.codebuddy/agents/trellis-{implement,check,research}.md`

**AI 已根据仓库现状预填了上述规范。本任务的目标是让使用者逐条校准它们，
使规范描述的是项目真实状态，而不是 AI 的假设。**

不要一次性倾倒全部内容。先用一段简短的说明开场，然后用对话方式推进。

---

## 当前状态（完成一项就勾掉）

- [ ] 使用者已确认工作流阶段与两条门禁符合预期
- [ ] 使用者已校准 `spec/data/directory-structure.md`（目录与命名约定）
- [ ] 使用者已校准 `spec/data/field-conventions.md`（字段与口径）
- [ ] 使用者已补齐 `data/*/*/来源.md` 中的 `待补充` 字段
- [ ] 使用者已确认 `spec/quality/data-validation.md` 的七维度与判定阈值
- [ ] 使用者已确认 `spec/analysis/conclusion-verification.md` 的九维度与验证方法
- [ ] `README.md` 与 `AGENTS.md` 已复核

---

## 背景：仓库当前的真实数据

```
data/徐汇区/学校/徐汇区-2026-名额到校.pdf
data/徐汇区/规划/【徐汇】【2022】上海市徐汇区单元规划.pdf
data/普陀区/学校/2023普陀名额到校.pdf  /  2024  /  2025
data/普陀区/规划/【普陀】【2022】普陀单元规划.pdf
data/*/小区/                     ← 暂无数据
```

数据来源登记表已建立，但多处为 `待补充` / `待核实` —— 这些必须由使用者补齐，
AI 不得臆造来源、发布主体或发布时间。

---

## 校准清单

### 0. 补齐上下文清单（工作流 1.3）

本任务目录下**没有** `implement.jsonl` / `check.jsonl`。
`task.py start` 对「文件不存在」不做门禁，但为空的文件会被拒绝。
建议在进入执行前整理：

```bash
python3 ./.trellis/scripts/task.py add-context 00-bootstrap-guidelines implement \
  ".trellis/spec/data/source-registry.md" "来源登记表的必填字段与格式"
python3 ./.trellis/scripts/task.py add-context 00-bootstrap-guidelines check \
  ".trellis/spec/quality/index.md" "校验规范入口，用于核对规范是否被正确落地"
python3 ./.trellis/scripts/task.py validate 00-bootstrap-guidelines
```

### 1. 工作流（`.trellis/workflow.md`）

逐条与使用者确认：

| 项 | 需要确认的内容 |
|----|----------------|
| 阶段划分 | Plan / Execute / Finish 三步是否符合预期 |
| 门禁 | 「2.2 数据校验未过不得分析」「2.4 结论验证未过不得收尾」是否接受 |
| 步骤顺序 | 2.1 采集 → 2.2 校验 → 2.3 分析 → 2.4 验证 |
| 产物命名 | `validation/data-validation.md`、`validation/conclusion-review.md`、`analysis/` 是否符合习惯 |
| 子代理角色 | `trellis-implement`（执行）/ `trellis-check`（校验）/ `trellis-research`（检索）的映射是否清楚 |

### 2. 数据规范（`.trellis/spec/data/`）

- `directory-structure.md`：行政区命名、主题边界、文件名带时点、
  原始 PDF 直接放主题目录（不搬迁）——是否符合使用者预期
- `source-registry.md`：`来源.md` 的必填字段是否够用/是否太多
- `field-conventions.md`：
  - 「名额到校」字段（`year` / `junior_high_school` / `senior_high_school` /
    `quota_plan` / `quota_actual` / `source_page` …）是否覆盖实际表格列
  - 「规划」（单元规划）字段是否覆盖实际摘录需求
  - 单位与枚举取值（`school_type` / `ownership` / `doc_type` / `status`）是否需要增删

### 3. 来源登记（`data/*/*/来源.md`）

这是本任务**最实际的产出**。逐个目录与使用者确认并补齐：

- [ ] `data/徐汇区/学校/来源.md` — 补齐原文链接、发布主体、发布时间
- [ ] `data/徐汇区/规划/来源.md` — 补齐链接、文号、批复/发布日期
- [ ] `data/普陀区/学校/来源.md` — 补齐三份 PDF 的链接、主体、时间
- [ ] `data/普陀区/规划/来源.md` — 补齐链接、文号、批复/发布日期

**注意**：使用者若也不知道来源链接，就把该项保持为 `待补充`，
并在「已知缺陷」栏明确写「来源链接缺失」。**不要臆造 URL。**

### 4. 校验与验证规范（`spec/quality/`、`spec/analysis/`）

- 七维度（完整性/唯一性/值域/一致性/时效性/可追溯性/口径一致性）是否够用
- 值域阈值（如 `unit_price_cny_per_sqm ∈ (0, 500000]`）是否符合实际
- 九维度（计算复核/口径一致/数据链路/样本代表性/对比基准/因果警惕/
  反向证据/稳健性/局限声明）是否需要调整
- 「必须显著标注的情况」阈值（样本 < 20、覆盖 < 50%、时点 > 6 个月）是否合理

### 5. 文档

- [ ] `README.md` 的项目目标、目录结构、工作流描述是否准确
- [ ] `AGENTS.md` 的须知是否准确

---

## 纪律要求（重要）

1. **不要臆造来源信息** —— 链接、发布主体、发布时间、文号都必须是使用者确认过的。
   不知道就保持 `待补充` 并写进「已知缺陷」。
2. **一次只问一个问题**，给选项而不是开放式提问。
3. **能自己查的不要问使用者**：文件是否存在、字段是否齐全、目录结构如何，直接查。
4. **不要为了「填满模板」而写占位内容** —— 宁可留 `待补充`。
5. 校准完成后，把结论写回对应文件，并勾掉上面的复选框。

---

## 完成

使用者确认全部勾选项后，引导其运行：

```bash
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive 00-bootstrap-guidelines
```

归档后，之后加入的新成员会得到一个 `00-join-<slug>` 引导任务，而不是本任务。

---

## 建议的开场白

「欢迎使用 Trellis！init 已经把工作流和规范按数据分析场景配置好了，
但它们是我基于仓库现状**预填**的，需要你来校准 —— 尤其是数据来源登记表里
还有几处 `待补充`，我不会替你猜。先从工作流的两条门禁开始对一遍，
还是先补来源登记？」
