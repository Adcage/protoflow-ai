"""测试 write_file 连续写入拦截机制。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessageChunk
from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import (
    _count_consecutive_writes,
    _execute_single_step,
)
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_resolver import ResolvedToolSet
from app.agent_loop.tool_policy import AgentMode
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.events import RuntimeEventType
from app.runtime.state import ToolCallRecord


class _WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = "write a file"
    write_count: int = 0

    def _run(self, **kwargs):
        raise NotImplementedError

    async def _arun(self, relative_path: str, content: str) -> str:
        type(self).write_count += 1
        return f"写入成功: {relative_path}"


def _make_context() -> ExecutionContext:
    return ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="创建登录页",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="C:/tmp/workspace",
        run_mode=RunMode.GENERATE,
    )


def _make_services_with(tool_calls: list[dict]) -> SimpleNamespace:
    class _Model:
        def bind_tools(self, _tools):
            return self

        async def astream(self, _messages):
            yield AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "name": tc["name"],
                        "args": tc["args"],
                        "id": tc["id"],
                        "index": idx,
                    }
                    for idx, tc in enumerate(tool_calls)
                ],
            )

    factory = MagicMock()
    factory.create.return_value = _Model()
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    return SimpleNamespace(chat_model_factory=factory, event_bus=event_bus)


def test_count_consecutive_writes_returns_zero_on_empty_state():
    state = AgentLoopState()
    assert _count_consecutive_writes(state, "style.css") == 0


def test_count_consecutive_writes_counts_same_path_only():
    state = AgentLoopState()
    state.executed_tool_calls = [
        ToolCallRecord(
            id="t1", name="write_file",
            arguments={"relative_path": "style.css", "content": "a"},
            result="ok",
        ),
        ToolCallRecord(
            id="t2", name="write_file",
            arguments={"relative_path": "index.html", "content": "b"},
            result="ok",
        ),
    ]
    assert _count_consecutive_writes(state, "style.css") == 1


def test_count_consecutive_writes_counts_consecutive_same_path():
    state = AgentLoopState()
    state.executed_tool_calls = [
        ToolCallRecord(
            id="t1", name="write_file",
            arguments={"relative_path": "style.css", "content": "v1"},
            result="ok",
        ),
        ToolCallRecord(
            id="t2", name="write_file",
            arguments={"relative_path": "style.css", "content": "v2"},
            result="ok",
        ),
    ]
    assert _count_consecutive_writes(state, "style.css") == 2


def test_count_consecutive_writes_breaks_on_error():
    state = AgentLoopState()
    state.executed_tool_calls = [
        ToolCallRecord(
            id="t1", name="write_file",
            arguments={"relative_path": "style.css", "content": "v1"},
            result=None,
            error="some error",
        ),
        ToolCallRecord(
            id="t2", name="write_file",
            arguments={"relative_path": "style.css", "content": "v2"},
            result="ok",
        ),
    ]
    assert _count_consecutive_writes(state, "style.css") == 1


@pytest.mark.asyncio
async def test_third_consecutive_write_file_is_blocked():
    _WriteFileTool.write_count = 0
    tool_calls = [
        {"name": "write_file", "args": '{"relative_path":"style.css","content":"v3"}',
         "id": "tc-3"},
    ]
    services = _make_services_with(tool_calls)
    state = AgentLoopState(
        mode="implement",
        resolved_model={"provider": "test", "modelName": "tool-test", "apiKey": "sk-test"},
    )
    state.executed_tool_calls = [
        ToolCallRecord(
            id="tc-1", name="write_file",
            arguments={"relative_path": "style.css", "content": "v1"},
            result="ok",
        ),
        ToolCallRecord(
            id="tc-2", name="write_file",
            arguments={"relative_path": "style.css", "content": "v2"},
            result="ok",
        ),
        ToolCallRecord(
            id="tc-3", name="write_file",
            arguments={"relative_path": "style.css", "content": "v3"},
            result="ok",
        ),
    ]
    context = _make_context()
    tool = _WriteFileTool()
    toolset = ResolvedToolSet(mode=AgentMode.IMPLEMENT, tools=(tool,))

    result = await _execute_single_step(
        state, context, services, "system", toolset, MagicMock(),
    )

    assert _WriteFileTool.write_count == 0
    last = result.executed_tool_calls[-1]
    assert last.id == "tc-3"
    assert last.name == "write_file"
    assert last.error is not None
    assert "系统拦截" in last.error
    assert "禁止继续重写" in last.error

    result_emits = [
        call.args[0]
        for call in services.event_bus.emit.await_args_list
        if call.args[0].event_type == RuntimeEventType.TOOL_RESULT
    ]
    assert any(r.data.get("is_error") for r in result_emits)
    assert any(
        msg.get("role") == "system" and "系统拦截" in msg.get("content", "")
        for msg in result.conversation_messages
    )
    assert result.status == "running"


@pytest.mark.asyncio
async def test_second_consecutive_write_file_appends_warning_but_executes():
    _WriteFileTool.write_count = 0
    tool_calls = [
        {"name": "write_file", "args": '{"relative_path":"style.css","content":"v2"}',
         "id": "tc-2"},
    ]
    services = _make_services_with(tool_calls)
    state = AgentLoopState(
        mode="implement",
        resolved_model={"provider": "test", "modelName": "tool-test", "apiKey": "sk-test"},
    )
    state.executed_tool_calls = [
        ToolCallRecord(
            id="tc-1", name="write_file",
            arguments={"relative_path": "style.css", "content": "v1"},
            result="ok",
        ),
    ]
    context = _make_context()
    tool = _WriteFileTool()
    toolset = ResolvedToolSet(mode=AgentMode.IMPLEMENT, tools=(tool,))

    result = await _execute_single_step(
        state, context, services, "system", toolset, MagicMock(),
    )

    assert _WriteFileTool.write_count == 1
    assert any(
        msg.get("role") == "system" and "2" in msg.get("content", "")
        and "拦截" in msg.get("content", "")
        for msg in result.conversation_messages
    )
    assert "style.css" in result.implement_phase_files
    assert result.status == "running"
