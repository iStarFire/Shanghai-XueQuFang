# Finish Work（收尾）

结束当前会话：归档当前任务（以及用户想一并清理的其他已完成任务），并记录会话日志。
**数据与分析变更的提交不在这里做** —— 那发生在工作流 Phase 3.4，先于本命令。

## 第 1 步：查看当前状态

```bash
python3 ./.trellis/scripts/get_context.py --mode record
```

它会打印：

- **我的进行中任务** —— 除当前任务外，判断是否还有其他任务其实已完成
  （验收标准已满足、结论已验证）且应在本轮归档
- **Git 状态** —— 快速查看哪些文件是脏的
- **最近提交** —— 第 4 步 `--commit` 需要用到它们的 hash

若 `--mode record` 显示出与本会话无关的其他已完成任务，用一次性确认向用户提出：
「这 N 个任务看起来已完成 —— 本轮一并归档？[y/N]」。默认否；
当前任务始终在第 3 步归档。

## 第 2 步：一致性检查 —— 给脏路径分类

```bash
git status --porcelain
```

过滤掉 `.trellis/workspace/` 与 `.trellis/tasks/` 下的路径 ——
它们由 `add_session.py` 与 `task.py archive` 的自动提交管理，本轮本身就会变脏。

对每个剩余脏路径，判断它属于**当前任务**还是**其他并行工作**（例如另一个终端窗口在编辑同一仓库）：

- 出现在当前任务的 `prd.md` / `implement.jsonl` / `check.jsonl` 中 → 当前任务
- 属于任务声明范围内（如对应行政区的 `data/` 目录），或你记得本会话改过 → 当前任务
- 属于无关区域且你本会话没有印象碰过 → 其他并行工作

然后分流：

- **任何剩余路径看起来是当前任务的工作** —— 中止并提示：
  > 「工作区还有本任务未提交的变更：`<列表>`。请回到工作流 Phase 3.4 先提交，再运行 `/trellis:finish-work`。」

  这里**不要**运行 `git commit`，也不要提示用户去提交。
  用户回到 Phase 3.4，由 AI 在那里主导批量提交。
- **所有剩余路径看起来都无关**（其他窗口的工作）—— 报告一次并继续第 3 步：
  > 「提示：以下脏文件不在本任务范围内，留给另一个窗口处理：`<列表>`。」
- **确实无法判断** —— 问用户一次：「`<列表>` 是本任务忘了提交的工作，还是另一个窗口的？（提交 / 忽略）」，再按其答复分流。

## 第 3 步：归档任务

```bash
python3 ./.trellis/scripts/task.py archive <task-name>
```

至少归档当前任务（若有）。加上第 1 步用户确认的额外任务。
每次归档会通过脚本的自动提交产生一个 `chore(task): archive ...` 提交。

若无当前任务且用户未确认任何清理归档，跳过本步。

## 第 4 步：记录会话日志

```bash
python3 ./.trellis/scripts/add_session.py \
  --title "Session Title" \
  --commit "hash1,hash2" \
  --summary "Brief summary"
```

`--commit` 使用 Phase 3.4 产生的工作提交 hash（见第 1 步的最近提交列表，或 `git log --oneline`）。
不要包含第 3 步的归档提交 hash。本命令会产生一个 `chore: record journal` 提交。

最终 git log 顺序：`<Phase 3.4 的工作提交>` → `chore(task): archive ...`（一个或多个）→ `chore: record journal`。
