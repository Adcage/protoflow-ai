import pytest
from unittest.mock import MagicMock

from langchain_core.tools import BaseTool

from app.agent_loop.tool_policy import (
    AgentMode,
    MODE_TOOL_POLICIES,
    PLAN_TOOLS,
    ROUTE_TOOLS,
    VALIDATE_TOOLS,
    IMPLEMENT_TOOLS,
)
from app.agent_loop.tool_resolver import ModeToolResolver
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


class TestReadonlyModesDoNotAllowWriteFile:
    def test_plan_no_write_file(self):
        policy = MODE_TOOL_POLICIES[AgentMode.PLAN]
        assert "write_file" not in policy.allowed_tool_names

    def test_route_no_write_file(self):
        policy = MODE_TOOL_POLICIES[AgentMode.ROUTE]
        assert "write_file" not in policy.allowed_tool_names

    def test_validate_no_write_file(self):
        policy = MODE_TOOL_POLICIES[AgentMode.VALIDATE]
        assert "write_file" not in policy.allowed_tool_names


class TestImplementAllowsWriteFile:
    def test_implement_has_write_file(self):
        policy = MODE_TOOL_POLICIES[AgentMode.IMPLEMENT]
        assert "write_file" in policy.allowed_tool_names

    def test_implement_has_structured_replan_request(self):
        policy = MODE_TOOL_POLICIES[AgentMode.IMPLEMENT]
        assert "request_replan" in policy.allowed_tool_names

    @pytest.mark.parametrize("mode", [AgentMode.PLAN, AgentMode.ROUTE, AgentMode.VALIDATE])
    def test_other_modes_do_not_allow_replan_request(self, mode):
        assert "request_replan" not in MODE_TOOL_POLICIES[mode].allowed_tool_names


class TestValidateRejectsForgedWriteFile:
    def test_require_allowed_raises_on_write_file(self):
        policy = MODE_TOOL_POLICIES[AgentMode.VALIDATE]
        with pytest.raises(AgentRuntimeError) as exc_info:
            policy.require_allowed("write_file")
        assert exc_info.value.code == AgentErrorCode.TOOL_CALL_FAILED
        assert "write_file" in exc_info.value.message


class TestUnknownToolIsRejected:
    @pytest.mark.parametrize("mode", list(AgentMode))
    def test_unknown_tool_rejected(self, mode):
        policy = MODE_TOOL_POLICIES[mode]
        with pytest.raises(AgentRuntimeError) as exc_info:
            policy.require_allowed("totally_fake_tool")
        assert exc_info.value.code == AgentErrorCode.TOOL_CALL_FAILED


class _StubTool(BaseTool):
    name: str = "stub"
    description: str = "stub"

    def _run(self, **kwargs):
        raise NotImplementedError

    async def _arun(self, **kwargs):
        return "ok"


def _make_tools(names: list[str]) -> list[BaseTool]:
    return [_StubTool(name=n) for n in names]


class TestRouteNodeBoundToolNamesAreReadonly:
    def test_route_tools_match_allowlist(self):
        tools = _make_tools(list(ROUTE_TOOLS))
        toolset = ModeToolResolver.resolve(AgentMode.ROUTE, tools)
        assert toolset.names == ROUTE_TOOLS


class TestValidateNodeBoundToolNamesAreReadonly:
    def test_validate_tools_match_allowlist(self):
        tools = _make_tools(list(VALIDATE_TOOLS))
        toolset = ModeToolResolver.resolve(AgentMode.VALIDATE, tools)
        assert toolset.names == VALIDATE_TOOLS


class TestBoundToolsMatchHandlers:
    @pytest.mark.parametrize("mode", list(AgentMode))
    def test_tool_names_match_resolver(self, mode):
        all_names = PLAN_TOOLS | IMPLEMENT_TOOLS | ROUTE_TOOLS | VALIDATE_TOOLS
        tools = _make_tools(list(all_names))
        toolset = ModeToolResolver.resolve(mode, tools)
        tool_names = toolset.names
        allowed = MODE_TOOL_POLICIES[mode].allowed_tool_names
        assert tool_names == allowed & {t.name for t in tools}


class TestPermissionDenialIsRecorded:
    @pytest.mark.asyncio
    async def test_forged_write_file_rejected_as_recoverable(self):
        """伪造 write_file 调用在 Validate 模式下被 toolset.require() 拒绝。

        TOOL_CALL_FAILED 属于可恢复错误：executor 把错误作为 tool result 返回给模型
        让它自行修正（换工具），而不是终止整次 run。错误仍被记录到 executed_tool_calls。
        """
        from app.agent_loop.state import AgentLoopState
        from app.agent_loop.nodes.step_base import _execute_single_step
        from app.agent_loop.tool_resolver import ModeToolResolver
        from app.runtime.context import ExecutionContext, CodeGenType, RunMode
        from app.tools.file_tools import Workspace, FileTools

        state = AgentLoopState(mode="validate", status="running")
        state.resolved_model = {"provider": "test", "modelName": "test"}

        context = ExecutionContext(
            agent_run_id=1,
            app_id=1,
            session_id=1,
            user_id=1,
            prompt="test",
            code_gen_type=CodeGenType.VUE_PROJECT,
            workspace_path="/tmp/test_workspace_policy",
            run_mode=RunMode.GENERATE,
        )

        async def _noop_emit(event):
            pass

        event_bus = MagicMock()
        event_bus.emit = _noop_emit

        chat_model = MagicMock()
        chat_model.bind_tools = MagicMock(return_value=chat_model)
        chat_model.astream = MagicMock(return_value=aiter_chunks_with_write_file())

        factory = MagicMock()
        factory.create = MagicMock(return_value=chat_model)

        services = MagicMock()
        services.chat_model_factory = factory
        services.event_bus = event_bus
        services.quality_checker = None

        workspace = Workspace(context.workspace_path)
        file_tools = FileTools(workspace)

        validate_tools = _make_tools(["run_checks", "submit_validation_report"])
        toolset = ModeToolResolver.resolve(AgentMode.VALIDATE, validate_tools)

        result = await _execute_single_step(
            state,
            context,
            services,
            "test prompt",
            toolset,
            file_tools,
        )

        # 可恢复错误不终止 run
        assert result.status != "failed"
        # 越权调用仍被记录
        assert any(tc.name == "write_file" and tc.error for tc in result.executed_tool_calls)


async def aiter_chunks_with_write_file():
    from langchain_core.messages import AIMessageChunk

    chunk = AIMessageChunk(
        content="",
        tool_calls=[
            {
                "id": "tc1",
                "name": "write_file",
                "args": {"relative_path": "test.css", "content": "h1{}"},
            }
        ],
    )
    yield chunk
