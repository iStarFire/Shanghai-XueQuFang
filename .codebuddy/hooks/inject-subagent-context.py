#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多平台子代理上下文注入 Hook（数据分析项目定制版）

在子代理被派发时注入任务相关上下文。

角色映射（本项目为数据分析项目，不存在写代码/编译/单测环节）：
- trellis-implement → 数据采集 / 整理 / 分析执行
- trellis-check     → 数据正确性校验 / 结论可靠性验证
- trellis-research  → 资料与来源检索

核心设计：
- Hook 负责注入全部上下文，子代理带着完整信息自主工作
- 每个代理有专属的 jsonl 文件声明其上下文
- 不依赖 resume，不做分段，行为由文件而非提示词决定

触发时机：PreToolUse（Task 工具调用之前）

上下文来源：Trellis 当前任务解析器指向的任务目录
- implement.jsonl - 执行代理专属上下文
- check.jsonl     - 校验代理专属上下文
- prd.md          - 要回答的问题与数据范围
- design.md       - 分析设计（口径、指标定义、对比基准、局限）
- implement.md    - 执行计划（含 2.2 / 2.4 判定标准）
"""
from __future__ import annotations

# IMPORTANT: Suppress all warnings FIRST
import warnings
warnings.filterwarnings("ignore")

import json
import os
import sys
from pathlib import Path
from typing import Any

# Hook hosts send UTF-8 JSON regardless of the process locale.
_stdin_reconfigure = getattr(sys.stdin, "reconfigure", None)
if callable(_stdin_reconfigure):
    try:
        _stdin_reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass

# IMPORTANT: Force stdout to use UTF-8 on Windows
# This fixes UnicodeEncodeError when outputting non-ASCII characters
if sys.platform.startswith("win"):
    import io as _io
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    elif hasattr(sys.stdout, "detach"):
        sys.stdout = _io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")  # type: ignore[union-attr]


# =============================================================================
# Path Constants (change here to rename directories)
# =============================================================================

DIR_WORKFLOW = ".trellis"
DIR_SPEC = "spec"
FILE_TASK_JSON = "task.json"

# =============================================================================
# Subagent Constants (change here to rename subagent types)
# =============================================================================

AGENT_IMPLEMENT = "trellis-implement"
AGENT_CHECK = "trellis-check"
AGENT_RESEARCH = "trellis-research"

# Agents that require a task directory
AGENTS_REQUIRE_TASK = (AGENT_IMPLEMENT, AGENT_CHECK)
# All supported agents
AGENTS_ALL = (AGENT_IMPLEMENT, AGENT_CHECK, AGENT_RESEARCH)


def find_repo_root(start_path: str) -> str | None:
    """
    Find git repo root from start_path upwards

    Returns:
        Repo root path, or None if not found
    """
    current = Path(start_path).resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


def _detect_platform(input_data: dict) -> str | None:
    if _hook_event_name(input_data) == "SubagentStart":
        return "codex"
    if isinstance(input_data.get("cursor_version"), str):
        return "cursor"
    # CLAUDE_PROJECT_DIR is a compatibility alias that several hosts set
    # alongside their own variable — CodeBuddy, ZCode and Trae all do. It must
    # therefore be checked LAST, or every one of them is detected as claude and
    # the context key becomes `claude_<their-session-id>`. That key does not
    # match the session file `task.py start` wrote under the host's real name,
    # so the sub-agent starts with no task context while the pointer exists on
    # disk. Same fix as inject-workflow-state.py and session-start.py; this
    # third copy was missed when those two were corrected.
    env_map = {
        "ZCODE_PROJECT_DIR": "zcode",
        "CURSOR_PROJECT_DIR": "cursor",
        "CODEBUDDY_PROJECT_DIR": "codebuddy",
        "FACTORY_PROJECT_DIR": "droid",
        "GEMINI_PROJECT_DIR": "gemini",
        "QODER_PROJECT_DIR": "qoder",
        "KIRO_PROJECT_DIR": "kiro",
        "COPILOT_PROJECT_DIR": "copilot",
        "TRAE_PROJECT_DIR": "trae",
        # Last: the shared alias, only meaningful once no vendor key matched.
        "CLAUDE_PROJECT_DIR": "claude",
    }
    for env_name, platform in env_map.items():
        if os.environ.get(env_name):
            return platform
    script_parts = set(Path(sys.argv[0]).parts)
    if ".claude" in script_parts:
        return "claude"
    if ".cursor" in script_parts:
        return "cursor"
    if ".gemini" in script_parts:
        return "gemini"
    if ".qoder" in script_parts:
        return "qoder"
    if ".codebuddy" in script_parts:
        return "codebuddy"
    if ".factory" in script_parts:
        return "droid"
    if ".kiro" in script_parts:
        return "kiro"
    if ".zcode" in script_parts:
        return "zcode"
    return None


def get_current_task(
    repo_root: str,
    input_data: dict,
    *,
    platform: str | None = None,
    allow_single_session_fallback: bool = True,
    allow_environment_context: bool = True,
    require_existing: bool = False,
) -> str | None:
    """Resolve current task directory through the unified active task resolver."""
    scripts_dir = Path(repo_root) / DIR_WORKFLOW / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.active_task import resolve_active_task  # type: ignore[import-not-found]
    except Exception:
        return None

    active = resolve_active_task(
        Path(repo_root),
        input_data,
        platform=platform or _detect_platform(input_data),
        allow_single_session_fallback=allow_single_session_fallback,
        allow_environment_context=allow_environment_context,
    )
    if require_existing and active.stale:
        return None
    return active.task_path


# =============================================================================
# Context Injection Limits (issue #441)
#
# Notice text and behavior mirrored byte-for-byte in the Pi TS extension
# (templates/pi/extensions/trellis/index.ts.txt). Changing wording here
# requires changing it there too.
# =============================================================================

DEFAULT_MAX_FILE_BYTES = 32768
DEFAULT_MAX_ARTIFACT_BYTES = 65536
DEFAULT_MAX_TOTAL_BYTES = 131072

DEFAULT_LIMITS: dict[str, int] = {
    "max_file_bytes": DEFAULT_MAX_FILE_BYTES,
    "max_artifact_bytes": DEFAULT_MAX_ARTIFACT_BYTES,
    "max_total_bytes": DEFAULT_MAX_TOTAL_BYTES,
}


def _get_limits(repo_root: str) -> dict[str, int]:
    """Load context-injection byte limits from config.yaml, with safe fallback."""
    scripts_dir = Path(repo_root) / DIR_WORKFLOW / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.config import get_context_injection_limits  # type: ignore[import-not-found]

        return get_context_injection_limits(Path(repo_root))
    except Exception:
        return dict(DEFAULT_LIMITS)


def truncate_utf8(data: bytes, cap: int) -> bytes:
    """Truncate ``data`` to at most ``cap`` bytes without splitting a UTF-8
    multi-byte sequence.

    ``cap <= 0`` means "no limit" — returns ``data`` unchanged.
    """
    if cap <= 0 or len(data) <= cap:
        return data

    truncated = data[:cap]
    i = len(truncated)
    # Back off over continuation bytes (10xxxxxx) to find the lead byte.
    while i > 0 and (truncated[i - 1] & 0xC0) == 0x80:
        i -= 1
    if i == 0:
        return b""

    lead = truncated[i - 1]
    if lead & 0x80:
        if (lead & 0xE0) == 0xC0:
            seq_len = 2
        elif (lead & 0xF0) == 0xE0:
            seq_len = 3
        elif (lead & 0xF8) == 0xF0:
            seq_len = 4
        else:
            seq_len = 1
        # Drop the lead byte too if its full sequence didn't fit.
        if (i - 1) + seq_len > len(truncated):
            i -= 1

    return truncated[:i]


class _Budget:
    """Tracks the running total of bytes emitted into the sub-agent context."""

    def __init__(self, max_total_bytes: int) -> None:
        self.max_total_bytes = max_total_bytes
        self.used = 0

    def has_room(self, size: int) -> bool:
        if self.max_total_bytes <= 0:
            return True
        return self.used + size <= self.max_total_bytes

    def add(self, size: int) -> None:
        self.used += size


def _real_path_contained(base_real: str, target_real: str) -> bool:
    """Whether an already-realpath'd target sits under an already-realpath'd base.

    ValueError on Windows when the two sit on different drives; that is
    outside the base by definition, so it fails closed.
    """
    try:
        return os.path.commonpath([base_real, target_real]) == base_real
    except ValueError:
        return False


def _read_file_bytes(base_path: str, file_path: str) -> bytes | None:
    """Read raw file bytes, return None if file doesn't exist."""
    full_path = os.path.join(base_path, file_path)
    try:
        root_real = os.path.realpath(base_path)
        # `.trellis` may itself be a symlink into a store outside the repo
        # (#567); its real location is a second legitimate containment base.
        workflow_real = os.path.realpath(os.path.join(base_path, ".trellis"))
        full_real = os.path.realpath(full_path)
        if not _real_path_contained(root_real, full_real) and not (
            _real_path_contained(workflow_real, full_real)
        ):
            return None
    except OSError:
        return None
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, "rb") as f:
                return f.read()
        except Exception:
            return None
    return None


