# 数据分析工作流（Development Workflow）

> 本项目是**上海学区房数据分析项目**，不是软件工程项目。
> 本工作流中不存在「写代码」「编译」「单元测试」等步骤；取而代之的是
> **数据采集 → 数据正确性校验 → 分析 → 结论可靠性验证**。
> 术语对照与项目约定见 `README.md`。

---

## 核心原则（Core Principles）

1. **先规划后执行** — 先想清楚要回答什么问题，再动手找数据、算结论
2. **规范注入，而非记忆** — 项目规范通过 hook / skill 注入，不靠临场回忆
3. **一切落盘** — 检索结果、判断依据、口径定义、修正记录都写进文件；对话会被压缩，文件不会
4. **增量推进** — 一次只推进一个任务、一个结论
5. **沉淀经验** — 每个任务结束后，把新认知写回 `.trellis/spec/`

### 本项目特有的两条硬原则

6. **数据正确性不可假设** — 任何进入分析的数值，必须经过 2.2 数据正确性校验，
   并留下可复核的校验记录。未经校验的数据不得用于任何结论。
7. **结论必须可证伪** — 任何对外输出的结论，必须经过 2.4 结论可靠性验证，
   明确写出：支撑数据、分析方法、口径、反向证据、局限与不确定性。

---

## Trellis 系统

### 开发者身份（Developer Identity）

首次使用时初始化身份：

```bash
python3 ./.trellis/scripts/init_developer.py <your-name>
```

生成 `.trellis/.developer`（已 gitignore）+ `.trellis/workspace/<your-name>/`。

### 规范系统（Spec System）

`.trellis/spec/` 存放**数据分析规范**，按领域分层：

| 目录 | 内容 |
|------|------|
| `.trellis/spec/data/` | 数据来源、目录结构、文件命名、字段与口径定义 |
| `.trellis/spec/quality/` | 数据正确性校验规范（必读，2.2 门禁依据） |
| `.trellis/spec/analysis/` | 分析方法与结论可靠性验证规范（必读，2.4 门禁依据） |
| `.trellis/spec/guides/` | 跨领域思考指南 |

- `.trellis/spec/<layer>/index.md` — 入口文件，含 **开工前检查清单（Pre-Development Checklist）** 与 **质量校验（Quality Check）**；具体规范在同目录的其他 `.md` 中。
- `.trellis/spec/guides/index.md` — 通用思考指南。

```bash
python3 ./.trellis/scripts/get_context.py --mode packages   # 列出可用的规范分层
```

**何时更新规范**：发现新的数据来源 · 新增/修订口径定义 · 踩坑后的防错约定 · 新的判断标准。

### 任务系统（Task System）

每个任务位于 `.trellis/tasks/{MM-DD-name}/`，包含 `task.json`、`prd.md`、可选的 `design.md`、`implement.md`、`research/`，以及面向子代理的上下文清单 `implement.jsonl` / `check.jsonl`。

```bash
# 任务生命周期
python3 ./.trellis/scripts/task.py create "<title>" [--slug <name>] [--parent <dir>]
python3 ./.trellis/scripts/task.py start <name>          # 设为当前任务（会话级）
python3 ./.trellis/scripts/task.py current --source      # 查看当前任务与来源
python3 ./.trellis/scripts/task.py finish                # 清除当前任务
python3 ./.trellis/scripts/task.py archive <name>        # 归档到 archive/{year-month}/
python3 ./.trellis/scripts/task.py list [--mine] [--status <s>]
python3 ./.trellis/scripts/task.py list-archive

# 上下文清单（子代理注入用）。
# implement.jsonl / check.jsonl 在 task create 时被写入占位行；AI 在规划阶段填入真实条目。
# 清单为空时 validate 失败、start 拒绝执行 —— 子代理会拿到零规范上下文。
python3 ./.trellis/scripts/task.py add-context <name> <action> <file> <reason>
python3 ./.trellis/scripts/task.py list-context <name> [action]
python3 ./.trellis/scripts/task.py validate <name>

# 任务元数据
python3 ./.trellis/scripts/task.py set-branch <name> <branch>
python3 ./.trellis/scripts/task.py set-base-branch <name> <branch>
python3 ./.trellis/scripts/task.py set-scope <name> <scope>

# 层级（父/子任务）
python3 ./.trellis/scripts/task.py add-subtask <parent> <child>
python3 ./.trellis/scripts/task.py remove-subtask <parent> <child>
```

> `python3 ./.trellis/scripts/task.py --help` 是权威且最新的命令清单。

**当前任务机制**：`task.py create` 创建任务目录并（在会话身份可用时）自动设置当前任务指针；`task.py start` 写入同一指针并把 `task.json.status` 从 `planning` 翻转为 `in_progress`。状态存放于 `.trellis/.runtime/sessions/`。

### 工作区系统（Workspace System）

