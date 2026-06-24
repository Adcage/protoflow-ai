from typing import Literal

from pydantic import BaseModel, Field

RouteTarget = Literal[
    "plan", "implement", "validate", "finished", "wait_user", "blocked"
]
RouteSource = Literal["user", "plan", "implement", "validate"]
RouteReasonCode = Literal[
    "new_app",
    "complex_change",
    "design_change",
    "low_risk_modify",
    "plan_completed",
    "plan_blocked",
    "implement_completed",
    "implement_blocked",
    "implement_needs_plan",
    "validate_passed",
    "validate_has_repair_issues",
    "validate_needs_plan",
    "cycle_detected",
    "stagnation_detected",
    "insufficient_info",
]


class RouteContext(BaseModel):
    source_mode: RouteSource
    state_revision: int
    plan_has_confirmed_design: bool = False
    plan_has_implementation_plan: bool = False
    plan_has_unresolved: bool = False
    execution_has_pending_tasks: bool = False
    execution_completion_passed: bool = False
    validation_has_open_issues: bool = False
    validation_has_repair_issues: bool = False
    validation_has_return_plan_issues: bool = False
    validation_passed: bool = False
    has_pending_questions: bool = False
    progress_stagnation: bool = False
    progress_cycle: bool = False


class RouteDecision(BaseModel):
    target: RouteTarget
    reason_code: RouteReasonCode
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    implement_run_kind: str | None = None
    active_task_ids: list[str] = Field(default_factory=list)
    active_issue_ids: list[str] = Field(default_factory=list)
    generation_mode: str | None = None
    candidate_generation_modes: list[str] = Field(default_factory=list)
    direct_implementation_brief: dict | None = None


class GuardRejection(BaseModel):
    attempted_target: RouteTarget
    failed_rules: list[str]
    missing_evidence: list[str]
    safe_targets: list[RouteTarget]


ALLOWED_TRANSITIONS: dict[RouteSource, dict[RouteTarget, list[str]]] = {
    "user": {
        "plan": ["new_app", "complex_change", "design_change"],
        "implement": ["low_risk_modify"],
        "wait_user": ["insufficient_info"],
        "blocked": ["insufficient_info"],
    },
    "plan": {
        "wait_user": ["plan_blocked"],
        "implement": ["plan_completed"],
        "plan": ["plan_blocked"],
        "blocked": ["plan_blocked"],
    },
    "implement": {
        "implement": ["implement_blocked"],
        "validate": ["implement_completed"],
        "plan": ["implement_needs_plan"],
        "blocked": ["implement_blocked"],
    },
    "validate": {
        "finished": ["validate_passed"],
        "implement": ["validate_has_repair_issues"],
        "plan": ["validate_needs_plan"],
        "wait_user": ["validate_needs_plan"],
        "blocked": ["validate_has_repair_issues"],
    },
}


class TransitionGuard:
    def evaluate(
        self, context: RouteContext, decision: RouteDecision
    ) -> GuardRejection | None:
        source = context.source_mode
        target = decision.target
        reason_code = decision.reason_code

        source_transitions = ALLOWED_TRANSITIONS.get(source, {})
        allowed_reasons = source_transitions.get(target)
        if allowed_reasons is None:
            return GuardRejection(
                attempted_target=target,
                failed_rules=[f"transition {source}→{target} not allowed"],
                missing_evidence=[],
                safe_targets=list(source_transitions.keys()),
            )

        if reason_code not in allowed_reasons:
            return GuardRejection(
                attempted_target=target,
                failed_rules=[
                    f"reason_code '{reason_code}' not allowed for {source}→{target}"
                ],
                missing_evidence=[],
                safe_targets=list(source_transitions.keys()),
            )

        failed_rules: list[str] = []
        missing_evidence: list[str] = []

        if target == "implement" and source == "plan":
            if not context.plan_has_confirmed_design:
                failed_rules.append("design_not_confirmed")
                missing_evidence.append("DesignSpecification.confirmed=true")
            if not context.plan_has_implementation_plan:
                failed_rules.append("no_implementation_plan")
                missing_evidence.append("ImplementationPlan present")
            if context.plan_has_unresolved:
                failed_rules.append("unresolved_questions")
                missing_evidence.append("no unresolved_questions")

        if target == "implement" and source == "validate":
            if not context.validation_has_repair_issues:
                failed_rules.append("no_repair_issues")
                missing_evidence.append(
                    "ValidationIssue with disposition=implement_repair"
                )
            if not decision.active_issue_ids:
                failed_rules.append("missing_issue_ids")
                missing_evidence.append("active_issue_ids")

        if target == "finished" and source == "validate":
            if not context.validation_passed:
                failed_rules.append("validation_not_passed")
                missing_evidence.append("required checks passed, no blocking issues")

        if target == "implement" and source == "user":
            if context.plan_has_unresolved:
                failed_rules.append("has_unresolved_questions")
            if not decision.evidence_refs:
                failed_rules.append("no_evidence")
                missing_evidence.append("evidence_refs for low-risk determination")

        if context.progress_cycle and target not in ("blocked", "wait_user"):
            failed_rules.append("cycle_detected")
            missing_evidence.append("cycle resolution: must route to blocked or wait_user")

        if context.progress_stagnation and target not in (
            "blocked",
            "wait_user",
            "plan",
        ):
            failed_rules.append("stagnation_detected")
            missing_evidence.append(
                "stagnation resolution: must route to blocked/wait_user/plan"
            )

        if failed_rules:
            return GuardRejection(
                attempted_target=target,
                failed_rules=failed_rules,
                missing_evidence=missing_evidence,
                safe_targets=list(source_transitions.keys()),
            )

        return None