def _truncate_notice(path: str, cap: int) -> str:
    return f"\n[Trellis: truncated at {cap} bytes — read {path} for the full content]"


def _is_binary_content(data: bytes) -> bool:
    """Return True when raw bytes should not be decoded into model context."""
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return True
    return False


def _binary_notice(path: str, size: int, reason: str) -> str:
    return (
        f"[Trellis: not inlined (binary file) — "
        f"{path} ({size} bytes): {reason}]"
    )


def _index_notice(path: str, size: int, reason: str) -> str:
    return (
        f"[Trellis: not inlined (total context limit reached) — "
        f"{path} ({size} bytes): {reason}]"
    )


def _budgeted_block(
    budget: _Budget,
    header: str,
    plain_path: str,
    content: str,
    reason: str,
    size_for_index: int,
) -> str:
    """Return an inlined ``=== header ===`` block, or degrade to an index
    notice once the total context budget is exhausted."""
    block = f"=== {header} ===\n{content}"
    block_bytes = len(block.encode("utf-8"))
    if not budget.has_room(block_bytes):
        notice = _index_notice(plain_path, size_for_index, reason)
        budget.add(len(notice.encode("utf-8")))
        return notice
    budget.add(block_bytes)
    return block


def _materialize_file(
    base_path: str,
    file_path: str,
    reason: str,
    limits: dict[str, int],
    budget: _Budget,
) -> str | None:
    """Read a JSONL-referenced file, apply the per-file cap, then budget it."""
    data = _read_file_bytes(base_path, file_path)
    if data is None:
        return None

    size = len(data)
    if _is_binary_content(data):
        notice = _binary_notice(file_path, size, reason)
        budget.add(len(notice.encode("utf-8")))
        return notice

    cap = limits["max_file_bytes"]
    truncated_bytes = truncate_utf8(data, cap)
    content = truncated_bytes.decode("utf-8", errors="replace")
    if len(truncated_bytes) < size:
        content += _truncate_notice(file_path, cap)

    return _budgeted_block(budget, file_path, file_path, content, reason, size)


