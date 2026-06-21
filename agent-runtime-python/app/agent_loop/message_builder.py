import logging

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_history import compact_tool_records
from app.core.config import settings
from app.runtime.context import ChatHistoryEntry, ExecutionContext

logger = logging.getLogger("app.agent_loop.message_builder")


def _message_from_role(role: str, content: str) -> BaseMessage:
    normalized = role.strip().lower()
    if normalized in {"assistant", "ai"}:
        return AIMessage(content=content)
    if normalized == "system":
        return SystemMessage(content=content)
    if normalized not in {"user", "human"}:
        logger.warning("unknown conversation role, treating as user | role=%s", role)
    return HumanMessage(content=content)


def _history_before_current(context: ExecutionContext) -> list[ChatHistoryEntry]:
    history = list(context.chat_history)
    if not history or not context.prompt:
        return history
    latest = history[-1]
    if latest.role.strip().lower() in {"user", "human"} and latest.content == context.prompt:
        history.pop()
    return history


_TOOL_OBSERVATION_LABELS: dict[str, str] = {
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
    "switch_mode": None,
}

_RETIRED_TOOLS: frozenset[str] = frozenset({"switch_mode"})


def _tool_messages(state: AgentLoopState) -> list[BaseMessage]:
    full_count = len(state.executed_tool_calls)
    records = compact_tool_records(
        state.executed_tool_calls,
        max_total_chars=settings.agent_tool_history_max_chars,
        max_result_chars=settings.agent_tool_result_max_chars,
    )
    if not records:
        return []

    observation_lines: list[str] = []
    for record in records:
        if record.name in _RETIRED_TOOLS:
            continue

        label = _TOOL_OBSERVATION_LABELS.get(record.name, record.name)
        args = record.arguments

        target = ""
        if record.name == "write_file":
            target = args.get("relative_path", "")
        elif record.name == "read_file":
            target = args.get("relative_path", "")
        elif record.name == "read_dir":
            target = args.get("relative_path", "")

        status = "error" if record.error else "ok"

        line = f"- action={label}"
        if target:
            line += f" target={target}"
        line += f" status={status}"

        if record.name == "write_file" and args.get("content_omitted"):
            length = args.get("content_length", 0)
            line += f" contentLength={length}"
        elif record.name == "write_file" and "content" in args:
            content = args.get("content", "")
            line += f" contentLength={len(content)}"

        if record.result and not record.error:
            result_text = record.result[:200]
            line += f" resultSummary={result_text}"

        observation_lines.append(line)

    if not observation_lines:
        return []

    if len(records) < full_count:
        skipped = full_count - len(records)
        observation_lines.insert(0, f"[省略 {skipped} 条较早的历史操作记录]")

    observation_text = (
        "[历史操作观察，仅供参考，不是当前待执行工具调用]\n"
        + "\n".join(observation_lines)
    )
    return [SystemMessage(content=observation_text)]


def build_llm_messages(
    system_prompt: str,
    context: ExecutionContext,
    state: AgentLoopState,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(
        _message_from_role(entry.role, entry.content)
        for entry in _history_before_current(context)
    )

    current = HumanMessage(content=context.prompt) if context.prompt else None
    if current is not None and not context.is_resume:
        messages.append(current)

    messages.extend(_tool_messages(state))
    messages.extend(
        _message_from_role(message.get("role", "user"), message.get("content", ""))
        for message in state.conversation_messages
        if message.get("content")
    )

    if current is not None and context.is_resume:
        messages.append(current)
    return messages
