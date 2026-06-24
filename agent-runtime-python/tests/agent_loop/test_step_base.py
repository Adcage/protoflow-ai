"""step_base 工具错误处理测试。

核心契约：状态机门禁拒绝（STATE_ERROR）、参数校验失败（TOOL_ARGS_ERROR）、
工具执行失败（TOOL_CALL_FAILED）和 Skill 资源读取失败属于可恢复错误，
executor 必须把错误作为 tool result 返回给模型，让它自行修正；
不应终止整次 run。安全拦截（PATH_TRAVERSAL_BLOCKED 等）和其他错误
仍然走 RUNTIME_ERROR + 终止 run 的路径。
"""

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessageChunk
from langchain_core.tools import BaseTool
from unittest.mock import AsyncMock, MagicMock

from app.agent_loop.nodes.step_base import (
    _RECOVERABLE_TOOL_ERROR_CODES,
    _classify_tool_error,
    _execute_single_step,
)
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ResolvedToolSet
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.events import RuntimeEventType


class TestClassifyToolError:
    def test_state_error_is_recoverable(self):
        """状态机门禁拒绝（典型场景：在 discover_direction 调 record_project_inspection）
        必须被识别为可恢复，让模型换工具重试。"""
        err = AgentRuntimeError(
            "当前 PlanStage=discover_direction 不允许该提交操作",
            code=AgentErrorCode.STATE_ERROR,
        )
        recoverable, code = _classify_tool_error(err)
        assert recoverable is True
        assert code == int(AgentErrorCode.STATE_ERROR)

    def test_tool_args_error_is_recoverable(self):
        """参数校验失败：模型可修正参数后重试。"""
        err = AgentRuntimeError(
            "missing required field: target_users",
            code=AgentErrorCode.TOOL_ARGS_ERROR,
        )
        recoverable, code = _classify_tool_error(err)
        assert recoverable is True
        assert code == int(AgentErrorCode.TOOL_ARGS_ERROR)

    def test_path_traversal_is_not_recoverable(self):
        """PATH_TRAVERSAL_BLOCKED 等安全类错误不可恢复：
        executor 应当终止 run，避免模型反复试探。返回自身错误码。"""
        err = AgentRuntimeError(
            "path traversal blocked",
            code=AgentErrorCode.PATH_TRAVERSAL_BLOCKED,
        )
        recoverable, code = _classify_tool_error(err)
        assert recoverable is False
        assert code == int(AgentErrorCode.PATH_TRAVERSAL_BLOCKED)

    def test_model_call_failed_is_not_recoverable(self):
        """模型调用失败：底层 LLM 错误，整次 run 应当终止。"""
        err = AgentRuntimeError(
            "model call failed",
            code=AgentErrorCode.MODEL_CALL_FAILED,
        )
        recoverable, _ = _classify_tool_error(err)
        assert recoverable is False

    def test_tool_call_failed_is_recoverable(self):
        """TOOL_CALL_FAILED（如资源不存在、文件操作失败等）属于可恢复错误：
        模型可换路径或跳过，不应终止整次 run。"""
        err = AgentRuntimeError(
            "tool call failed",
            code=AgentErrorCode.TOOL_CALL_FAILED,
        )
        recoverable, code = _classify_tool_error(err)
        assert recoverable is True
        assert code == int(AgentErrorCode.TOOL_CALL_FAILED)

    def test_plain_exception_is_not_recoverable(self):
        """非 AgentRuntimeError 的异常（如 RuntimeError, ValueError）一律不可恢复。"""
        recoverable, code = _classify_tool_error(RuntimeError("boom"))
        assert recoverable is False
        assert code == int(AgentErrorCode.INTERNAL_ERROR)

        recoverable, _ = _classify_tool_error(ValueError("bad arg"))
        assert recoverable is False

    def test_recoverable_codes_constant_is_frozen_and_explicit(self):
        """可恢复错误码集合必须明确：只放真正可由模型自纠的根因。
        TOOL_CALL_FAILED / SKILL_RESOURCE_NOT_FOUND / SKILL_RESOURCE_READ_FAILED
        属于可恢复：模型可换路径或跳过。
        安全拦截（PATH_TRAVERSAL_BLOCKED / COMMAND_NOT_ALLOWED / COMMAND_INJECTION_BLOCKED）
        不可恢复：必须终止 run。"""
        assert isinstance(_RECOVERABLE_TOOL_ERROR_CODES, frozenset)
        assert int(AgentErrorCode.STATE_ERROR) in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.TOOL_ARGS_ERROR) in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.TOOL_CALL_FAILED) in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.SKILL_RESOURCE_NOT_FOUND) in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.SKILL_RESOURCE_READ_FAILED) in _RECOVERABLE_TOOL_ERROR_CODES
        # 安全拦截不可恢复
        assert int(AgentErrorCode.MODEL_CALL_FAILED) not in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.PATH_TRAVERSAL_BLOCKED) not in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.COMMAND_NOT_ALLOWED) not in _RECOVERABLE_TOOL_ERROR_CODES
        assert int(AgentErrorCode.COMMAND_INJECTION_BLOCKED) not in _RECOVERABLE_TOOL_ERROR_CODES