def _materialize_directory(
    base_path: str,
    dir_path: str,
    reason: str,
    limits: dict[str, int],
    budget: _Budget,
    max_files: int = 20,
) -> list[str]:
    """Read all .md files in a directory, applying the same per-file and
    total caps as a single-file JSONL entry."""
    full_path = os.path.join(base_path, dir_path)
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return []

    blocks: list[str] = []
    try:
        md_files = sorted(
            f
            for f in os.listdir(full_path)
            if f.endswith(".md") and os.path.isfile(os.path.join(full_path, f))
        )
        for filename in md_files[:max_files]:
            relative_path = os.path.join(dir_path, filename)
            block = _materialize_file(base_path, relative_path, reason, limits, budget)
            if block:
                blocks.append(block)
    except Exception:
        pass

    return blocks


def read_jsonl_entries(base_path: str, jsonl_path: str) -> list[dict]:
    """
    Parse all file/directory entries referenced in a jsonl context file.

    Schema:
        {"file": "path/to/file.md", "reason": "..."}
        {"file": "path/to/dir/", "type": "directory", "reason": "..."}
        {"_example": "..."}          # legacy placeholder — skipped (no `file` field)

    Rows without a ``file`` field (e.g. the placeholder line older Trellis
    versions wrote at ``task.py create`` time) are skipped silently. If the
    resulting entry list is empty, a stderr warning is emitted so the operator
    can debug missing context.

    Returns:
        [{"file": path, "type": "file" | "directory", "reason": reason}, ...]
    """
    full_path = os.path.join(base_path, jsonl_path)
    if not os.path.exists(full_path):
        print(
            f"[inject-subagent-context] WARN: {jsonl_path} not found — "
            f"sub-agent will receive only task artifacts",
            file=sys.stderr,
        )
        return []

    entries: list[dict] = []
    saw_real_entry = False
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    file_path = item.get("file") or item.get("path")

                    if not file_path:
                        # Seed / comment row — skip silently
                        continue

                    saw_real_entry = True
                    entries.append(
                        {
                            "file": file_path,
                            "type": item.get("type", "file"),
                            "reason": item.get("reason") or "-",
                        }
                    )
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    if not saw_real_entry:
        print(
            f"[inject-subagent-context] WARN: {jsonl_path} has no curated "
            f"entries (only seed / empty) — sub-agent will receive only "
            f"task artifacts. See workflow.md planning artifact guidance.",
            file=sys.stderr,
        )

    return entries


def _materialize_jsonl_entries(
    base_path: str, jsonl_path: str, limits: dict[str, int], budget: _Budget
) -> list[str]:
    """Materialize every entry in a jsonl context file into context blocks,
    applying per-file and total budget caps."""
    blocks: list[str] = []
    for entry in read_jsonl_entries(base_path, jsonl_path):
        if entry["type"] == "directory":
            blocks.extend(
                _materialize_directory(
                    base_path, entry["file"], entry["reason"], limits, budget
                )
            )
        else:
            block = _materialize_file(
                base_path, entry["file"], entry["reason"], limits, budget
            )
            if block:
                blocks.append(block)
    return blocks