在 `.trellis/workspace/<developer>/` 记录每次 AI 会话：

- `journal-N.md` — 会话日志，单文件上限 2000 行，超出自动新建 `journal-(N+1).md`
- `index.md` — 个人索引（会话总数、最后活跃时间）

```bash
python3 ./.trellis/scripts/add_session.py --title "Title" --commit "hash" --summary "Summary"
```

### 上下文脚本（Context Script）

```bash
python3 ./.trellis/scripts/get_context.py                            # 完整会话运行时上下文
python3 ./.trellis/scripts/get_context.py --mode packages            # 可用规范分层
python3 ./.trellis/scripts/get_context.py --mode phase --step <X.Y>  # 某一步的详细指引
```

---

<!--
  工作流状态面包屑契约（修改下方 tag 块前必读）

  `## Phase Index` 中内嵌的 [workflow-state:STATUS] 块是每轮
  `<workflow-state>` 面包屑的**唯一真源**。CodeBuddy 的
  UserPromptSubmit hook（.codebuddy/hooks/inject-workflow-state.py）
  只解析它们，脚本内不再有任何兜底文案。

  STATUS 字符集：[A-Za-z0-9_-]+。hook 找不到 tag 时会退化为一句
  "Refer to workflow.md for current step."，这是刻意设计的可见失败，
  以便使用者发现并修复 workflow.md。

  不变量：
    Phase Index 中每个标记为 `[required · once]` 的步骤，都必须在其所属
    阶段的 [workflow-state:*] 块里有一条对应的强制提示行。面包屑是唯一的
    每轮通道；若某个强制步骤没出现在面包屑里，AI 会静默跳过它。

  TAG ↔ PHASE 对应：
    [workflow-state:no_task]      → 无当前任务（Phase 1 之前）
    [workflow-state:task_error]   → 当前任务记录不可读，先修复再继续
    [workflow-state:planning]     → Phase 1 全程（status='planning'）
    [workflow-state:planning-inline] → Phase 1 的内联变体（本平台不使用）
    [workflow-state:in_progress]  → Phase 2 + Phase 3.2-3.4
    [workflow-state:in_progress-inline] → Phase 2/3 的内联变体（本平台不使用）
    [workflow-state:completed]    → 归档后（当前为 DEAD 分支，保留占位）

  修改清单：
    - 改动 [workflow-state:STATUS] 块时，同步检查对应阶段的 `[required · once]` 步骤
    - `## Phase Index` 与 `## Phase 1: Plan` 两个标题被
      .codebuddy/hooks/session-start.py 与 .trellis/scripts/common/workflow_phase.py
      按字面匹配，**不要改名**
    - `#### X.X 标题` 形式的步骤标题被 get_context.py --mode phase --step 解析，
      步骤正文中出现行首 `---` / `## ` / `#### ` 会截断该步骤
-->

## Phase Index

```
Phase 1: Plan    → 分类请求、取得建任务同意，然后产出规划产物
Phase 2: Execute → 采集/整理数据 → 数据正确性校验 → 分析 → 结论可靠性验证 → 结论网页化
Phase 3: Finish  → 复盘、更新规范、提交、收尾
```

### 请求分类（Request Triage）

- 简单问答或小任务：只问一句「这一轮是否需要建立 Trellis 任务」。用户说不需要，则本轮不走 Trellis。
- 复杂任务：询问是否可建立 Trellis 任务并进入规划。用户拒绝时，不要自行大范围展开执行；先解释、澄清范围，或建议拆小。
- **用户同意建任务 ≠ 同意开始执行**。规划永远先行。

### 规划产物（Planning Artifacts）

| 产物 | 内容 | 不应包含 |
|------|------|----------|
| `prd.md` | 要回答的问题、数据范围（行政区/时间窗/学段）、口径要求、验收标准 | 技术设计、执行清单 |
| `design.md` | 分析方法设计：数据来源清单、字段定义、指标口径与计算方式、对比基准、偏差来源、局限声明 | 逐步操作流水账 |
| `implement.md` | 执行计划：有序清单（采集→校验→分析→验证）、每步的校验/验证命令与判定标准、回滚点 | 需求正文 |
| `implement.jsonl` / `check.jsonl` | 子代理需要的规范与检索材料清单 | 替代 `implement.md` |

- 轻量任务允许只有 `prd.md`。
- 复杂任务在 `task.py start` 之前必须同时具备 `prd.md`、`design.md`、`implement.md`。

### 父 / 子任务树

一个请求包含多个**可独立验证**的交付物时使用父任务。父任务持有原始需求、子任务映射、跨子任务验收标准与最终整合校验；除自身有直接工作外，父任务通常不是执行对象。

父/子结构不是依赖系统：若子任务 B 依赖 A，把顺序写进 B 的 `prd.md` / `implement.md`，并保证每个子任务的验收标准可独立检验。

