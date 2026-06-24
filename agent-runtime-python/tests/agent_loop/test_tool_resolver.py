"""Phase 1 Task 1-1 测试：ModeToolResolver 和 ResolvedToolSet。"""

import pytest

from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from langchain_core.tools import BaseTool


class _StubTool(BaseTool):
    name: str = ""
    description: str = "stub"

    def _run(self, *args, **kwargs):
        return "stub"

    async def _arun(self, *args, **kwargs):
        return "stub"


def _make_tools(names: list[str]) -> list[BaseTool]:
    return [_StubTool(name=n) for n in names]


class TestResolverFiltersToolsByMode:
    """混合候选工具；预期只返回 allowlist 交集。"""

    @pytest.mark.parametrize(
        "mode,expected_names",
        [
            (AgentMode.ROUTE, frozenset({"read_file", "read_dir", "decide_route"})),
            (AgentMode.PLAN, frozenset({
                "read_file", "read_dir", "read_asset", "run_command",
                "ask_user", "select_skill", "write_plan",
            })),
            (AgentMode.IMPLEMENT, frozenset({
                "read_file", "read_dir", "read_asset", "write_file",
                "run_command", "complete_implementation",
            })),
            (AgentMode.VALIDATE, frozenset({
                "read_file", "read_dir", "run_checks", "submit_validation_report",
            })),
        ],
    )
    def test_resolver_filters_tools_by_mode(self, mode, expected_names):
        all_tools = _make_tools([
            "read_file", "read_dir", "read_asset", "write_file",
            "run_command", "ask_user", "select_skill", "write_plan",
            "complete_implementation", "decide_route", "run_checks",
            "submit_validation_report",
        ])
        toolset = ModeToolResolver.resolve(mode, all_tools)
        assert toolset.names == expected_names


class TestResolverRejectsDuplicateNames:
    """两个同名工具；预期 STATE_ERROR。"""

    def test_resolver_rejects_duplicate_names(self):
        tools = _make_tools(["read_file", "decide_route"]) + [_StubTool(name="read_file")]
        with pytest.raises(AgentRuntimeError) as exc_info:
            ModeToolResolver.resolve(AgentMode.ROUTE, tools)
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR


class TestResolverRejectsMissingRequiredTool:
    """Route 缺少 decide_route；预期 STATE_ERROR。"""

    def test_resolver_rejects_missing_required_tool(self):
        tools = _make_tools(["read_file", "read_dir"])
        with pytest.raises(AgentRuntimeError) as exc_info:
            ModeToolResolver.resolve(AgentMode.ROUTE, tools)
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR


class TestResolvedToolSetRejectsUnboundInvocation:
    """调用未绑定工具；预期 TOOL_CALL_FAILED。"""

    def test_resolved_toolset_rejects_unbound_invocation(self):
        tools = _make_tools(["read_file", "decide_route"])
        toolset = ModeToolResolver.resolve(AgentMode.ROUTE, tools)

        with pytest.raises(AgentRuntimeError) as exc_info:
            toolset.require("write_file")
        assert exc_info.value.code == AgentErrorCode.TOOL_CALL_FAILED


class TestBoundToolsAreExactlyExecutableTools:
    """模型绑定集合与可执行集合完全相同。"""

    @pytest.mark.parametrize("mode", list(AgentMode))
    def test_bound_tools_are_exactly_executable_tools(self, mode: AgentMode):
        all_tools = _make_tools([
            "read_file", "read_dir", "read_asset", "write_file",
            "run_command", "ask_user", "select_skill", "write_plan",
            "complete_implementation", "decide_route", "run_checks",
            "submit_validation_report",
        ])
        toolset = ModeToolResolver.resolve(mode, all_tools)

        bind_names = frozenset(t.name for t in toolset.tools)
        exec_names = toolset.names
        assert bind_names == exec_names

        for tool in toolset.tools:
            assert toolset.require(tool.name) is tool