def get_agent_context(
    repo_root: str,
    task_dir: str,
    agent_type: str,
    limits: dict[str, int],
    budget: _Budget,
) -> str:
    """
    Get context from {agent_type}.jsonl for the specified agent.
    Only reads implement.jsonl or check.jsonl (the two JSONL files the task system creates).
    """
    agent_jsonl = f"{task_dir}/{agent_type}.jsonl"
    blocks = _materialize_jsonl_entries(repo_root, agent_jsonl, limits, budget)
    if not blocks:
        # Zero curated context reaches the model silently otherwise — the
        # stderr WARN above never enters any session (#573). Put the fact in
        # the prompt itself so the sub-agent compensates instead of assuming
        # the spec context was complete.
        return (
            f"[Trellis] {agent_jsonl} 没有整理好的条目，因此未注入任何规范/检索上下文。"
            "开工前请自行阅读 .trellis/spec/ 下与本任务相关的规范"
            "（数据规范 spec/data/、数据校验 spec/quality/、分析与结论验证 spec/analysis/），"
            "并把下方任务产物视为唯一已准备的上下文。"
        )
    return "\n\n".join(blocks)


def _materialize_artifact(
    base_path: str,
    file_path: str,
    header_label: str,
    reason: str,
    limits: dict[str, int],
    budget: _Budget,
) -> str | None:
    """Read a task artifact (prd/design/implement.md), apply the per-artifact
    cap, then budget it."""
    data = _read_file_bytes(base_path, file_path)
    if data is None:
        return None

    size = len(data)
    cap = limits["max_artifact_bytes"]
    truncated_bytes = truncate_utf8(data, cap)
    content = truncated_bytes.decode("utf-8", errors="replace")
    if len(truncated_bytes) < size:
        content += _truncate_notice(file_path, cap)

    return _budgeted_block(budget, header_label, file_path, content, reason, size)


def get_implement_context(repo_root: str, task_dir: str) -> str:
    """
    Complete context for Implement Agent

    Read order:
    1. All files in implement.jsonl (spec/research manifests)
    2. prd.md (requirements)
    3. design.md if present (technical design)
    4. implement.md if present (execution plan)
    """
    limits = _get_limits(repo_root)
    budget = _Budget(limits["max_total_bytes"])
    context_parts = []

    # 1. Read implement.jsonl
    base_context = get_agent_context(repo_root, task_dir, "implement", limits, budget)
    if base_context:
        context_parts.append(base_context)

    # 2. Requirements document
    prd_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/prd.md",
        f"{task_dir}/prd.md（要回答的问题与数据范围）",
        "任务需求文档",
        limits,
        budget,
    )
    if prd_block:
        context_parts.append(prd_block)

    # 3. Technical design for complex tasks
    design_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/design.md",
        f"{task_dir}/design.md（分析设计）",
        "分析设计文档（口径、指标定义、对比基准、局限）",
        limits,
        budget,
    )
    if design_block:
        context_parts.append(design_block)

    # 4. Execution plan for complex tasks
    implement_plan_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/implement.md",
        f"{task_dir}/implement.md（执行计划）",
        "执行计划文档（含 2.2 数据校验与 2.4 结论验证的判定标准）",
        limits,
        budget,
    )
    if implement_plan_block:
        context_parts.append(implement_plan_block)

    return "\n\n".join(context_parts)


def get_check_context(repo_root: str, task_dir: str) -> str:
    """
    Context for Check Agent: check.jsonl + task artifacts.
    """
    limits = _get_limits(repo_root)
    budget = _Budget(limits["max_total_bytes"])
    context_parts = []

    base_context = get_agent_context(repo_root, task_dir, "check", limits, budget)
    if base_context:
        context_parts.append(base_context)

    prd_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/prd.md",
        f"{task_dir}/prd.md（要回答的问题与数据范围）",
        "任务需求文档",
        limits,
        budget,
    )
    if prd_block:
        context_parts.append(prd_block)

    design_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/design.md",
        f"{task_dir}/design.md（分析设计）",
        "分析设计文档（口径、指标定义、对比基准、局限）",
        limits,
        budget,
    )
    if design_block:
        context_parts.append(design_block)

    implement_plan_block = _materialize_artifact(
        repo_root,
        f"{task_dir}/implement.md",
        f"{task_dir}/implement.md（执行计划）",
        "执行计划文档（含 2.2 数据校验与 2.4 结论验证的判定标准）",
        limits,
        budget,
    )
    if implement_plan_block:
        context_parts.append(implement_plan_block)

    return "\n\n".join(context_parts)


def get_finish_context(repo_root: str, task_dir: str) -> str:
    """
    Context for Finish phase: reuses check.jsonl + prd.md
    (Finish is a final check, same context source.)
    """
    return get_check_context(repo_root, task_dir)



