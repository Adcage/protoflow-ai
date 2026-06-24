import logging

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_history import format_tool_observation_history
from app.core.config import settings
from app.runtime.context import ChatHistoryEntry, ExecutionContext

logger = logging.getLogger("app.agent_loop.message_builder")


def _should_include_message(message: dict, current_mode: str) -> bool:
    """按 source 标签过滤：无 source 或 source=common 的所有模式可见；带 source 的仅在对应模式可见。"""
    source = message.get("source", "")
    if not source or source == "common":
        return True
    return source == current_mode


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


def _tool_messages(state: AgentLoopState) -> list[BaseMessage]:
    message = format_tool_observation_history(
        state.executed_tool_calls,
        max_total_chars=settings.agent_tool_history_max_chars,
        max_result_chars=settings.agent_tool_result_max_chars,
    )
    return [message] if message is not None else []


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
        if message.get("content") and _should_include_message(message, state.mode)
    )

    if current is not None and context.is_resume:
        messages.append(current)
    return messages
