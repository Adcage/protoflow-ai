"""测试 HistoryBuilder 对话历史构建。"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent_loop_vnext.shared.history import HistoryBuilder
from app.runtime.context import ChatHistoryEntry, ExecutionContext, CodeGenType, RunMode


def _make_context(prompt: str = "写一个登录页", history: list[ChatHistoryEntry] | None = None) -> ExecutionContext:
    return ExecutionContext(
        agent_run_id=1, app_id=1, session_id=1, user_id=1,
        prompt=prompt,
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="/tmp/test",
        run_mode=RunMode.GENERATE,
        chat_history=tuple(history or []),
    )


def test_build_messages_empty_history():
    """无历史记录时只返回 system + current user 两条消息。"""
    builder = HistoryBuilder()
    context = _make_context()
    messages = builder.build_messages(context, "system prompt")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == "system prompt"
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "写一个登录页"


def test_build_messages_with_history():
    """有历史记录时正确插入 history + current user。"""
    history = [
        ChatHistoryEntry(id=1, role="user", content="帮我写个首页"),
        ChatHistoryEntry(id=2, role="assistant", content="好的，我来写首页..."),
    ]
    builder = HistoryBuilder()
    context = _make_context(history=history)
    messages = builder.build_messages(context, "system prompt")

    assert len(messages) == 4
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "帮我写个首页"
    assert isinstance(messages[2], AIMessage)
    assert messages[2].content == "好的，我来写首页..."
    assert isinstance(messages[3], HumanMessage)
    assert messages[3].content == "写一个登录页"


def test_history_before_current_dedup():
    """如果历史最后一条 user 消息和当前 prompt 重复，应去重。"""
    history = [
        ChatHistoryEntry(id=1, role="user", content="写一个登录页"),
    ]
    builder = HistoryBuilder()
    context = _make_context(history=history)
    messages = builder.build_messages(context, "system prompt")

    # 历史最后一条和当前 prompt 重复，应去重
    assert len(messages) == 2
    assert messages[0].content == "system prompt"
    assert messages[1].content == "写一个登录页"


def test_history_before_current_no_dedup():
    """如果最后一条不是 user 消息，不去重。"""
    history = [
        ChatHistoryEntry(id=1, role="user", content="写一个登录页"),
        ChatHistoryEntry(id=2, role="assistant", content="好的..."),
    ]
    builder = HistoryBuilder()
    # 获取 builder 内部方法
    result = builder._history_before_current(_make_context(history=history))
    assert len(result) == 2  # 不去重


def test_message_from_role_user():
    """user 或 human role 转 HumanMessage。"""
    from app.agent_loop_vnext.shared.history import HistoryBuilder
    msg1 = HistoryBuilder._message_from_role("user", "hello")
    assert isinstance(msg1, HumanMessage)
    msg2 = HistoryBuilder._message_from_role("human", "hello")
    assert isinstance(msg2, HumanMessage)


def test_message_from_role_assistant():
    """assistant 或 ai role 转 AIMessage。"""
    from app.agent_loop_vnext.shared.history import HistoryBuilder
    msg1 = HistoryBuilder._message_from_role("assistant", "hello")
    assert isinstance(msg1, AIMessage)
    msg2 = HistoryBuilder._message_from_role("ai", "hello")
    assert isinstance(msg2, AIMessage)