def build_implement_prompt(original_prompt: str, context: str) -> str:
    """构建执行代理（数据采集/整理/分析）的完整提示词"""
    return f"""<!-- trellis-hook-injected -->
# 执行代理任务（数据采集 / 整理 / 分析）

你是多代理流程中的执行代理（平台标识 `trellis-implement`）。
本项目是上海学区房数据分析项目：不存在写代码/编译/单测环节，
你负责工作流 2.1 数据采集与整理、2.3 分析与结论产出。

## 你的上下文

你需要的全部信息已准备好：

{context}

---

## 你的任务

{original_prompt}

---

## 工作流

1. **理解规范** - 上方已注入规范，先读懂它们（重点：`.trellis/spec/data/`、`spec/analysis/method-guidelines.md`）
2. **理解任务产物** - 读 `prd.md`、`design.md`（如有）、`implement.md`（如有）
3. **执行** - 按规范与任务产物采集/整理数据，或产出分析与结论草稿
4. **自检** - 落盘前按 `spec/data/` 与 `spec/analysis/` 自检

## 重要约束

- 不要执行 git commit / push / merge
- 只采集 `design.md` 声明的字段；不确定的值留空并标注「待核实」，禁止猜测填充
- 每条数据必须可追溯来源，并登记进对应目录的 `来源.md`
- 执行 2.3 之前必须确认 2.2 数据校验已通过（读 `validation/data-validation.md` 门禁结论）
- 遵循上方注入的全部规范
- 完成后汇报产出/修改的文件清单、数据缺口与待确认问题"""


def build_check_prompt(original_prompt: str, context: str) -> str:
    """构建校验代理（数据正确性 + 结论可靠性）的完整提示词"""
    return f"""<!-- trellis-hook-injected -->
# 校验代理任务（数据正确性校验 / 结论可靠性验证）

你是多代理流程中的校验代理（平台标识 `trellis-check`）。
本项目是上海学区房数据分析项目：不存在写代码/编译/单测环节。
你负责工作流 2.2 数据正确性校验、2.4 结论可靠性验证。

## 你的上下文

你需要的全部判定依据：

{context}

---

## 你的任务

{original_prompt}

---

## 工作流

1. **圈定校验对象** - 用 `git status --porcelain` / `git diff --name-only` 找出本次变更
   的数据文件（`data/**`）或分析产物（`{{TASK_DIR}}/analysis/**`）
2. **逐维度校验/验证** - 对照上方规范逐项执行，每一项都要留下样本证据
   （文件 + 行号 + 具体值），不接受「整体看起来正常」
3. **证明方法有效** - 用「语义上明显错误」的样例验证你的校验方法本身能失败；
   捕获不到的维度必须说明并视为方法不合格
4. **自修复** - 机械问题（格式、命名不统一、枚举越界）直接改，改完必须重新校验；
   判断类问题（口径变更、结论表述、样本取舍）记录证据交主会话，不要静默改写
5. **给出门禁结论** - 明确写「通过」或「不通过（需回到 2.1 / 2.3）」

## 重要约束

- **自己动手修复**，不要只报告问题
- 必须完整执行 `spec/quality/data-validation.md`（七个维度）与
  `spec/analysis/conclusion-verification.md`（九个维度）的清单
- 独立重算，不要复用执行代理的中间结果当证据（循环验证）
- 「未发现问题」≠「数据无误」；前者是观测，后者需要证据
- 门禁不通过时必须如实说「不通过」，不要为推进流程放水"""


def build_finish_prompt(original_prompt: str, context: str) -> str:
    """构建收尾阶段最终校验的完整提示词"""
    return f"""<!-- trellis-hook-injected -->
# 收尾校验任务

你正在执行本任务进入 Phase 3 之前的最终校验。

## 你的上下文

收尾校验清单与要求：

{context}

---

## 你的任务

{original_prompt}

---

## 工作流

1. **回顾变更** - 运行 `git diff --name-only` 查看全部变更文件
2. **核对任务产物** - 对照 `prd.md` 的验收标准，以及 `design.md` / `implement.md`（如有）的约束
3. **规范同步判断** - 判断本次是否产生了应写入 `.trellis/spec/` 的新知识
   - 新数据来源、新字段/口径、新的校验或验证手段 → 读目标规范文件后更新它，
     必要时同步更新同目录 `index.md`
   - 只是常规数据补充、无新认知 → 跳过本步
4. **门禁复核** - 确认 `validation/data-validation.md` 与
   `validation/conclusion-review.md` 都给出了明确的通过结论（或已记录用户降级确认）
5. **确认可收尾** - 确保数据与结论满足 prd.md 的验收标准

## 重要约束

- 发现规范缺口时可以更新规范文件（参照 update-spec skill）
- 编辑规范前**必须先读**目标文件，避免重复已有内容
- 琐碎变更（错别字、格式）不要更新规范
- 发现严重的数据正确性缺陷时，明确指出并回到 2.1 / 2.2，不要直接收尾
- 逐条核对 prd.md 的验收标准是否满足
- `design.md` / `implement.md` 存在时，核对其中约束是否落实"""



