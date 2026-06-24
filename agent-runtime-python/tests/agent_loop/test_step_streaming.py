from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessageChunk
from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import _execute_single_step, _stream_invoke
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_resolver import ResolvedToolSet
from app.agent_loop.tool_policy import AgentMode
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.events import RuntimeEventType


class _FailingTool(BaseTool):
    name: str = "read_file"
    description: str = "read a file"

    def _run(self, **kwargs):
        raise RuntimeError("missing file")

    async def _arun(self, **kwargs):
        raise RuntimeError("missing file")


class _NoopTool(BaseTool):
    name: str = "read_file"
    description: str = "read a file"

    def _run(self, **kwargs):
        return "ok"

    async def _arun(self, **kwargs):
        return "ok"


def _make_toolset(mode=AgentMode.VALIDATE, tools=None):
    return ResolvedToolSet(mode=mode, tools=tuple(tools or []))


class StreamingModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        yield AIMessageChunk(content="你")
        yield AIMessageChunk(content="好")


class ToolCallingModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        yield AIMessageChunk(
            content="",
            tool_call_chunks=[
                {
                    "name": "read_file",
                    "args": '{"relative_path":"missing.txt"}',
                    "id": "tool-1",
                    "index": 0,
                }
            ],
        )


def make_event_bus():
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    return event_bus


def emitted_texts(event_bus) -> list[str]:
    return [
        call.args[0].data["text"]
        for call in event_bus.emit.await_args_list
        if call.args[0].event_type == RuntimeEventType.TEXT_DELTA
    ]


@pytest.mark.asyncio
async def test_stream_invoke_emits_each_delta_once():
    event_bus = make_event_bus()

    text, tool_calls, _ = await _stream_invoke(StreamingModel(), [], event_bus)

    assert text == "你好"
    assert tool_calls == []
    assert emitted_texts(event_bus) == ["你好"]


@pytest.mark.asyncio
async def test_execute_single_step_does_not_reemit_aggregate_text():
    event_bus = make_event_bus()
    factory = MagicMock()
    factory.create.return_value = StreamingModel()
    services = SimpleNamespace(chat_model_factory=factory, event_bus=event_bus)
    state = AgentLoopState(
        resolved_model={"provider": "test", "modelName": "streaming-test"},
    )
    context = ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="创建登录页",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="C:/tmp/workspace",
        run_mode=RunMode.GENERATE,
    )

    toolset = _make_toolset()

    result = await _execute_single_step(
        state,
        context,
        services,
        "系统规则",
        toolset,
        MagicMock(),
    )

    assert emitted_texts(event_bus) == ["你好"]
    assert result.model_response_text == "你好"


@pytest.mark.asyncio
async def test_execute_single_step_records_failed_tool_calls():
    event_bus = make_event_bus()
    factory = MagicMock()
    factory.create.return_value = ToolCallingModel()
    services = SimpleNamespace(chat_model_factory=factory, event_bus=event_bus)
    state = AgentLoopState(
        resolved_model={"provider": "test", "modelName": "tool-test", "apiKey": "sk-test"},
    )
    context = ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="读取文件",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="C:/tmp/workspace",
        run_mode=RunMode.GENERATE,
    )

    toolset = _make_toolset(tools=[_FailingTool()])

    result = await _execute_single_step(
        state,
        context,
        services,
        "系统规则",
        toolset,
        MagicMock(),
    )

    assert len(result.executed_tool_calls) == 1
    record = result.executed_tool_calls[0]
    assert record.id == "tool-1"
    assert record.name == "read_file"
    assert record.arguments == {"relative_path": "missing.txt"}
    assert record.result is None
    assert "missing file" in record.error


@pytest.mark.asyncio
async def test_execute_single_step_marks_state_failed_after_tool_error():
    event_bus = make_event_bus()
    factory = MagicMock()
    factory.create.return_value = ToolCallingModel()
    services = SimpleNamespace(chat_model_factory=factory, event_bus=event_bus)
    state = AgentLoopState(
        resolved_model={"provider": "test", "modelName": "tool-test", "apiKey": "sk-test"},
    )
    context = ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="读取文件",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="C:/tmp/workspace",
        run_mode=RunMode.GENERATE,
    )

    toolset = _make_toolset(tools=[_FailingTool()])

    result = await _execute_single_step(
        state,
        context,
        services,
        "系统规则",
        toolset,
        MagicMock(),
    )

    assert result.status == "failed"
