<!-- TRELLIS:START -->
# Trellis 说明

本文件面向在本项目中工作的 AI 助手。

本项目由 Trellis 管理。你需要的工作知识都在 `.trellis/` 下：

- `.trellis/workflow.md` — 数据分析工作流：阶段划分、何时建任务、skill 路由
- `.trellis/spec/` — 项目规范，按领域分层（**动手前必读**）
  - `spec/data/` — 数据来源、目录、命名、字段与口径
  - `spec/quality/` — 数据正确性校验（七个维度）
  - `spec/analysis/` — 分析方法与结论可靠性验证（九个维度）
  - `spec/guides/` — 跨领域思考指南
- `.trellis/workspace/` — 每个开发者的会话日志与记录
- `.trellis/tasks/` — 进行中与已归档的任务（PRD、检索材料、jsonl 上下文）

若你的平台提供 Trellis 命令（如 `/trellis:finish-work`、`/trellis:continue`），优先使用它们而非手工步骤。
并非所有平台都暴露全部命令。

本块由 Trellis 管理。块外编辑会被保留；块内编辑可能被将来的 `trellis update` 覆盖。

<!-- TRELLIS:END -->

---

# 项目须知（上海学区房数据分析）

## 这不是一个编码项目

本项目**不写代码**，只做数据采集、整理、校验、分析与结论验证。
工作流中不存在编译、单元测试、lint、typecheck 等步骤。

判断「做完了没有」的标准是：

- **数据正确性**：数据通过了 `.trellis/spec/quality/` 定义的七个维度校验，且有可复核的证据
- **结论可靠性**：结论通过了 `.trellis/spec/analysis/` 定义的九个维度验证，且有可复核的证据

## 工作流骨架

```
Phase 1: Plan    规划      → prd.md（问题与范围）design.md（口径与设计）implement.md（执行与判定标准）
Phase 2: Execute 执行      → 2.1 采集/整理 → 2.2 数据校验 → 2.3 分析 → 2.4 结论验证
                             → 2.5 结论网页化（如需对外发布）
Phase 3: Finish  收尾      → 复盘 → 更新规范 → 提交 → /trellis:finish-work
```

**两条硬门禁**（不可绕过）：

1. 2.2 数据正确性校验未通过 → 不得开始 2.3 分析
2. 2.4 结论可靠性验证未通过 → 不得进入 2.5 网页化，也不得进入 Phase 3

> 2.5 生成的页面**必须由结论正文（`analysis/<课题>/分析报告.md`）程序生成，不得手写** ——
> 手写会让页面与已验证的结论脱钩，等于绕过 2.4 门禁。

## 子代理角色映射

| 平台标识 | 本项目角色 |
|----------|------------|
| `trellis-implement` | 数据采集、整理、分析执行 |
| `trellis-check` | 数据正确性校验、结论可靠性验证 |
| `trellis-research` | 资料与来源检索 |

## 数据存放

- 所有业务数据放在 `data/<行政区>/<主题>/`
- 主题目前为：`学校`、`小区`、`规划`
- 每个目录必须有 `来源.md` 登记来源、口径、已知缺陷
- 约定详见 `.trellis/spec/data/directory-structure.md` 与 `data/README.md`

## 报告的诚实性要求

- 「未发现问题」≠「数据无误」
- 「找不到反证」≠「结论成立」
- 未执行的校验 / 验证必须如实说明未执行，不得以「通过」表述