def get_research_context(repo_root: str, task_dir: str | None) -> str:
    """
    Context for Research Agent — project structure overview for spec directories.

    `task_dir` kept for signature parity with get_implement_context / get_check_context
    so the dispatcher can call them uniformly.
    """
    _ = task_dir
    context_parts = []

    # 1. Project structure overview (dynamically discover spec directories)
    spec_path = f"{DIR_WORKFLOW}/{DIR_SPEC}"
    spec_root = Path(repo_root) / DIR_WORKFLOW / DIR_SPEC

    # Build spec tree dynamically
    tree_lines = [f"{spec_path}/"]
    if spec_root.is_dir():
        pkg_dirs = sorted(d for d in spec_root.iterdir() if d.is_dir())
        for i, pkg_dir in enumerate(pkg_dirs):
            is_last = i == len(pkg_dirs) - 1
            prefix = "└── " if is_last else "├── "
            layers = sorted(d.name for d in pkg_dir.iterdir() if d.is_dir())
            layer_info = f" ({', '.join(layers)})" if layers else ""
            tree_lines.append(f"{prefix}{pkg_dir.name}/{layer_info}")

    spec_tree = "\n".join(tree_lines)

    project_structure = f"""## 项目规范目录结构

```
{spec_tree}
```

获取结构化分层信息：`python3 ./{DIR_WORKFLOW}/scripts/get_context.py --mode packages`

## 检索提示

- 规范文件：`{spec_path}/**/*.md`
- 已有数据：`data/<行政区>/<主题>/`（`学校` / `小区` / `规划`），来源登记见各目录的 `来源.md`
- 任务产物：`.trellis/tasks/<task>/prd.md`、`design.md`、`implement.md`
- 本地检索：用 Glob 与 Grep
- 外部检索：优先官方来源（教育局、区政府、规划资源局），其次主流房产平台；
  必须记录发布主体、发布时间与原文关键句"""

    context_parts.append(project_structure)

    return "\n\n".join(context_parts)


def build_research_prompt(original_prompt: str, context: str) -> str:
    """构建检索代理的完整提示词"""
    return f"""# 检索代理任务（资料与来源检索）

你是多代理流程中的检索代理（平台标识 `trellis-research`）。

## 核心原则

**你只做一件事：找到并解释信息。**

你是记录者，不是评审者。检索结果必须**落盘**到 `{{TASK_DIR}}/research/<topic>.md`，
只在对话里回复视为失败。

## 项目信息

{context}

---

## 你的任务

{original_prompt}

---

## 工作流

1. **理解检索需求** - 分类（内部/外部/混合）、范围（全市 / 某区 / 某校）、期望产出
2. **规划检索** - 复杂需求先列出检索步骤
3. **执行检索** - 并行执行多个独立检索
4. **逐主题落盘** - 每个主题写入 `{{TASK_DIR}}/research/<topic-slug>.md`
5. **汇报** - 只回复文件路径 + 一句话摘要，不要粘贴全文

## 检索工具

| 工具 | 用途 |
|------|------|
| Glob | 按文件名查找已有数据文件 |
| Grep | 按内容检索字段、口径、来源 |
| Read | 读取文件内容 |
| 联网检索 | 官方政策、招生公告、划片范围、学校信息、数据平台 |

## 学区房来源检索的特别要求

每条发现必须包含：

1. **可信度分级**：`官方` / `平台` / `中介` / `非官方`
2. **发布主体与发布时间**：政策、划片类信息缺一不可
3. **生效时点**：对应哪个招生学年 / 数据对应哪个月
4. **原文关键段落**：原样引用「单价」「面积」「划片依据」的表述，不要改写
5. **可获得性**：是否可下载、是否需要登录、是否只有图表

## 严格边界

**只允许**：描述存在什么、在哪里、怎么运作

**禁止**（除非用户明确要求）：
- 提出改进建议
- 批评既有分析
- 修改任何文件（尤其 `data/` 下的数据文件——采集由执行代理负责）
- 执行任何 git 操作

## 汇报格式

- 写入的文件路径（相对仓库根）
- 每个文件一句话摘要
- 主会话当下必须知道的注意事项（如某来源不可得、某政策已废止）

不要粘贴检索全文——文件才是交付物。"""