# ---------------------------------------------------------------------------
# 集成测试：executor 在工具抛 STATE_ERROR 时不应终止 run
# ---------------------------------------------------------------------------


class _StateGuardedTool(BaseTool):
    """模拟 plan_tools 中会抛 STATE_ERROR 的工具（例如 record_project_inspection
    在 discover_direction 阶段被调用）。"""

    name: str = "record_project_inspection"
    description: str = "记录项目检查"

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError

    async def _arun(self, **kwargs: Any) -> str:
        raise AgentRuntimeError(
            "当前 PlanStage=discover_direction 不允许该提交操作；"
            "需要在 ('discover_scope', 'inspect_existing_project') 阶段进行",
            code=AgentErrorCode.STATE_ERROR,
        )


class _RecoverableToolCallingModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        yield AIMessageChunk(
            content="",
            tool_call_chunks=[
                {
                    "name": "record_project_inspection",
                    "args": '{"decision":"inspected","summary":"x","evidence_files":["a"]}',
                    "id": "tool-1",
                    "index": 0,
                }
            ],
        )


def _make_event_bus() -> MagicMock:
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


def _emit_event_types(bus: MagicMock) -> list[RuntimeEventType]:
    return [call.args[0].event_type for call in bus.emit.await_args_list]


def _last_tool_result_data(bus: MagicMock) -> dict[str, Any] | None:
    for call in reversed(bus.emit.await_args_list):
        event = call.args[0]
        if event.event_type == RuntimeEventType.TOOL_RESULT:
            return event.data
    return None


@pytest.mark.asyncio
async def test_state_error_does_not_terminate_run():
    """契约：工具抛 STATE_ERROR 时，state.status 不应变 failed，事件流必须
    包含 TOOL_RESULT（让模型看到错误并重试）且不包含 RUNTIME_ERROR。"""
    event_bus = _make_event_bus()
    factory = MagicMock()
    factory.create.return_value = _RecoverableToolCallingModel()
    services = SimpleNamespace(chat_model_factory=factory, event_bus=event_bus)

    state = AgentLoopState(
        resolved_model={"provider": "test", "modelName": "test", "apiKey": "sk-test"},
    )
    # 把 plan_stage 设为 discover_direction 模拟用户真实场景
    state._state_envelope = state._to_envelope()
    state._state_envelope.workflow.plan.plan_stage = "discover_direction"

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
    toolset = ResolvedToolSet(mode=AgentMode.PLAN, tools=(_StateGuardedTool(),))

    result = await _execute_single_step(
        state,
        context,
        services,
        "系统规则",
        toolset,
        MagicMock(),
    )

    # 核心契约：可恢复错误不终止 run
    assert result.status != "failed", (
        f"STATE_ERROR 不应终止 run，但 status={result.status}"
    )

    # 事件流：必须有 TOOL_RESULT（让模型看到错误），不能有 RUNTIME_ERROR
    types = _emit_event_types(event_bus)
    assert RuntimeEventType.TOOL_RESULT in types
    assert RuntimeEventType.RUNTIME_ERROR not in types

    # 错误内容必须传达给模型
    tool_result = _last_tool_result_data(event_bus)
    assert tool_result is not None
    assert tool_result.get("is_error") is True
    assert "PlanStage" in tool_result.get("result", "")

