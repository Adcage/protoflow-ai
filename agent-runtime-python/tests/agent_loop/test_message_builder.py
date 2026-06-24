from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent_loop.message_builder import build_llm_messages
from app.agent_loop.state import AgentLoopState
from app.runtime.context import ChatHistoryEntry, CodeGenType, ExecutionContext, RunMode
from app.runtime.state import ToolCallRecord


def make_context(
    *,
    prompt: str,
    history: tuple[ChatHistoryEntry, ...] = (),
    is_resume: bool = False,
) -> ExecutionContext:
    return ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt=prompt,
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="C:/tmp/workspace",
        run_mode=RunMode.GENERATE,
        chat_history=history,
        is_resume=is_resume,
    )


def test_new_request_contains_current_prompt_once():
    prompt = "创建企业后台登录页面"
    context = make_context(
        prompt=prompt,
        history=(ChatHistoryEntry(id=1, role="user", content=prompt),),
    )

    messages = build_llm_messages("系统规则", context, AgentLoopState())

    assert sum(message.content == prompt for message in messages) == 1
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[-1], HumanMessage)


def test_resume_answer_is_after_previous_tool_history():
    prompt = "需求补充：企业后台登录页面\n\n请继续生成。"
    state = AgentLoopState()
    state.executed_tool_calls = [
        ToolCallRecord(
            id="ask-1",
            name="ask_user",
            arguments={"question": "您想创建什么样的登录界面？"},
            result="等待用户回答",
        )
    ]
    state.conversation_messages = [
        {"role": "system", "content": "上轮校验失败，请修复布局"},
    ]
    context = make_context(
        prompt=prompt,
        history=(
            ChatHistoryEntry(id=1, role="user", content="创建登录页面"),
            ChatHistoryEntry(id=2, role="ai", content="您想创建什么样的登录界面？"),
            ChatHistoryEntry(id=3, role="user", content=prompt),
        ),
        is_resume=True,
    )

    messages = build_llm_messages("系统规则", context, state)

    assert sum(message.content == prompt for message in messages) == 1
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == prompt
    observation_messages = [m for m in messages if isinstance(m, SystemMessage) and "历史工具操作记录" in m.content]
    assert len(observation_messages) >= 1


def test_write_file_history_includes_content_in_tool_call():
    state = AgentLoopState()
    state.executed_tool_calls = [
        ToolCallRecord(
            id="write-1",
            name="write_file",
            arguments={
                "relative_path": "style.css",
                "content": "body { color: #111; }",
            },
            result="写入成功: style.css",
        )
    ]

    messages = build_llm_messages("系统规则", make_context(prompt="继续"), state)

    observation_messages = [
        message for message in messages
        if isinstance(message, SystemMessage) and "历史工具操作记录" in message.content
    ]
    assert len(observation_messages) == 1
    observation = observation_messages[0].content
    assert "file_write" in observation
    assert "style.css" in observation
    assert "--- file_write" in observation
    assert "body { color: #111; }" in observation


def test_conversation_roles_are_preserved():
    state = AgentLoopState()
    state.conversation_messages = [
        {"role": "assistant", "content": "上一轮结论"},
        {"role": "system", "content": "校验反馈"},
        {"role": "user", "content": "额外说明"},
    ]

    messages = build_llm_messages("系统规则", make_context(prompt="当前需求"), state)

    assert any(
        isinstance(message, AIMessage) and message.content == "上一轮结论"
        for message in messages
    )
    assert any(
        isinstance(message, SystemMessage) and message.content == "校验反馈"
        for message in messages
    )
    assert any(
        isinstance(message, HumanMessage) and message.content == "额外说明"
        for message in messages
    )


def test_only_latest_persisted_current_message_is_removed():
    prompt = "继续生成"
    context = make_context(
        prompt=prompt,
        history=(
            ChatHistoryEntry(id=1, role="user", content=prompt),
            ChatHistoryEntry(id=2, role="ai", content="请确认"),
            ChatHistoryEntry(id=3, role="user", content=prompt),
        ),
    )

    messages = build_llm_messages("系统规则", context, AgentLoopState())

    assert sum(
        isinstance(message, HumanMessage) and message.content == prompt
        for message in messages
    ) == 2