def _string_value(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped
    return ""


def _hook_event_name(input_data: dict) -> str:
    """Return a hook event name from the documented snake/camel-case fields."""
    return _string_value(
        input_data.get("hook_event_name") or input_data.get("hookEventName")
    )


def _codex_subagent_type(input_data: dict) -> str:
    """Return a Trellis Codex agent type only for a native start event."""
    if _hook_event_name(input_data) != "SubagentStart":
        return ""
    agent_type = _string_value(
        input_data.get("agent_type") or input_data.get("agentType")
    )
    return agent_type if agent_type in AGENTS_ALL else ""


def build_codex_subagent_context(
    subagent_type: str,
    task_dir: str,
    context: str,
) -> str:
    """Build developer context for a native, already-dispatched Codex role."""
    role = subagent_type.removeprefix("trellis-")
    return f"""<!-- trellis-hook-injected -->
# Trellis Native {role.title()} Subagent

You are the dispatched `{subagent_type}` role for this task. Perform that role
directly; do not follow main-session dispatch or wait instructions, and do not
spawn another Trellis subagent.

Active task: {task_dir}

## Curated Context

{context}"""


def _handle_codex_subagent_start(input_data: dict) -> None:
    """Emit Codex developer context for a recognised native Trellis subagent.

    The event supplies the parent session id. Disabling the generic
    single-session fallback is essential here: native starts must never borrow
    a task from another Codex window when that parent id is absent or stale.
    """
    subagent_type = _codex_subagent_type(input_data)
    parent_session_id = _string_value(input_data.get("session_id"))
    if not subagent_type or not parent_session_id:
        return

    # Payload cwd first, then our own — some hosts (CodeBuddy IDE 4.10.4)
    # report "/" for every hook event. See inject-workflow-state.py.
    repo_root = None
    for candidate in (_string_value(input_data.get("cwd")), os.getcwd()):
        if not candidate:
            continue
        repo_root = find_repo_root(candidate)
        if repo_root:
            break
    if not repo_root:
        return

    task_dir = get_current_task(
        repo_root,
        {"session_id": parent_session_id},
        platform="codex",
        allow_single_session_fallback=False,
        allow_environment_context=False,
        require_existing=True,
    )
    if not task_dir:
        return

    if subagent_type in AGENTS_REQUIRE_TASK:
        task_dir_full = Path(repo_root) / task_dir
        if not task_dir_full.is_dir():
            return

    if subagent_type == AGENT_IMPLEMENT:
        context = get_implement_context(repo_root, task_dir)
    elif subagent_type == AGENT_CHECK:
        context = get_check_context(repo_root, task_dir)
    else:
        context = get_research_context(repo_root, task_dir)

    if not context:
        return

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": build_codex_subagent_context(
                subagent_type, task_dir, context
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=False))


def _extract_subagent_name(value: Any) -> str:
    """Extract a sub-agent name from common platform encodings.

    Cursor's native Task args encode custom sub-agents as a protobuf oneof,
    which can appear in hook JSON as either ``{"custom": {"name": "..."}}``
    or ``{"type": {"case": "custom", "value": {"name": "..."}}}``.
    """
    direct = _string_value(value)
    if direct:
        return direct

    if not isinstance(value, dict):
        return ""

    for key in ("name", "subagent_type_name", "subagentTypeName"):
        direct = _string_value(value.get(key))
        if direct:
            return direct

    custom = value.get("custom")
    if isinstance(custom, dict):
        custom_name = _string_value(custom.get("name"))
        if custom_name:
            return custom_name

    oneof = value.get("type")
    if isinstance(oneof, dict):
        case_name = _string_value(oneof.get("case"))
        if case_name == "custom":
            nested_value = oneof.get("value")
            if isinstance(nested_value, dict):
                custom_name = _string_value(nested_value.get("name"))
                if custom_name:
                    return custom_name
        if case_name:
            return case_name

    case_name = _string_value(value.get("case"))
    if case_name == "custom":
        nested_value = value.get("value")
        if isinstance(nested_value, dict):
            custom_name = _string_value(nested_value.get("name"))
            if custom_name:
                return custom_name
    if case_name:
        return case_name

    for agent_name in AGENTS_ALL:
        if agent_name in value:
            return agent_name

    return ""


def _extract_subagent_type(tool_input: dict) -> str:
    for key in (
        "subagent_type",
        "subagentType",
        "subagent_type_name",
        "subagentTypeName",
        "subagent_name",
        "subagentName",
        "agent_type",
        "agentType",
        "name",
    ):
        agent_name = _extract_subagent_name(tool_input.get(key))
        if agent_name:
            return agent_name
    return ""


