"""对话历史构建器，将 chat_history 转为 LangChain 消息列表。"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.runtime.context import ChatHistoryEntry, ExecutionContext


class HistoryBuilder:
    """对话历史构建器，将 chat_history 转为 LangChain 消息列表。"""

    def build_messages(
        self,
        context: ExecutionContext,
        system_prompt: str,
    ) -> list[BaseMessage]:
        """构建完整的 LLM 输入消息列表。"""
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        # 注入对话历史
        history = self._history_before_current(context)
        for entry in history:
            messages.append(self._message_from_role(entry.role, entry.content))

        # 注入当前用户消息
        if context.prompt:
            messages.append(HumanMessage(content=context.prompt))

        return messages

    def _history_before_current(self, context: ExecutionContext) -> list[ChatHistoryEntry]:
        """返回当前消息之前的历史，去除与当前 prompt 重复的最后一条。"""
        history = list(context.chat_history)
        if not history:
            return history
        latest = history[-1]
        if latest.role.strip().lower() in {"user", "human"}:
            if context.prompt and latest.content == context.prompt:
                history.pop()
        return history

    @staticmethod
    def _message_from_role(role: str, content: str) -> BaseMessage:
        """将数据库 role 字符串转为 LangChain 消息类型。"""
        normalized = role.strip().lower()
        if normalized in {"assistant", "ai"}:
            return AIMessage(content=content)
        return HumanMessage(content=content)