新建子任务：`task.py create "<title>" --slug <name> --parent <parent-dir>`；关联既有任务：`task.py add-subtask <parent> <child>`；解除：`task.py remove-subtask <parent> <child>`。

<!-- 每轮面包屑：无当前任务时（Phase 1 之前） -->

[workflow-state:no_task]
当前无任务。先分类本轮请求，在创建任何 Trellis 任务之前取得用户同意。
简单问答/小任务：只问这一轮是否需要建立 Trellis 任务；用户说不需要则本轮跳过 Trellis。
复杂任务：询问是否可以建立 Trellis 任务并进入规划阶段；用户拒绝时，先解释、澄清范围或建议拆小。
[/workflow-state:no_task]

<!-- 每轮面包屑：当前任务记录无法读取时 -->

[workflow-state:task_error]
当前任务记录无法读取。不要创建或激活另一个任务。
检查上面指出的任务目录并修复其 task.json：必须是合法 JSON 对象且 status 非空。
保留已有任务字段与产物。若无法安全判断正确的 status，先询问用户再重建记录。
[/workflow-state:task_error]

### Phase 1: Plan
- 1.0 创建任务 `[required · once]`（仅在取得建任务同意后）
- 1.1 需求与分析目标探索 `[required · repeatable]`（`prd.md`；复杂任务还需 `design.md` + `implement.md`）
- 1.2 资料检索 `[optional · repeatable]`
- 1.3 配置上下文 `[required · once]`（子代理调度平台必做；内联平台跳过）
- 1.4 激活任务 `[required · once]`（评审门禁后执行 `task.py start`，status → in_progress）
- 1.5 完成标准

<!-- 每轮面包屑：Phase 1 全程（status='planning'） -->

[workflow-state:planning]
加载 `trellis-brainstorm`，停留在规划阶段。
轻量任务：`prd.md` 即可。复杂任务：完成 `prd.md`、`design.md`、`implement.md`，并在 `task.py start` 前请用户评审。
多交付物：考虑父任务 + 可独立验证的子任务；依赖关系写进子任务产物，不要靠树结构暗示。
子代理模式：在 start 前整理 `implement.jsonl` 与 `check.jsonl`（规范/检索清单）。
本阶段必须显式确定两件事：数据正确性如何校验（2.2 的判定标准）、结论可靠性如何验证（2.4 的判定标准）。
[/workflow-state:planning]

<!-- 每轮面包屑：Phase 1 内联模式变体（本平台不使用，保留结构占位） -->

[workflow-state:planning-inline]
加载 `trellis-brainstorm`，停留在规划阶段。
轻量任务：`prd.md` 即可。复杂任务：完成 `prd.md`、`design.md`、`implement.md`，并在 `task.py start` 前请用户评审。
内联模式：跳过 jsonl 整理；Phase 2 通过 `trellis-before-dev` 读取产物与规范。
[/workflow-state:planning-inline]

### Phase 2: Execute

顺序固定，不可跳步：

```
2.1 数据采集与整理  →  2.2 数据正确性校验  →  2.3 分析与结论产出  →  2.4 结论可靠性验证
                                                              →  2.5 结论网页化与发布
```

- 2.1 数据采集与整理 `[required · repeatable]`
- 2.2 数据正确性校验 `[required · repeatable]` ← **未通过不得进入 2.3**
- 2.3 分析与结论产出 `[required · repeatable]`
- 2.4 结论可靠性验证 `[required · repeatable]` ← **未通过不得进入 2.5 与 Phase 3**
- 2.5 结论网页化与发布 `[on demand]` ← **未过 2.4 不得生成对外页面**
- 2.6 回滚 `[on demand]`

<!-- 每轮面包屑：status='in_progress'（覆盖 Phase 2 全部 + Phase 3.2-3.4） -->

[workflow-state:in_progress]
工具角色：`trellis-implement` = 数据采集/整理与分析执行子代理；`trellis-check` = 数据校验与结论验证子代理；`trellis-research` = 资料检索子代理。三者都是以 Task/Agent 形式调用的子代理，不是 Skill。
流程：`trellis-implement`（2.1 采集/整理）→ `trellis-check`（2.2 数据正确性校验）→ `trellis-implement`（2.3 分析）→ `trellis-check`（2.4 结论可靠性验证）→ `trellis-implement`（2.5 结论网页化，如需发布）→ `trellis-update-spec` → 提交（Phase 3.4）→ `/trellis:finish-work`。
**门禁**：2.2 未通过不得开始 2.3；2.4 未通过不得进入 2.5 与 Phase 3。校验/验证记录必须落盘到任务目录（`validation/` 或 `research/`），只在对话里说「已校验」不算完成。
子代理自我豁免：若已作为 `trellis-implement` 运行，不要再派 `trellis-implement` / `trellis-check`；若已作为 `trellis-check` 运行，不要再派同类。派发只由主会话发起。
派发提示词首行写 `Active task: <task.py current 返回的路径>`。上下文读取顺序：jsonl 条目 → `prd.md` → `design.md`（如有）→ `implement.md`（如有）。
[/workflow-state:in_progress]