def _parse_hook_input(input_data: dict) -> tuple[str, str, dict]:
    """Parse hook input across different platform formats.

    Returns (subagent_type, original_prompt, tool_input).
    Handles:
    - Claude Code / Qoder / Droid: tool_name=Task|Agent, tool_input.subagent_type
    - CodeBuddy: tool_name=task (IDE) or Task (CLI), tool_input.subagent_name
    - Cursor: tool_name=Task|Subagent, tool_input.subagent_type
    - Copilot CLI: toolName=task (camelCase key, lowercase value)
    - ZCode: toolName=Agent, toolInput/tool_input.subagent_type
    - Gemini CLI: tool_name IS the agent name (BeforeTool matcher already filtered)
    - Kiro: agentSpawn hook, agent_name field at top level
    """
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = input_data.get("toolInput", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Standard format: Task/Agent tool with subagent_type
    tool_name = input_data.get("tool_name", "") or input_data.get("toolName", "")
    if tool_name.lower() in ("task", "agent", "subagent"):
        return (
            _extract_subagent_type(tool_input),
            tool_input.get("prompt", ""),
            tool_input,
        )

    # Kiro: agentSpawn hook passes agent_name at top level
    agent_name = input_data.get("agent_name", "")
    if agent_name:
        return agent_name, tool_input.get("prompt", input_data.get("prompt", "")), tool_input

    # Gemini CLI: BeforeTool where tool_name IS the agent name
    # (matcher already ensured it's one of our agents)
    if tool_name in AGENTS_ALL:
        return tool_name, tool_input.get("prompt", ""), tool_input

    # Copilot CLI: toolName field (camelCase), value might be the agent name
    tool_name_camel = input_data.get("toolName", "")
    if tool_name_camel in AGENTS_ALL:
        return tool_name_camel, input_data.get("toolArgs", ""), tool_input

    return "", "", tool_input


def main():
    if os.environ.get("TRELLIS_HOOKS") == "0" or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1":
        sys.exit(0)

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not isinstance(input_data, dict):
        sys.exit(0)

    if _hook_event_name(input_data) == "SubagentStart":
        try:
            _handle_codex_subagent_start(input_data)
        except Exception:
            # A native context hook must never prevent Codex from spawning the
            # requested child when its runtime state is unavailable or stale.
            pass
        sys.exit(0)

    subagent_type, original_prompt, tool_input = _parse_hook_input(input_data)
    cwd = input_data.get("cwd", os.getcwd())

    # Only handle subagent types we care about
    if subagent_type not in AGENTS_ALL:
        sys.exit(0)

    # Find repo root
    repo_root = find_repo_root(cwd)
    if not repo_root:
        sys.exit(0)

    # Get current task directory (research doesn't require it)
    task_dir = get_current_task(
        repo_root,
        input_data,
        allow_single_session_fallback=True,
    )

    # implement/check need task directory
    if subagent_type in AGENTS_REQUIRE_TASK:
        if not task_dir:
            sys.exit(0)
        # Contain the pointer before reading anything through it. `task.py` now
        # refuses to store a ref that leaves the repo, but a session file
        # written before that fix can still hold one, and `trellis update`
        # does not rewrite session files — so a poisoned pointer outlives the
        # upgrade that closed the writer. This is the last hop before the
        # task's prd.md/design.md reach the model prompt, so it checks again.
        try:
            root_real = os.path.realpath(repo_root)
            # `.trellis` may itself be a symlink into a store outside the
            # repo (#567); its real location is a second legitimate base.
            workflow_real = os.path.realpath(os.path.join(repo_root, ".trellis"))
            task_dir_full = os.path.realpath(os.path.join(repo_root, task_dir))
            if not _real_path_contained(root_real, task_dir_full) and not (
                _real_path_contained(workflow_real, task_dir_full)
            ):
                sys.exit(0)
        except OSError:
            sys.exit(0)
        if not os.path.exists(task_dir_full):
            sys.exit(0)

    # Check for [finish] marker in prompt (check agent with finish context)
    is_finish_phase = "[finish]" in original_prompt.lower()

    # Get context and build prompt based on subagent type
    if subagent_type == AGENT_IMPLEMENT:
        assert task_dir is not None  # validated above
        context = get_implement_context(repo_root, task_dir)
        new_prompt = build_implement_prompt(original_prompt, context)
    elif subagent_type == AGENT_CHECK:
        assert task_dir is not None  # validated above
        if is_finish_phase:
            # Finish phase: use finish context (lighter, focused on final verification)
            context = get_finish_context(repo_root, task_dir)
            new_prompt = build_finish_prompt(original_prompt, context)
        else:
            # Regular check phase: use check context (full specs for self-fix loop)
            context = get_check_context(repo_root, task_dir)
            new_prompt = build_check_prompt(original_prompt, context)
    elif subagent_type == AGENT_RESEARCH:
        # Research can work without task directory
        context = get_research_context(repo_root, task_dir)
        new_prompt = build_research_prompt(original_prompt, context)
    else:
        sys.exit(0)

    if not context:
        sys.exit(0)

    # Return updated input. Most platforms ignore unrecognized fields, so we
    # include multiple formats. ZCode is stricter; live probing confirmed the
    # nested Claude-compatible shape below reaches the sub-agent prompt.
    updated = {**tool_input, "prompt": new_prompt}
    if _detect_platform(input_data) == "zcode":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": updated,
            }
        }
    else:
        output = {
            # Claude Code / Qoder / CodeBuddy / Droid format
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": updated,
            },
            # Cursor format
            "permission": "allow",
            "updated_input": updated,
            # Gemini format
            "updatedInput": updated,
        }

    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
