"""统一工具解析：ModeToolResolver 和 ResolvedToolSet。

同一 ResolvedToolSet 同时用于模型绑定、动态 Prompt 工具摘要和工具执行。
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool

from app.agent_loop.tool_policy import AgentMode, MODE_TOOL_POLICIES
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


@dataclass(frozen=True)
class ResolvedToolSet:
    """不可变工具集合，同一实例同时用于 bind_tools、Prompt 摘要和工具执行。"""

    mode: AgentMode
    tools: tuple[BaseTool, ...]

    @property
    def names(self) -> frozenset[str]:
        return frozenset(t.name for t in self.tools)

    def require(self, tool_name: str) -> BaseTool:
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        raise AgentRuntimeError(
            f"模式 {self.mode.value} 未绑定工具 {tool_name}",
            code=AgentErrorCode.TOOL_CALL_FAILED,
        )

    async def invoke(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.require(tool_name)
        result = await tool.ainvoke(arguments)
        return str(result) if not isinstance(result, str) else result


class ModeToolResolver:
    """根据模式 policy 和候选工具，解析出本次实际可用的不可变工具集合。"""

    @staticmethod
    def resolve(mode: AgentMode, candidates: list[BaseTool]) -> ResolvedToolSet:
        policy = MODE_TOOL_POLICIES[mode]

        seen_names: dict[str, BaseTool] = {}
        for tool in candidates:
            if tool.name in seen_names:
                raise AgentRuntimeError(
                    f"候选工具中存在同名工具 {tool.name}，模式 {mode.value}",
                    code=AgentErrorCode.STATE_ERROR,
                )
            seen_names[tool.name] = tool

        allowed_tools: list[BaseTool] = []
        for tool in candidates:
            if tool.name in policy.allowed_tool_names:
                allowed_tools.append(tool)

        actual_names = {t.name for t in allowed_tools}
        missing_required = policy.required_tool_names - actual_names
        if missing_required:
            raise AgentRuntimeError(
                f"模式 {mode.value} 缺少必需工具: {missing_required}",
                code=AgentErrorCode.STATE_ERROR,
            )

        return ResolvedToolSet(mode=mode, tools=tuple(allowed_tools))
