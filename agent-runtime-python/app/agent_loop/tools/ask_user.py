"""Phase 3 ask_user 工具。

问题 ID 与 questionSetId 由编排层/工具统一生成；状态和事件使用同一值。
问句协议使用稳定 JSON 结构，事件映射层将 CLARIFICATION_REQUIRED 折叠为
TOOL_REQUEST 事件，避免重复气泡。
"""

import logging
import uuid
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("app.agent_loop.tools.ask_user")

PROTOCOL_VERSION = 1


class AskUserInput(BaseModel):
    stage: str = Field(
        default="discover_scope",
        description="当前 Plan 阶段标签，会写入 questionSetId 元数据",
    )
    questions: list[dict] = Field(
        default_factory=list,
        description=(
            "结构化问题列表：每项 {id, prompt, inputType, required, options}"
        ),
    )


class AskUserTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "ask_user"
    description: str = (
        "向用户发起结构化提问，触发流程暂停。每个问题必须由模型给出 prompt/inputType/options，"
        "问题 ID 与 questionSetId 由工具和编排层统一生成。"
    )
    args_schema: Type[BaseModel] = AskUserInput

    _state: object | None = None
    _event_bus: object | None = None
    _question_set_id_factory: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def set_event_bus(self, event_bus: object) -> None:
        self._event_bus = event_bus

    def set_question_set_id_factory(self, factory: object) -> None:
        self._question_set_id_factory = factory

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        stage: str = "discover_scope",
        questions: list[dict] | None = None,
        # 兼容旧调用签名：question / input_type / options
        question: str | None = None,
        input_type: str | None = None,
        options: list[Any] | None = None,
        **_legacy_kwargs: Any,
    ) -> str:
        from app.agent_loop.state import AgentLoopState

        # 兼容旧 test 与旧调用：把 (question, input_type, options) 翻译为新的 questions 结构
        if questions is None and question is not None:
            questions = [
                {
                    "id": "q1",
                    "prompt": question,
                    "inputType": input_type or "single_select",
                    "required": True,
                    "options": options or [],
                }
            ]
            # 旧路径 stage 默认是 plan
            if stage == "discover_scope" and not _legacy_kwargs:
                stage = "plan"

        if not questions:
            return "错误：questions 不能为空；至少要包含一个结构化问题"

        if self._state is None:
            return "错误：未绑定 AgentLoopState"

        # 归一化 inputType 到协议值 single_select / multi_select。
        # Phase 3 协议统一为选择式，text 已被前端通过"自定义回答"替代。
        # 模型可能传 single_choice / multi_choice / select / single / multi 等变体，
        # 一律按以下规则映射：含 multi 关键字 → multi_select；其他合法变体 → single_select。
        # text（无论是否带 options）直接拒绝，让模型重新调用。
        for q in questions:
            raw_input_type = q.get("inputType", "single_select")
            options = q.get("options") or []
            if not isinstance(raw_input_type, str):
                raw_input_type = ""
            val = raw_input_type.strip().lower()
            if val == "text":
                return (
                    f"错误：inputType={raw_input_type!r} 不被支持；"
                    "ask_user 统一为选择式，只接受 single_select / multi_select，"
                    "自由文本通过前端的\"自定义回答\"实现。"
                )
            if "multi" in val:
                input_type = "multi_select"
            elif val in ("single_select", "single", ""):
                input_type = "single_select"
            else:
                # single_choice / select / choice / 其它单选语义变体
                input_type = "single_select"
            q["inputType"] = input_type
            if not options:
                return (
                    f"错误：inputType={raw_input_type!r} 归一化为 {input_type!r}，"
                    "但未提供 options 选项列表；请重新调用并提供至少 2 个具体选项。"
                )

        # questionSetId 优先使用用户提供的 factory，否则生成 qs_<uuid>
        question_set_id = self._next_question_set_id(stage)

        # 问题 ID 统一由工具按 questions 列表顺序生成
        normalized_questions: list[dict] = []
        for index, q in enumerate(questions, start=1):
            qid = q.get("id") or f"q{index}"
            input_type = q.get("inputType", "single_select")
            options = q.get("options") or []
            prompt_text = q.get("prompt", "") or q.get("question", "")
            normalized_questions.append(
                {
                    "id": qid,
                    "prompt": prompt_text,
                    # 兼容旧字段名：旧调用方按 "question" 字段读取
                    "question": prompt_text,
                    "inputType": input_type,
                    "required": bool(q.get("required", True)),
                    "options": [
                        _normalize_option(opt) for opt in options
                    ],
                }
            )

        plan_state = None
        envelope = getattr(self._state, "_state_envelope", None)
        if envelope is not None:
            plan_state = envelope.workflow.plan

        # 检查是否已对同一 stage 提问过：避免重复提问（无论是否已回答）
        if stage:
            for q in getattr(self._state, "clarification_questions", []):
                if isinstance(q, dict) and q.get("stage") == stage:
                    logger.info(
                        "ask_user | stage=%s already asked, rejecting duplicate",
                        stage,
                    )
                    return (
                        f"关于 {stage} 的问题已经提问过，请等待用户回答"
                        "或根据已有对话内容继续推进。"
                    )

        # 记录到 state.clarification_questions
        record: dict[str, Any] = {
            "id": question_set_id,
            "questionSetId": question_set_id,
            "stage": stage,
            "protocolVersion": PROTOCOL_VERSION,
            "questions": normalized_questions,
            "answered": False,
        }
        # 旧 arguments 格式兼容：单问题时把首个问题提升为顶层字段
        if len(normalized_questions) == 1:
            first = normalized_questions[0]
            record["question"] = first.get("prompt", "")
            record["inputType"] = first.get("inputType", "single_select")
            record["options"] = first.get("options", [])
            record["required"] = first.get("required", True)
        if isinstance(self._state, AgentLoopState):
            self._state.clarification_questions.append(record)
            self._state.status = "waiting_for_user"
            if plan_state is not None:
                plan_state.is_waiting_for_user = True
                plan_state.pending_question_set_id = question_set_id

        if self._event_bus is not None:
            from app.runtime.events import RuntimeEvent, RuntimeEventType

            await self._event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.CLARIFICATION_REQUIRED,
                    {
                        "questionSetId": question_set_id,
                        "stage": stage,
                        "protocolVersion": PROTOCOL_VERSION,
                        "questions": normalized_questions,
                    },
                )
            )

        logger.info(
            "ask_user | questionSetId=%s stage=%s questions=%d",
            question_set_id,
            stage,
            len(normalized_questions),
        )
        return f"已向用户提问 questionSetId={question_set_id}（{len(normalized_questions)} 个问题），请等待用户回答。"

    def _next_question_set_id(self, stage: str) -> str:
        if self._question_set_id_factory is not None:
            return self._question_set_id_factory(stage)
        return f"qs_{stage}_{uuid.uuid4().hex[:10]}"


def _normalize_option(opt: Any) -> dict[str, Any]:
    if isinstance(opt, str):
        return {"id": opt, "label": opt, "description": "", "recommended": False}
    if isinstance(opt, dict):
        return {
            "id": str(opt.get("id") or opt.get("value") or opt.get("label", "")),
            "label": str(opt.get("label") or opt.get("id") or opt.get("value", "")),
            "description": str(opt.get("description", "")),
            "recommended": bool(opt.get("recommended", False)),
        }
    return {"id": str(opt), "label": str(opt), "description": "", "recommended": False}


__all__ = ["AskUserTool", "PROTOCOL_VERSION"]