<!-- 每轮面包屑：内联模式变体（本平台不使用，保留结构占位） -->

[workflow-state:in_progress-inline]
流程：`trellis-before-dev` → 采集/整理 → `trellis-check` 数据校验 → 分析 → `trellis-check` 结论验证 → `trellis-update-spec` → 提交（Phase 3.4）→ `/trellis:finish-work`。
内联模式下不要派发 implement/check 子代理。
上下文读取顺序：`prd.md` → `design.md`（如有）→ `implement.md`（如有），外加 skill 加载的相关规范/检索材料。
[/workflow-state:in_progress-inline]

### Phase 3: Finish
- 3.2 复盘 `[on demand]`
- 3.3 规范更新 `[required · once]`
- 3.4 提交变更 `[required · once]`
- 3.5 收尾提醒

> 说明：3.1 已并入 2.4（末轮全量验证）与 3.4（提交前置检查），编号保持稳定以免破坏外部引用。

<!-- 每轮面包屑：status='completed'（当前为 DEAD 分支，保留占位） -->

[workflow-state:completed]
变更已提交。执行 `/trellis:finish-work`；若工作区仍为脏，先回到 Phase 3.4。
[/workflow-state:completed]

### Rules

1. 先判断自己处于哪个 Phase，再从该 Phase 的下一步继续
2. Phase 内按顺序执行；`[required]` 步骤不可跳过
3. Phase 可以回滚（例如执行阶段发现 prd 缺陷 → 回到 Plan 修正后再进入 Execute）
4. 标记 `[once]` 的步骤，若产物已存在则跳过，不要重复执行
5. 产物是否存在决定下一步走向；缺少 `design.md` / `implement.md` 对轻量任务是合法的，对复杂任务则属于规划不完整
6. **数据与结论门禁优先级最高**：任何「先出结论、事后再补校验」的做法都违反本工作流

### Active Task Routing

用户请求命中以下意图时，先路由，再按需加载对应步骤详情：

- 规划、需求不清 → `trellis-brainstorm`
- `in_progress` 下的采集/整理/分析 → 派发 `trellis-implement`
- 数据正确性校验、结论可靠性验证、对已有结论的质疑 → 派发 `trellis-check`
- 反复调试同一问题 → `trellis-break-loop`；规范更新 → `trellis-update-spec`

### Guardrails

- 建任务同意 ≠ 执行同意；执行要等产物评审通过并执行 `task.py start`
- 轻量任务允许只有 PRD；复杂任务必须有 `design.md` + `implement.md`
- 规划必须落盘为任务产物；**校验与验证必须在完成汇报之前真实执行并落盘**
- 不得把「未见异常」当作「已正确」：校验要有明确的判定标准与失败样例
- 不得用单一数据源的单点结论支撑对外输出；结论需注明口径、样本量与不确定性

### Loading Step Detail

每一步的详细指引：

```bash
python3 ./.trellis/scripts/get_context.py --mode phase --step <step>
# 例：python3 ./.trellis/scripts/get_context.py --mode phase --step 2.2
```

---

## Phase 1: Plan

目标：分类请求，在需要时取得建任务同意，并产出进入执行前所需的规划产物。

#### 1.0 创建任务 `[required · once]`

仅在取得建任务同意后创建任务目录。该命令把 status 置为 `planning`、写入 `task.json`、生成默认 `prd.md`，并在会话身份可用时自动指向新任务：

```bash
python3 ./.trellis/scripts/task.py create "<task title>" --slug <name>
```

`--slug` 只是可读名称，**不要**带 `MM-DD-` 日期前缀，`task.py create` 会自动加上。

任务树场景：先建父任务，再用 `--parent <parent-dir>` 创建各子任务。不要因为子任务存在就启动父任务；启动「下一个可独立验证交付物」所属的子任务。

命令成功后，每轮面包屑自动切换为 `[workflow-state:planning]`。

此步只运行 `create`，不要顺手 `start`。`start` 会把 status 翻成 `in_progress`，在规划产物评审前就把面包屑切到执行阶段。`start` 留给 1.4。

若 `python3 ./.trellis/scripts/task.py current --source` 已指向某任务，跳过本步。

#### 1.1 需求与分析目标探索 `[required · repeatable]`

加载 `trellis-brainstorm` skill，按其指引与用户交互式探索需求。

brainstorm 会引导你：

- 一次只问一个问题
- 能检索就不要问用户
- 优先给选项而不是开放式提问
- 每次得到答复后立刻更新 `prd.md`
- 交付物可独立验证时，拆成父任务 + 子任务
- `prd.md` 只写需求与验收标准
- 复杂任务在进入执行前产出 `design.md` 与 `implement.md`

