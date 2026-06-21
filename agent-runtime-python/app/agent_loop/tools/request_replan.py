import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.request_replan")


class RequestReplanInput(BaseModel):
    reason: str = Field(
        min_length=1,
        description="无法继续实现的具体原因，以及实施计划缺失的关键内容",
    )


class RequestReplanTool(BaseTool):
    """由 Implement 提交结构化重新规划请求，不直接修改运行模式。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "request_replan"
    description: str = "实施计划存在关键缺口、无法安全继续实现时，提交重新规划请求和具体原因。"
    args_schema: Type[BaseModel] = RequestReplanInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, reason: str) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, reason: str) -> str:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise AgentRuntimeError(
                "重新规划原因不能为空",
                code=AgentErrorCode.TOOL_ARGS_ERROR,
            )

        if self._state is None:
            raise AgentRuntimeError(
                "AgentLoopState 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        state = self._state
        if getattr(state, "mode", None) != "implement":
            raise AgentRuntimeError(
                "只有 implement 模式可以请求重新规划",
                code=AgentErrorCode.TOOL_CALL_FAILED,
            )

        state.implement_replan_requested = True
        state.implement_replan_reason = normalized_reason
        state.implement_just_finished = True
        state.validate_just_finished = False
        state.status = "running"
        logger.info("request_replan | reason=%s", normalized_reason)
        return f"已提交重新规划请求：{normalized_reason}"
