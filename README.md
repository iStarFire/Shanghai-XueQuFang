# 上海学区房数据分析

围绕**上海学区房**的数据采集、整理、校验与分析项目。

目标是回答这类问题：

- 对口某所小学/初中，是否真的让周边小区房价更高？高多少？
- 同类学区之间如何横向对比？
- 新建学校、地铁、旧改等规划，在多大程度上已被市场定价？
- 政策调整（划片变化、民办政策）对价格与选择的影响。

**这不是一个编码项目。** 项目里没有应用代码、没有构建、没有单测。
这里唯一的产出物是**可信的数据**与**经得起验证的结论**。

---

## 分析课题

每个课题对应 `analysis/` 下一个中文子目录（一个课题一个目录），结论有网页版（GitHub Pages）与本地 `分析报告.md` 双形态。

- [徐汇区公办初中名额分配到校分析](https://istarfire.github.io/Shanghai-XueQuFang/徐汇区公办初中名额分配到校分析/)
  （本地：[分析报告.md](analysis/徐汇区公办初中名额分配到校分析/分析报告.md) · [index.html](analysis/徐汇区公办初中名额分配到校分析/index.html)）

> 新增课题后，在 `analysis/` 下建目录并跑 `工具/build_html.py`，本列表与站点入口页会自动更新对应卡片。

---

## 目录结构

```
Shanghai-XueQuFang/
├── README.md              # 本文件
├── AGENTS.md              # 面向 AI 助手的项目须知
├── .gitignore
├── .nojekyll              # 关闭 GitHub Pages 的 Jekyll 处理
├── index.html             # 站点入口页（GitHub Pages），自动汇总 analysis/ 下的课题
├── data/                  # 唯一的项目数据目录（按行政区隔离）
│   ├── README.md          # 数据目录规范
│   ├── 徐汇区/
│   │   ├── 学校/          # 学校名录、办学性质、对口划片、招生计划
│   │   ├── 小区/          # 小区名录、建成年代、户型、价格与租金
│   │   ├── 规划/          # 官方规划文件与摘要（学校建设/交通/旧改）
│   │   └── 来源.md        # 数据来源登记表（必须维护）
│   ├── 普陀区/
│   └── _全市/             # 跨行政区的市级文件
├── analysis/              # 分析产物（一个课题一个中文子目录）
│   └── 徐汇区公办初中名额分配到校分析/
│       ├── index.html     # 结论网页版（由 分析报告.md 生成，勿手改）
│       ├── 宽表-*.csv      # 核心交付物
│       ├── 分析报告.md     # 结论的**唯一事实来源**，改这里再重跑生成
│       ├── 分析方法-*.md   # 可复用方法
│       ├── 剔除清单.md     # 被排除的对象与理由
│       └── 工具/           # 可复跑脚本（构建 / 独立复算 / 生成网页）
└── .trellis/              # 工作流、项目规范、任务记录（不含业务数据）
    ├── workflow.md        # 数据分析工作流（核心）
    ├── spec/              # 项目规范
    │   ├── data/          # 数据来源、目录、命名、字段与口径
    │   ├── quality/       # 数据正确性校验规范
    │   ├── analysis/      # 分析方法与结论可靠性验证规范
    │   └── guides/        # 跨领域思考指南
    ├── tasks/             # 进行中 / 已归档的任务
    ├── workspace/         # 会话日志
    └── scripts/           # Trellis 脚本
```

---

## 结论网页（GitHub Pages）

分析结论有网页版，移动端可读，发布后可直接分享给他人：

```
https://istarfire.github.io/Shanghai-XueQuFang/
```

- 站点由 `analysis/<课题>/工具/build_html.py` 生成：**只读 `分析报告.md`**，
  转成响应式 HTML（CSS 内联、零外部依赖、含深色模式与表格横向滚动）。
  ⇒ **改结论只改 `分析报告.md`，然后重跑脚本**，不要手改 `index.html`。
- 根 `index.html` 是入口页，自动扫描 `analysis/*/index.html` 生成课题卡片；
  新增课题后重跑脚本即可自动出现。
- `.nojekyll` 必须保留：`data/_全市/` 以 `_` 开头，Jekyll 会忽略它。
- 首次发布需在仓库 Settings → Pages 里把 Source 设为
  **Deploy from a branch → `main` → `/ (root)`**。

---

## 数据组织约定（摘要）

完整约定见 [`data/README.md`](data/README.md) 与
[`.trellis/spec/data/directory-structure.md`](.trellis/spec/data/directory-structure.md)。

1. **所有业务数据只能放 `data/` 下**，不放任何平行数据目录
2. **第一层是行政区**（`徐汇区`、`普陀区`…），写官方简称，不写拼音/缩写
3. **第二层是主题**：`学校`、`小区`、`规划`
4. **每个主题目录必须有 `来源.md`**，登记每个数据文件的来源、发布主体、发布时间、
   采集时间、采集人、口径说明、已知缺陷
5. **文件名带时点**，例如 `小学名录-公办-2026.csv`、`小区挂牌价-2026-09.csv`
6. **结构化数据用 CSV**（UTF-8 含 BOM，首行英文字段名），政策摘要用 Markdown
7. **失效数据不删除**，移到 `_废弃/` 并注明原因

---

## 工作流（Trellis）

本项目使用 [Trellis](https://docs.trytrellis.app/) 作为工作流框架，
但工作流内容已被**改写为数据分析场景**，移除了编码相关步骤。

### 三个阶段

| 阶段 | 做什么 | 产出 |
|------|--------|------|
| **Phase 1: Plan** | 分类请求、取得建任务同意、探索问题与数据范围、检索资料 | `prd.md`、`design.md`、`implement.md`、`research/` |
| **Phase 2: Execute** | 采集/整理数据 → **数据正确性校验** → 分析 → **结论可靠性验证** | `data/**`、`analysis/`、`validation/` |
| **Phase 3: Finish** | 复盘、更新规范、提交、收尾 | 规范更新、提交记录 |

### 两条硬门禁

```
2.1 数据采集与整理
        ↓
2.2 数据正确性校验   ← 未通过不得进入 2.3
        ↓
2.3 分析与结论产出
        ↓
2.4 结论可靠性验证   ← 未通过不得进入 Phase 3
        ↓
Phase 3 收尾
```

### 2.2 数据正确性校验（七个维度）

完整性 · 唯一性 · 值域 · 一致性 · 时效性 · 可追溯性 · 口径一致性

判定标准见 [`.trellis/spec/quality/data-validation.md`](.trellis/spec/quality/data-validation.md)。

### 2.4 结论可靠性验证（九个维度）

计算复核 · 口径一致 · 数据链路 · 样本代表性 · 对比基准 ·
因果警惕 · 反向证据 · 稳健性 · 局限声明

判定标准见 [`.trellis/spec/analysis/conclusion-verification.md`](.trellis/spec/analysis/conclusion-verification.md)。

### 子代理角色

| 平台标识 | 本项目角色 | 职责 |
|----------|------------|------|
| `trellis-implement` | 执行代理 | 数据采集、整理、分析产出 |
| `trellis-check` | 校验代理 | 数据正确性校验、结论可靠性验证 |
| `trellis-research` | 检索代理 | 官方来源、政策口径、资料检索 |

> `trellis-implement` / `trellis-check` 是 Trellis 的**平台标识**，
> 在本项目中的含义是「执行/校验」，与写代码无关。

### 术语对照

| Trellis 原生术语 | 本项目含义 |
|------------------|------------|
| implement（实现） | 采集、整理、分析 |
| check（代码检查） | 数据校验、结论验证 |
| lint / typecheck | **不适用** |
| spec（编码规范） | 数据规范、校验规范、分析规范 |
| bug | 数据错误 / 口径错误 / 结论不成立 |

---

## 如何使用

### 1. 初始化开发者身份（首次）

```bash
python3 ./.trellis/scripts/init_developer.py <your-name>
```

### 2. 提一个分析需求

直接用自然语言描述你想回答的问题。AI 会：

1. 判断是否需要建立一个 Trellis 任务，并征求你同意
2. 进入规划，与你逐条确认问题边界、数据范围、校验与验证标准
3. 评审通过后开始执行：采集 → 校验 → 分析 → 验证
4. 收尾时更新规范、提交变更

### 3. 常用命令

```bash
# 任务生命周期
python3 ./.trellis/scripts/task.py create "<标题>" --slug <name>
python3 ./.trellis/scripts/task.py start <name>
python3 ./.trellis/scripts/task.py list
python3 ./.trellis/scripts/task.py archive <name>

# 查看工作流与步骤指引
python3 ./.trellis/scripts/get_context.py --mode phase
python3 ./.trellis/scripts/get_context.py --mode phase --step 2.2
python3 ./.trellis/scripts/get_context.py --mode packages

# 会话结束收尾
#   /trellis:finish-work
```

---

## 数据诚信要求

本项目的价值完全取决于数据可信度。以下要求是硬性的：

1. **未经 2.2 校验的数据，不得用于任何结论**
2. **每个数字必须能走回原始来源**：结论 → 指标 → 口径 → 数据文件 → 字段 → `来源.md` → 原始来源
3. **不确定的值留空并标注「待核实」**，禁止猜测填充
4. **口径不同的来源分开存放**，不得合并成「看起来统一」的数据
5. **必须主动寻找反向证据**，不得只挑支持结论的样本
6. **「未发现问题」≠「数据无误」**，「找不到反证」≠「结论成立」
7. **带着已知缺陷继续**必须由使用者显式确认，并写入结论的局限声明

---

## 常见陷阱（摘要）

详见 [`.trellis/spec/quality/data-validation.md`](.trellis/spec/quality/data-validation.md)。

- **挂牌价 ≠ 成交价**：混用会系统性高估溢价
- **建筑面积 ≠ 使用面积**：单价口径不同可差 20%+
- **同名不同校**：不同区有同名「实验小学」，跨区合并统计是致命的
- **政策时点错位**：用上一学年的划片分析当前房价，结论无效
- **居委划片无法直接落到小区**：需要居委-小区映射表
- **商住混入**：商住/公寓不能入学，混入会拉低学区溢价估算
- **规划 ≠ 落地**：征求意见稿不得当既成事实

---

## 许可

本项目为个人研究用途。