**数据分析项目额外必须明确的四项**（写进 `prd.md` / `design.md`）：

1. **问题边界** — 要回答什么、不回答什么；结论服务于什么决策
2. **数据范围** — 行政区、时间窗、学段、房屋类型等口径边界
3. **数据正确性校验标准** — 2.2 用什么判定「数据可信」（见 `.trellis/spec/quality/`）
4. **结论可靠性验证标准** — 2.4 用什么判定「结论站得住」（见 `.trellis/spec/analysis/`）

需求变化时回到本步并修订相关产物。

#### 1.2 资料检索 `[optional · repeatable]`

检索可发生在需求探索期间的任何时刻。范围不限于本地：招生政策、对口划片细则、学校信息、市场数据、行业分析方法等，都可以用可用工具（知识库、skill、联网检索等）获取。

派发检索子代理：

- **Agent 类型**：`trellis-research`
- **任务描述**：检索 <具体问题>
- **硬性要求**：检索结果必须落盘到 `{TASK_DIR}/research/`

**检索产物约定**：

- 一个主题一个文件（如 `research/徐汇区对口入学政策-2026.md`）
- 记录来源链接、发布时间、发布主体、原文关键段落（不要只写结论）
- 记录数据可得性、颗粒度、更新频率，以及哪些字段缺失
- 标注你发现的可用规范文件路径，便于后续引用

brainstorm 与检索可自由交替。

**关键原则**：检索产物必须写入文件，不能只留在对话里。对话会被压缩，文件不会。

#### 1.3 配置上下文 `[required · once]`

整理 `implement.jsonl` 与 `check.jsonl`，让 Phase 2 的子代理拿到正确的规范/检索上下文。这两个文件在 `task create` 时已写入一行自描述的 `_example` 占位行；本步的职责是填入真实条目。

**位置**：`{TASK_DIR}/implement.jsonl` 与 `{TASK_DIR}/check.jsonl`（已存在）。

**格式**：每行一个 JSON 对象 — `{"file": "<path>", "reason": "<why>"}`。路径相对于仓库根。

**应放入**：

- **规范文件** — `.trellis/spec/<layer>/index.md` 及该任务确实需要遵守的具体规范文件
- **检索文件** — 子代理需要查阅的 `{TASK_DIR}/research/*.md`

**不应放入**：

- 数据文件本体（`data/**`）— 子代理在执行时自行读取
- 你即将修改的文件 — 同理

**两个文件的划分**：

- `implement.jsonl` → 采集/整理/分析子代理需要的规范与检索材料
- `check.jsonl` → 校验/验证子代理需要的规范（`spec/quality/`、`spec/analysis/`）与同一批检索材料

清单不能替代 `implement.md`：`implement.md` 是给人看的执行计划，jsonl 只声明要注入的文件。

**发现相关规范**：

```bash
python3 ./.trellis/scripts/get_context.py --mode packages
```

**追加条目**：

```bash
python3 ./.trellis/scripts/task.py add-context "$TASK_DIR" implement "<path>" "<reason>"
python3 ./.trellis/scripts/task.py add-context "$TASK_DIR" check "<path>" "<reason>"
```

真实条目写入后可删除 `_example` 占位行（消费者会自动跳过它）。

就绪门禁：`implement.jsonl` 与 `check.jsonl` 都必须至少包含一条真实条目，`task.py start` 才允许执行。

#### 1.4 激活任务 `[required · once]`

产物评审通过后，把任务状态翻转为 `in_progress`：

```bash
python3 ./.trellis/scripts/task.py start <task-dir>
```

轻量任务 `prd.md` 即可；复杂任务必须在 start 前具备并评审 `prd.md`、`design.md`、`implement.md`；子代理调度平台上 `implement.jsonl` 与 `check.jsonl` 都必须有真实条目。

命令成功后面包屑自动切到 `[workflow-state:in_progress]`。

若 `task.py start` 报会话身份错误，按提示设置会话身份后重试。

#### 1.5 完成标准

| 条件 | 是否必须 |
|------|:---:|
| `prd.md` 存在 | ✅ |
| 复杂任务：`design.md` 存在（含口径与局限声明） | ✅ |
| 复杂任务：`implement.md` 存在（含 2.2 / 2.4 的判定标准） | ✅ |
| `implement.jsonl` 与 `check.jsonl` 各有至少一条真实条目 | ✅ |
| 用户确认可以进入执行 | ✅ |
| 已运行 `task.py start`（status = in_progress） | ✅ |
| `research/` 有产物（复杂任务） | 推荐 |

---

## Phase 2: Execute

目标：把经过评审的规划产物变成**可复核的数据与可信的结论**。

顺序不可调换：先有可信数据（2.1+2.2），才允许分析（2.3）；先完成结论验证（2.4），
才允许对外发布（2.5）与进入收尾。

