"""Phase 3 兼容入口：旧 write_plan 工具。

本工具仅作为 Phase 2 之前测试和外部调用的兼容入口。所有真实写入都委托给
``WriteImplementationPlanTool``，由状态机门禁进行结构化校验。模型不得直接调用；
新链路应使用 plan_tools 提供的 stage 提交工具。
"""

import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.write_plan")


class WritePlanInput(BaseModel):
    outline: str = Field(
        description="实现计划，需包含文件清单（路径、职责、依赖）、生成顺序、技术选型和关键逻辑"
    )


class WritePlanTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "write_plan"
    description: str = (
        "已弃用：保留为兼容入口；新链路请使用 plan_tools 提供的 write_implementation_plan。"
        "任何调用都会被路由到结构化 ImplementationPlan 写入，并要求已通过 design confirm。"
    )
    args_schema: Type[BaseModel] = WritePlanInput

    _state: object | None = None
    _delegate: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def set_delegate(self, delegate: object) -> None:
        self._delegate = delegate

    def _run(self, outline: str) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, outline: str) -> str:
        if not outline or not outline.strip():
            raise AgentRuntimeError(
                "计划内容不能为空",
                code=AgentErrorCode.TOOL_ARGS_ERROR,
            )
        if self._state is None:
            return "错误：未绑定 AgentLoopState"

        from app.agent_loop.state import AgentLoopState

        if not isinstance(self._state, AgentLoopState):
            return "错误：状态类型不匹配"

        # 兼容路径：把 outline 当作 summary 写入 implementation_outline 占位
        self._state.implementation_outline = {"text": outline, "legacy_compat": True}

        if self._delegate is not None:
            try:
                return await self._delegate(
                    self._state,
                    outline=outline,
                )
            except AgentRuntimeError as e:
                logger.warning("write_plan | delegate 拒绝, 记录为未确认: %s", e)
                # 不抛错以保证历史调用不破，但 state 不会进入 completed
                return (
                    "write_plan 已写入 outline；为保证已确认设计要求，"
                    "新链路请使用 write_implementation_plan。"
                )

        return "已记录 outline（兼容路径）；新链路请使用 write_implementation_plan。"
