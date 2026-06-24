from __future__ import annotations

import logging
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.confirm_generation_mode")


class ConfirmGenerationModeInput(BaseModel):
    generation_mode: str = Field(description="确认的生成模式，当前仅支持 application")
    rationale: str = Field(default="", description="选择此模式的理由")


class ConfirmGenerationModeTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "confirm_generation_mode"
    description: str = (
        "在 generationMode 为 unresolved 时，Plan 通过此工具写入已确认的生成模式。"
        "确认前禁止编写正式实施计划或写业务文件。"
    )
    args_schema: Type[BaseModel] = ConfirmGenerationModeInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        generation_mode: str,
        rationale: str = "",
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )

        if not generation_mode.strip():
            raise AgentRuntimeError(
                "generation_mode 必填",
                code=AgentErrorCode.STATE_ERROR,
            )

        mode = generation_mode.strip()

        envelope = getattr(self._state, "_state_envelope", None)
        if envelope is not None:
            current = getattr(envelope.workflow, "generation_mode", None)
            if current is not None and current != "unresolved":
                raise AgentRuntimeError(
                    f"generationMode 已确定为 {current}，不得重复确认",
                    code=AgentErrorCode.STATE_ERROR,
                )
            envelope.workflow.generation_mode = mode
            envelope.next_revision()
        else:
            setattr(self._state, "generation_mode", mode)

        logger.info(
            "confirm_generation_mode | mode=%s rationale=%s",
            mode,
            rationale[:120],
        )
        return f"已确认生成模式为 {mode}，可继续编写实施计划。"