#### 2.1 数据采集与整理 `[required · repeatable]`

派发执行子代理：

- **Agent 类型**：`trellis-implement`
- **任务描述**：按 `{TASK_DIR}/design.md` / `implement.md` 采集与整理数据，落到 `data/<行政区>/`；整理记录写入 `{TASK_DIR}/validation/collection-log.md`
- **派发提示词守卫**：提示词必须以 `Active task: <task path>` 开头，并声明「你已经是 `trellis-implement` 子代理，直接执行，不要再派发 implement/check 子代理」

采集与整理的硬性要求：

- 只采集 `design.md` 声明的字段；额外字段要么删掉，要么补进 `design.md` 再采集
- 每条数据必须能追溯到来源（URL / 文件 / 采集时间 / 采集人）
- 不确定的值一律留空并标注 `待核实`，**不要猜、不要用邻近值填充**
- 不同来源的同一指标口径不一致时，分开存放并标注口径，不要直接合并
- 数据文件统一放在 `data/<行政区>/<主题>/`，命名与格式约定见 `.trellis/spec/data/`

平台 hook 会自动完成：读取 `implement.jsonl` 并注入其引用的规范/检索文件；注入 `prd.md`、`design.md`（如有）、`implement.md`（如有）。

#### 2.2 数据正确性校验 `[required · repeatable]`

派发校验子代理：

- **Agent 类型**：`trellis-check`
- **任务描述**：对 2.1 新增/修改的数据执行数据正确性校验，产出 `{TASK_DIR}/validation/data-validation.md`，并直接修复可机械修复的问题
- **派发提示词守卫**：提示词必须以 `Active task: <task path>` 开头，并声明「你已经是 `trellis-check` 子代理，直接校验与修复，不要再派发同类子代理」

**校验清单以 `.trellis/spec/quality/` 为准**，至少覆盖：

| 维度 | 检查内容 | 判定 |
|------|----------|------|
| 完整性 | 必填字段是否缺失、行数是否符合预期 | 缺必填字段即不通过 |
| 唯一性 | 主键/自然键是否重复（如同小区重复记录） | 重复未标注来源即不通过 |
| 值域 | 数值范围、枚举取值是否合法（如单价为负、学段取值越界） | 非法值即不通过 |
| 一致性 | 同一实体在不同文件/字段间是否自相矛盾（如面积与户型不匹配） | 未解释的矛盾即不通过 |
| 时效性 | 数据时点是否在声明的有效期内（政策/划片尤其严格） | 过期未标注即不通过 |
| 可追溯性 | 每条记录能否定位到来源与采集时间 | 无法追溯即不通过 |
| 口径一致性 | 是否与 `design.md` 定义的口径一致 | 不一致即不通过 |

**校验结果必须落盘**，格式见 `.trellis/spec/quality/`：逐项写「检查项 / 方法 / 结果 / 样本证据 / 处置」。

**门禁**：存在未处置的不通过项时，**必须回到 2.1**，不得开始 2.3。降级使用（带着已知缺陷继续）必须由用户在 `validation/data-validation.md` 中显式确认，并写进最终结论的局限声明。

#### 2.3 分析与结论产出 `[required · repeatable]`

派发执行子代理：

- **Agent 类型**：`trellis-implement`
- **任务描述**：基于已通过 2.2 校验的数据，按 `design.md` 的口径完成分析，产出 `{TASK_DIR}/analysis/` 下的分析与结论草稿
- **派发提示词守卫**：同 2.1

分析硬性要求：

- 计算过程必须可复现：写清输入文件、筛选条件、聚合口径、公式
- 每条结论后必须紧跟「支撑数据」与「样本量」
- 明确区分**事实描述**（数据说了什么）与**推断判断**（我认为意味着什么）
- 主动写出**反向证据**与**异常个案**，不要只挑支持结论的样本
- 结论草稿中的每个数字都要能指回具体数据文件与字段

#### 2.4 结论可靠性验证 `[required · repeatable]`

派发验证子代理：

- **Agent 类型**：`trellis-check`
- **任务描述**：对 2.3 的分析与结论执行可靠性验证，产出 `{TASK_DIR}/validation/conclusion-review.md`，并修复可修复的问题
- **派发提示词守卫**：同 2.2

**验证清单以 `.trellis/spec/analysis/` 为准**，至少覆盖：

| 维度 | 检查内容 |
|------|----------|
| 计算复核 | 关键指标独立重算一遍，结果是否一致（抽样或全量） |
| 口径一致 | 结论使用的口径是否与 `design.md` 一致，是否中途偷换口径 |
| 数据链路 | 每个数字能否回溯到已通过 2.2 校验的数据文件与字段 |
| 样本代表性 | 样本量是否足够、是否只覆盖少数小区/学校、是否有时段偏差 |
| 对比基准 | 涨幅/溢价类结论是否用了合适基准（同区域、同房龄、同时点） |
| 因果警惕 | 是否把相关性直接说成因果（如「因为对口某校所以贵」） |
| 反向证据 | 是否存在与结论冲突的数据，是否被忽略 |
| 稳健性 | 换一个合理口径/样本重算，结论方向是否仍然成立 |
| 局限声明 | 不确定性、数据缺口、政策变动风险是否显式写出 |

