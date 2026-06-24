import logging
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.agent_loop.transition import apply_workflow_transition, _get_current_mode
from app.agent_loop.transition_guard import (
    RouteDecision,
)

logger = logging.getLogger("app.agent_loop.tools.decide_route")

RouteTargetLegacy = Literal["plan", "implement", "validate", "finish"]

_TARGET_TO_LEGACY: dict[str, str] = {
    "plan": "plan",
    "implement": "implement",
    "validate": "validate",
    "finished": "finish",
    "wait_user": "finish",
    "blocked": "finish",
}

_SOURCE_LEGACY_TO_V2: dict[str, str] = {
    "initial": "user",
    "plan": "plan",
    "implement": "implement",
    "validate": "validate",
}


def _resolve_route_source(state) -> str:
    if getattr(state, "plan_just_finished", False):
        return "plan"
    if getattr(state, "implement_just_finished", False):
        return "implement"
    if getattr(state, "validate_just_finished", False):
        return "validate"
    return "initial"


def apply_route_decision(
    state,
    *,
    source: str,
    mode: RouteTargetLegacy,
    code_gen_type: str,
    reason: str,
    route_decision: RouteDecision | None = None,
    reason_code: str | None = None,
) -> None:
    target = mode if mode != "finish" else "finished"

    if route_decision is not None:
        route_decision_dict = {
            "mode": mode,
            "code_gen_type": code_gen_type,
            "reason": reason,
            "target": route_decision.target,
            "reason_code": route_decision.reason_code,
            "rationale": route_decision.rationale,
            "evidence_refs": route_decision.evidence_refs,
            "active_issue_ids": route_decision.active_issue_ids,
        }
    elif reason_code is not None:
        route_decision_dict = {
            "mode": mode,
            "code_gen_type": code_gen_type,
            "reason": reason,
            "target": target,
            "reason_code": reason_code,
            "rationale": reason,
            "evidence_refs": [],
            "active_issue_ids": [],
        }
    else:
        route_decision_dict = {
            "mode": mode,
            "code_gen_type": code_gen_type,
            "reason": reason,
        }

    if mode == "implement" and getattr(state, "mode", None) != "implement":
        state.implement_phase_files = []

    transition_source = _get_current_mode(state)
    logger.debug(
        "apply_route_decision | source=%s transition_source=%s target=%s reason=%s",
        source, transition_source, target, reason,
    )

    apply_workflow_transition(
        state,
        source=transition_source,
        target=target,
        reason_code="route_decision",
        route_decision=route_decision_dict,
    )

    if code_gen_type:
        state.recommended_code_gen_type = code_gen_type


_LEGACY_MODE_TO_REASON_CODE: dict[tuple[str, str], str] = {
    ("initial", "plan"): "new_app",
    ("initial", "implement"): "low_risk_modify",
    ("plan", "plan"): "plan_blocked",
    ("plan", "implement"): "plan_completed",
    ("implement", "plan"): "implement_needs_plan",
    ("implement", "validate"): "implement_completed",
    ("implement", "finish"): "validate_passed",
    ("validate", "plan"): "validate_needs_plan",
    ("validate", "implement"): "validate_has_repair_issues",
    ("validate", "finish"): "validate_passed",
}


def apply_v2_route_decision(state, decision: RouteDecision, code_gen_type: str = "") -> None:
    source = _resolve_route_source(state)
    legacy_target = _TARGET_TO_LEGACY.get(decision.target, "plan")
    apply_route_decision(
        state,
        source=source,
        mode=legacy_target,
        code_gen_type=code_gen_type,
        reason=decision.rationale or decision.reason_code,
        route_decision=decision,
    )
    if decision.target == "wait_user":
        state.status = "waiting_for_user"
    elif decision.target == "blocked":
        state.status = "failed"
        if not state.final_summary:
            state.final_summary = decision.rationale or "路由决策进入 blocked 状态"
    if decision.implement_run_kind:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            envelope.workflow.execution.execution_run_kind = decision.implement_run_kind

    if decision.generation_mode:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            current = getattr(envelope.workflow, "generation_mode", None)
            if current is None or current == "unresolved":
                envelope.workflow.generation_mode = decision.generation_mode

    if decision.direct_implementation_brief:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            from app.agent_loop.execution_contract import DirectImplementationBrief, from_direct_brief

            brief_data = decision.direct_implementation_brief
            brief = DirectImplementationBrief(
                generation_mode=brief_data.get("generation_mode", "application"),
                goal=brief_data["goal"],
                allowed_files=brief_data.get("allowed_files", []),
                acceptance_criteria=brief_data.get("acceptance_criteria", []),
                verification_requirements=brief_data.get("verification_requirements", []),
            )
            artifact_format = brief_data.get("expected_artifact_format", "web_single_file")
            contract = from_direct_brief(brief, expected_artifact_format=artifact_format)
            envelope.workflow.execution.execution_contract = contract.model_dump()


class DecideRouteInput(BaseModel):
    mode: Literal["plan", "implement", "validate", "finish"] = Field(
        description="路由目标模式：plan(需规划)、implement(直接实现)、validate(需校验)、finish(直接完成)"
    )
    generation_mode: Literal["", "application"] = Field(
        default="",
        description="生成模式，前端已指定时沿用；未指定且可判断时填写；无法判断时留空由 Plan 澄清",
    )
    reason: str = Field(
        default="",
        description="路由理由简述",
    )


class DecideRouteTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "decide_route"
    description: str = "判断请求应进入哪种模式后调用此工具输出决策。必须调用。"
    args_schema: type[BaseModel] = DecideRouteInput

    _state: object | None = None

    def set_state(self, state) -> None:
        self._state = state

    def _run(self, **kwargs) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        mode: str = "plan",
        generation_mode: str = "",
        reason: str = "",
    ) -> str:
        if self._state is not None:
            source = _resolve_route_source(self._state)
            reason_code = _LEGACY_MODE_TO_REASON_CODE.get((source, mode), "")
            apply_route_decision(
                self._state,
                source=source,
                mode=mode,
                code_gen_type="",
                reason=reason,
                reason_code=reason_code,
            )
            if generation_mode:
                envelope = getattr(self._state, "_state_envelope", None)
                if envelope is not None:
                    current = getattr(envelope.workflow, "generation_mode", None)
                    if current is None or current == "unresolved":
                        envelope.workflow.generation_mode = generation_mode
        type_info = f" 生成模式：{generation_mode}" if generation_mode else ""
        return f"路由决策已记录：进入 {mode} 模式。{type_info}"
