# 继续当前任务

恢复当前任务的工作 —— 从 `.trellis/workflow.md` 中正确的阶段/步骤接着做。

---

## 第 1 步：加载当前上下文

```bash
python3 ./.trellis/scripts/get_context.py
```

确认：当前任务、git 状态、最近提交。

## 第 2 步：加载 Phase Index

```bash
python3 ./.trellis/scripts/get_context.py --mode phase
```

展示 Phase Index（Plan / Execute / Finish）与路由、skill 映射。

## 第 3 步：判断当前所处位置

`get_context.py` 会显示当前任务的 `status` 字段。按 `status` + 产物存在情况路由。
本命令只是替代用户记忆流程，本身**不代表**批准执行。

- `status=planning` 且无 `prd.md` → **1.1**（加载 `trellis-brainstorm`）
- `status=planning` 且只有 `prd.md` → 判断任务属于轻量还是复杂。
  轻量可进入 **1.4** 评审；复杂则回到 **1.1** 补 `design.md` + `implement.md`
- `status=planning` 且复杂产物齐备、但 jsonl 未整理（空或只剩 `_example` 占位行）→ **1.3**
- `status=planning` 且必需产物齐备、jsonl 已整理 → **1.4**（请用户评审；用户确认后才运行 `task.py start`）
- `status=in_progress` 且尚未采集/整理数据 → **2.1**
- `status=in_progress` 且数据已落盘、尚未校验 → **2.2 数据正确性校验**
- `status=in_progress` 且 2.2 已通过、尚未分析 → **2.3**
- `status=in_progress` 且分析已产出、尚未验证 → **2.4 结论可靠性验证**
- `status=in_progress` 且 2.2 与 2.4 均通过 → **3.3**（更新规范）→ **3.4**（提交）
- `status=completed`（少见，通常直接归档）→ 走归档流程

阶段规则（完整说明见 `.trellis/workflow.md`）：

1. 阶段内**按顺序**执行 —— `[required]` 步骤不得跳过
2. `[once]` 步骤在必需产物已存在时视为完成。`prd.md` 只对轻量任务足够；
   复杂任务还需 `design.md` 与 `implement.md`
3. **门禁不可绕过**：2.2 未通过不得进入 2.3；2.4 未通过不得进入 Phase 3
4. 若发现需要，可以回到更早的阶段

## 第 4 步：加载具体步骤

确定恢复点后：

```bash
python3 ./.trellis/scripts/get_context.py --mode phase --step <X.X> --platform codebuddy
```

按加载到的指引执行。每个 `[required]` 步骤完成后进入下一步。

---

## 参考

完整工作流与详细步骤位于 `.trellis/workflow.md`。本命令只是入口，权威指引在那份文件里。