**验证结果必须落盘**到 `validation/conclusion-review.md`，逐项写「检查项 / 方法 / 结果 / 证据 / 处置」。

**门禁**：核心结论未通过（计算不一致、数据链路断裂、样本明显不足、口径偷换）时，**必须回到 2.3 修正**，修正后重新执行 2.4。带着已知重大不确定性输出结论，必须在结论中显著标注。

#### 2.5 结论网页化与发布 `[on demand]`

把 2.4 已验证的结论转成可直接分享的静态页面（移动端可读，可发布到 GitHub Pages）。

**前置条件：2.4 已通过。** 未过 2.4 不得生成对外页面 —— 页面属于「对外输出的结论」，
受本文件第 7 条硬原则（结论必须可证伪）约束。

- **单一事实来源**：页面必须由结论正文（`analysis/<课题>/分析报告.md`）**程序生成**，
  **不得手写 HTML**。改结论只改 Markdown，然后重跑生成脚本。
  ⇒ 目的是从根本上杜绝「网页上的数字与已验证的结论不一致」。
- **产物位置**：
  - 课题页 `analysis/<课题>/index.html`
  - 站点入口为仓库根 `index.html`（自动汇总 `analysis/*/index.html`）
  - `.nojekyll` 必须存在（关闭 Jekyll，否则 `_` 开头的目录不会被发布）

**硬性要求**：

1. **零外部依赖**：CSS 内联，不引任何 CDN —— 发布环境不可控，页面必须离线可读
2. **移动端可用**：必须设 `viewport`；宽表用横向滚动容器包裹，
   **不得让整页产生横向溢出**（首列吸附、表体自滑）
3. **数字同源**：页面里的每个数字都来自已通过 2.4 的结论正文，不得另行计算
4. **生成幂等**：连跑两次输出必须逐字节一致（锚点稳定，旧链接不失效）

**派发**：生成用 `trellis-implement`；页面自检与移动端实测用 `trellis-check`
（结果落盘 `validation/page-check.md`）。

**验证方式**：

- 自检生成物：无未转换的 Markdown 残留（裸 `**`、未转表格行）、无外部加载资源
- 生成幂等：连跑两次比对哈希
- **用真实移动视口（如 390px）实测 `document.scrollWidth == clientWidth`**。
  **不得只用桌面视口或目测截图判断** —— 截图工具可能把布局宽度钳到最小值，
  制造「页面被撑宽」的假象（本项目踩过：Chrome headless 最小窗口宽 500px，
  截 390px 宽的图看起来右侧全被截断，实测页面并无溢出）

**发布**：GitHub Pages，Source 设为 `Deploy from a branch → main → / (root)`。

#### 2.6 回滚 `[on demand]`

- 2.2 / 2.4 暴露 `prd.md` 缺陷 → 回到 Phase 1 修订 `prd.md`，再重做对应步骤
- 采集方向错误 → 丢弃/隔离该批数据（移到 `data/<行政区>/_废弃/` 并注明原因），重做 2.1
- 结论不成立但流程无误 → 回到 Phase 1 修订问题定义，不要硬凑结论
- 需要更多资料 → 同 Phase 1.2，检索结果写入 `research/`
- 2.5 生成页面后结论被修订 → 重跑生成脚本，**页面不得手工改回去**

---

## Phase 3: Finish

目标：确认数据与结论质量、沉淀经验、记录本次工作。

#### 3.2 复盘 `[on demand]`

若本任务出现反复调试（同一问题被多次修正），加载 `trellis-break-loop` skill：

- 归类根因（数据源问题 / 口径理解错误 / 计算方法错误 / 流程缺失）
- 说明此前修复为何失败
- 提出防错措施，并写入 `.trellis/spec/`

#### 3.3 规范更新 `[required · once]`

加载 `trellis-update-spec` skill，审查本任务是否产生了值得记录的新认知：

- 新发现的数据来源、字段含义、官方口径
- 踩过的坑（口径陷阱、过期政策、同名不同校等）
- 新的校验手段或判定标准

据此更新 `.trellis/spec/`。即使结论是「无需更新」，也要走完判断过程。

#### 3.4 提交变更 `[required · once]`

**规范同步前置**：起草提交之前先问自己：本任务是否修复了某类错误、或发现了不明显但重要的知识，应该写进 `.trellis/spec/`，以免将来（人或 AI）重蹈覆辙？如果是，先回 3.3 —— 规范改动应与本任务的提交同批落地。

