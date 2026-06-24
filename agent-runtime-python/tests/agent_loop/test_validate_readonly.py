"""Validate 工具 schema 和执行器只读保护测试。

覆盖 Task 4-3 中关于 Validate 永久只读、write 工具在 schema 和执行器均不存在的保证。
"""

import pytest
from langchain_core.tools import BaseTool

from app.agent_loop.tool_policy import (
    AgentMode,
    MODE_TOOL_POLICIES,
    VALIDATE_TOOLS,
)
from app.agent_loop.tool_resolver import ModeToolResolver, ResolvedToolSet
from app.core.exceptions import AgentRuntimeError


class TestValidateReadOnlySchema:
    def test_validate_schema_has_no_write_tools(self):
        for tool_name in (
            "write_file",
            "modify_file",
            "delete_file",
            "apply_patch",
            "deploy",
        ):
            assert tool_name not in VALIDATE_TOOLS, (
                f"Validate 不应包含写工具: {tool_name}"
            )

    def test_resolver_filters_validate_to_readonly(self):
        candidates = []
        for name in (
            "read_file",
            "read_dir",
            "write_file",
            "modify_file",
            "delete_file",
            "run_checks",
            "submit_validation_report",
        ):
            t = _StubTool(name=name, description="stub")
            candidates.append(t)
        toolset = ModeToolResolver.resolve(AgentMode.VALIDATE, candidates)
        for name in toolset.names:
            assert "write" not in name
            assert "delete" not in name
            assert "modify" not in name
            assert "patch" not in name


class TestValidateExecutorRejectsForgedWrite:
    def test_validate_cannot_invoke_write_file(self):
        toolset = ResolvedToolSet(
            mode=AgentMode.VALIDATE,
            tools=(_StubTool(name="read_file", description="r"),),
        )
        with pytest.raises(AgentRuntimeError):
            toolset.require("write_file")

    def test_resolver_rejects_write_tool_for_validate(self):
        # Add required validate tools to satisfy the resolver
        candidates = [
            _StubTool(name="read_file", description="r"),
            _StubTool(name="write_file", description="w"),
            _StubTool(name="run_checks", description="rc"),
            _StubTool(name="submit_validation_report", description="svr"),
        ]
        toolset = ModeToolResolver.resolve(AgentMode.VALIDATE, candidates)
        assert "write_file" not in toolset.names


class TestImplementCannotResolveValidationIssue:
    def test_implement_cannot_resolve_validation_issue(self):
        impl_policy = MODE_TOOL_POLICIES[AgentMode.IMPLEMENT]
        for tool_name in (
            "resolve_validation_issue",
            "close_validation_issue",
            "submit_validation_report",
        ):
            assert tool_name not in impl_policy.allowed_tool_names


class _StubTool(BaseTool):
    name: str = "stub"
    description: str = "stub"

    def _run(self, **kwargs):
        return ""

    async def _arun(self, **kwargs):
        return ""
