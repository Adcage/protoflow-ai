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
        "将实现计划写入状态。必须先调用此工具写入计划，才能进入下一阶段。"
        "可多次调用更新计划。"
    )
    args_schema: Type[BaseModel] = WritePlanInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, outline: str) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, outline: str) -> str:
        if self._state is None:
            return "错误：未绑定 AgentLoopState"

        if not outline or not outline.strip():
            raise AgentRuntimeError(
                "计划内容不能为空",
                code=AgentErrorCode.TOOL_ARGS_ERROR,
            )

        state = self._state
        state.implementation_outline = {"text": outline}
        state.plan_just_finished = True
        logger.info("write_plan | outline length=%d", len(outline))

        return (
            "实现计划已记录。请停止当前阶段，编排层将决定下一步。"
        )