AI 主导本任务变更的批量提交，使 `/finish-work` 随后能干净运行。目标顺序：先产出工作提交，再做记账（归档 + 日志）提交，两者不交错。

**步骤**：

1. **查看脏状态**：

   ```bash
   git status --porcelain
   ```

   记录所有脏路径。若工作区干净，跳到 3.5。

2. **学习提交风格**：

   ```bash
   git log --oneline -5
   ```

   注意前缀约定（`feat:` / `fix:` / `chore:` / `docs:` …）、语言（中文/英文）与长度风格。

3. **把脏文件分成两组**：

   - **本会话由 AI 编辑** —— 你这次通过编辑/写入/命令工具改动的文件，你知道改了什么、为什么
   - **无法识别** —— 本会话你没碰过的脏文件（可能是用户手动改动、上一次会话的遗留、或无关工作）。**不要**擅自纳入

4. **拟定提交计划**：把 AI 编辑的文件按逻辑单元分组（一个连贯变更一个提交，而不是一个文件一个提交）。每条包含：`<提交信息>` + 文件列表。无法识别的文件单独列在末尾。

5. **一次性呈现计划，请用户一次性确认**：

   ```
   Proposed commits (in order):
     1. <message>
        - <file>
        - <file>

   Unrecognized dirty files (NOT in any commit — confirm include/exclude):
     - <file>

   Reply 'ok' / '行' to execute. Reply with edits, or '我自己来' / 'manual' to abort.
   ```

6. **确认后执行**：按顺序对每批运行 `git add <files>` + `git commit -m "<msg>"`。不要 amend，不要 push。

7. **被拒绝时**（用户回复「不行」/「我自己来」/「manual」/ 对分组提出异议）：停止。不要尝试第二版计划。用户自行提交；用户确认后直接跳到 3.5。

**规则**：

- 全程禁止 `git commit --amend` —— 三段式：工作提交 → 归档提交 → 日志提交
- 本步骤绝不 push 到远端
- 用户只想改措辞但接受分组时，改一次措辞再确认；若拒绝分组，退出到手动模式

#### 3.5 收尾提醒

以上完成后，提醒用户可以运行 `/finish-work` 收尾（归档任务、记录本次会话）。

---

## 定制本工作流（Customizing Trellis）

本节面向要修改工作流本身的人。所有定制都通过编辑本文件完成；脚本只做解析。

### 修改某一步的含义

编辑 Phase 1 / 2 / 3 中对应步骤的正文。关键不变量：

- 无当前任务时必须先分类，并在创建 Trellis 任务前取得用户同意
- 规划必须区分「轻量 PRD-only」与「复杂任务需 prd + design + implement」
- **Phase 2 必须保持 `2.1 采集 → 2.2 数据校验 → 2.3 分析 → 2.4 结论验证 → 2.5 结论网页化` 的顺序与门禁**：数据校验未过不得分析，结论验证未过不得对外发布、不得收尾
- **`2.5` 生成的页面必须由结论正文程序生成，不得手写**：手写会让页面与已验证的结论脱钩，绕过 2.4 的门禁
- 每条必需执行路径上，Phase 3.4 的提交提醒必须可达，且先于 `/trellis:finish-work`

所有 tag 块位于上方 `## Phase Index` 各阶段摘要之后：

| 范围 | 对应 tag |
|---|---|
| 无当前任务（Phase 1 之前） | `[workflow-state:no_task]` |
| 当前任务记录不可读 | `[workflow-state:task_error]` |
| Phase 1 全程 | `[workflow-state:planning]` |
| 内联模式 Phase 1 | `[workflow-state:planning-inline]` |
| Phase 2 + Phase 3.2–3.4 | `[workflow-state:in_progress]` |
| 内联模式 Phase 2 + Phase 3.2–3.4 | `[workflow-state:in_progress-inline]` |
| Phase 3.5 之后（已归档） | `[workflow-state:completed]`（当前 DEAD） |

### 修改每轮提示文案

直接编辑对应 `[workflow-state:STATUS]` 块的正文。改完后重启 AI 会话即可生效，无需改脚本。

### 新增自定义状态

```text
[workflow-state:my-status]
你的每轮提示文案
[/workflow-state:my-status]
```

约束：

- STATUS 字符集：`[A-Za-z0-9_-]+`
- 必须有生命周期钩子把 `task.json.status` 写成你的自定义值，否则该 tag 永远不会被读取
- 生命周期钩子位于 `task.json.hooks.after_*`，支持 `after_create / after_start / after_finish / after_archive`

### 完整契约

- `.codebuddy/hooks/inject-workflow-state.py` — 实际解析器（只读 workflow.md，无内置兜底文案）
- `.codebuddy/hooks/session-start.py` — 按字面匹配 `## Phase Index` 与 `## Phase 1: Plan`
- `.trellis/scripts/common/workflow_phase.py` — 步骤抽取与平台块过滤
