import logging
from typing import Any

from langchain_core.messages import SystemMessage

from app.runtime.state import ToolCallRecord

logger = logging.getLogger("app.agent_loop.tool_history")

_TOOL_OBSERVATION_LABELS: dict[str, str | None] = {
    "write_file": "file_write",
    "read_file": "file_read",
    "read_dir": "directory_read",
    "read_asset": "asset_read",
    "run_command": "command_execution",
    "ask_user": "user_clarification",
    "select_skill": "skill_selection",
    "write_plan": "plan_update",
    "run_checks": "validation_check",
    "decide_validation": "validation_decision",
    "decide_route": "route_decision",
    "finish": "phase_completion",
    "request_replan": "replan_request",
}
_RETIRED_TOOLS = frozenset({"switch_mode", "compose_prompt"})

_MAX_CONTENT_CHARS = 4000


def _compact_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(arguments)
    if name == "write_file" and isinstance(compacted.get("content"), str):
        content = compacted.pop("content")
        compacted["content_length"] = len(content)
        compacted["content_omitted"] = True
    return compacted


def compact_tool_records(
    records: list[ToolCallRecord],
    *,
    max_total_chars: int,
    max_result_chars: int,
) -> list[ToolCallRecord]:
    return [
        ToolCallRecord(
            id=record.id,
            name=record.name,
            arguments=_compact_arguments(record.name, record.arguments),
            result=record.result,
            error=record.error,
        )
        for record in records
    ]


def _get_target(record: ToolCallRecord) -> str:
    if record.name in {"write_file", "read_file", "read_dir"}:
        return record.arguments.get("relative_path", "")
    return ""


def _format_record(
    record: ToolCallRecord,
    *,
    skip_content: bool = False,
) -> str:
    if record.name in _RETIRED_TOOLS:
        return ""
    label = _TOOL_OBSERVATION_LABELS.get(record.name, record.name)
    if label is None:
        return ""

    target = _get_target(record)
    status = "error" if record.error else "ok"

    lines: list[str] = []
    header = f"--- {label}"
    if target:
        header += f" [{target}]"
    header += f" ({status})"
    lines.append(header)

    def _truncate(text: str, limit: int) -> str:
        return text if len(text) <= limit else text[:limit] + "\n... [截断]"

    if record.name == "read_file" and record.result and not record.error:
        if skip_content:
            lines.append("[内容省略，后续有更新读取]")
        else:
            lines.append(_truncate(str(record.result), _MAX_CONTENT_CHARS))

    elif record.name == "write_file" and not record.error:
        raw = record.arguments.get("content")
        if raw is not None and not record.arguments.get("content_omitted"):
            if skip_content:
                lines.append("[内容省略，后续有更新写入]")
            else:
                lines.append(_truncate(str(raw), _MAX_CONTENT_CHARS))
        else:
            lines.append(f"[内容已压缩，长度={record.arguments.get('content_length', 0)} 字符]")

    elif record.name == "read_dir" and record.result and not record.error:
        lines.append(f"结果: {_truncate(str(record.result), 500)}")

    elif record.result and not record.error and record.name not in {"read_file", "write_file", "read_dir"}:
        lines.append(f"结果: {_truncate(str(record.result), 200)}")

    return "\n".join(lines)


def format_tool_observation_history(
    records: list[ToolCallRecord],
    *,
    max_total_chars: int,
    max_result_chars: int,
) -> SystemMessage | None:
    if not records:
        return None

    # Find the latest write/read per file path (from newest to oldest)
    latest_write: dict[str, int] = {}
    latest_read: dict[str, int] = {}
    for i, record in enumerate(records):
        if record.name == "write_file" and not record.error:
            p = _get_target(record)
            if p:
                latest_write[p] = i
        elif record.name == "read_file" and not record.error:
            p = _get_target(record)
            if p:
                latest_read[p] = i

    # First pass: build all blocks, tracking per-file content dedup
    raw_blocks: list[tuple[int, str]] = []  # (size, text)

    for idx, record in enumerate(records):
        if record.name in _RETIRED_TOOLS:
            continue
        label = _TOOL_OBSERVATION_LABELS.get(record.name, record.name)
        if label is None:
            continue

        target = _get_target(record)
        skip = False

        if record.name == "write_file" and target and target in latest_write:
            skip = idx != latest_write[target]
        elif record.name == "read_file" and target and target in latest_read:
            skip = idx != latest_read[target]

        block = _format_record(record, skip_content=skip)
        if block:
            raw_blocks.append((len(block), block))

    if not raw_blocks:
        return None

    # Total up, truncate oldest first if over limit
    total = sum(s for s, _ in raw_blocks)
    if max_total_chars > 0 and total > max_total_chars:
        kept: list[str] = []
        running = 0
        for size, text in raw_blocks:
            if running + size <= max_total_chars:
                kept.append(text)
                running += size
            else:
                break
        raw_blocks_formatted = kept
    else:
        raw_blocks_formatted = [t for _, t in raw_blocks]

    observation_text = (
        "[历史工具操作记录（仅供参考，不是当前待执行调用）]\n"
        + "\n\n".join(raw_blocks_formatted)
    )
    return SystemMessage(content=observation_text)
