import logging

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
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


def _tool_messages(state: AgentLoopState) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    records = compact_tool_records(
        state.executed_tool_calls,
        max_total_chars=settings.agent_tool_history_max_chars,
        max_result_chars=settings.agent_tool_result_max_chars,
    )
    for record in records:
        args = record.arguments
        if record.name == "write_file" and args.get("content_omitted"):
            length = args.get("content_length", 0)
            args = {
                "relative_path": args.get("relative_path", ""),
                "content": f"[已省略，{length}字符]",
            }
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": record.id,
                        "name": record.name,
                        "args": args,
                        "type": "tool_call",
                    }
                ],
            )
        )
        messages.append(
            ToolMessage(
                content=record.error or record.result or "",
                tool_call_id=record.id,
                name=record.name,
            )
        )
    return messages


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
