import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("app.agent_loop.tools.ask_user")


class AskUserInput(BaseModel):
    question: str = Field(description="向用户提出的问题")
    input_type: str = Field(
        default="single_select", description="输入类型: single_select, multi_select"
    )
    options: list[str] = Field(
        default_factory=list, description="可选选项列表（single_select/multi_select 时使用）"
    )


class AskUserTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "ask_user"
    description: str = "向用户发起选择式提问（单选或多选）。必须提供 options 选项列表。用户选择后系统会在下一轮请求中通过对话历史传入。"
    args_schema: Type[BaseModel] = AskUserInput

    _state: object | None = None
    _event_bus: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def set_event_bus(self, event_bus: object) -> None:
        self._event_bus = event_bus

    def _run(
        self, question: str, input_type: str = "single_select", options: list[str] | None = None
    ) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self, question: str, input_type: str = "single_select", options: list[str] | None = None
    ) -> str:
        # 单选/多选必须提供选项
        if input_type in ("single_select", "multi_select"):
            if not options:
                return (
                    "错误：input_type 为 single_select 或 multi_select 时必须提供 options 选项列表。"
                    "请重新调用并提供至少 3 个具体选项。"
                )

        if self._state is not None:
            q = {
                "id": f"q{len(getattr(self._state, 'clarification_questions', [])) + 1}",
                "question": question,
                "inputType": input_type,
                "required": True,
                "options": [
                    {"value": o, "label": o, "recommended": False} for o in (options or [])
                ],
            }
            state = self._state
            if hasattr(state, "clarification_questions"):
                state.clarification_questions.append(q)
            if hasattr(state, "status"):
                state.status = "waiting_for_user"

        if self._event_bus is not None:
            from app.runtime.events import RuntimeEvent, RuntimeEventType

            await self._event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.CLARIFICATION_REQUIRED,
                    {
                        "questions": [
                            {
                                "id": "q1",
                                "question": question,
                                "inputType": input_type,
                                "required": True,
                                "options": [
                                    {"value": o, "label": o, "recommended": False}
                                    for o in (options or [])
                                ],
                            }
                        ],
                    },
                )
            )

        logger.info(
            "ask_user | question=%s input_type=%s options=%d",
            question,
            input_type,
            len(options or []),
        )
        return f"已向用户提问：{question}\n请等待用户回答后再继续。"
