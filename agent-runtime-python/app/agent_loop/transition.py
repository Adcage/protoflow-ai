from typing import Any, Literal

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

WorkflowTransition = Literal[
    "plan_completed",
    "implement_completed",
    "validate_passed",
    "validate_failed",
    "implement_replan_requested",
    "route_decision",
]

_ALLOWED_TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("plan", "implement"): {"plan_completed", "route_decision"},
    ("implement", "validate"): {"implement_completed"},
    ("implement", "route"): {"implement_replan_requested"},
    ("validate", "finished"): {"validate_passed"},
    ("validate", "route"): {"validate_failed"},
    ("plan", "plan"): {"route_decision"},
    ("route", "plan"): {"route_decision"},
    ("route", "implement"): {"route_decision"},
    ("route", "finished"): {"route_decision"},
    # 安全兜底：Route 节点内部 _get_current_mode 可能受 checkpoint/restore
    # 影响返回旧 mode，这些路径在实际运行时不应发生，但作为故障容错必须存在
    ("implement", "plan"): {"route_decision"},
    ("validate", "plan"): {"route_decision"},
    ("validate", "implement"): {"route_decision"},
}


def apply_workflow_transition(
    state: Any,
    source: str,
    target: str,
    reason_code: str,
    evidence_refs: list[str] | None = None,
    route_decision: dict | None = None,
) -> None:
    current_mode = _get_current_mode(state)
    if current_mode != source:
        raise AgentRuntimeError(
            f"Transition source={source} 不匹配当前 mode={current_mode}",
            code=AgentErrorCode.STATE_ERROR,
        )

    key = (source, target)
    allowed_codes = _ALLOWED_TRANSITIONS.get(key)
    if allowed_codes is None or reason_code not in allowed_codes:
        raise AgentRuntimeError(
            f"不允许的流转: {source}\u2192{target} reason={reason_code}",
            code=AgentErrorCode.STATE_ERROR,
        )

    _write_mode(state, target)
    _increment_revision(state)
    _increment_mode_switches(state)
    _cleanup_phase_flags(state)
    _write_route_decision(state, target, reason_code, route_decision)


def _get_current_mode(state: Any) -> str:
    envelope = getattr(state, "_state_envelope", None)
    if envelope is not None:
        return envelope.workflow.current_mode
    legacy = getattr(state, "mode", "plan")
    if legacy == "finish":
        return "finished"
    return legacy


def _write_mode(state: Any, target: str) -> None:
    mode_map = {"finished": "finish", "route": "plan"}
    legacy_mode = mode_map.get(target, target)
    state.mode = legacy_mode

    envelope = getattr(state, "_state_envelope", None)
    if envelope is not None:
        envelope.workflow.current_mode = target


def _increment_revision(state: Any) -> None:
    envelope = getattr(state, "_state_envelope", None)
    if envelope is not None:
        envelope.workflow.next_revision()


def _increment_mode_switches(state: Any) -> None:
    state.mode_switches = getattr(state, "mode_switches", 0) + 1
    envelope = getattr(state, "_state_envelope", None)
    if envelope is not None:
        envelope.workflow.mode_switches = state.mode_switches


def _cleanup_phase_flags(state: Any) -> None:
    state.implement_replan_requested = False
    state.implement_replan_reason = ""
    state.route_decided = True


def _write_route_decision(
    state: Any, target: str, reason_code: str, route_decision: dict | None
) -> None:
    if route_decision is not None:
        state.route_decision = route_decision
    else:
        state.route_decision = {
            "mode": target if target != "finished" else "finish",
            "reason": reason_code,
            "target": target,
            "reason_code": reason_code,
        }
