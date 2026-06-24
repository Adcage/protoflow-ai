"""Route 转移矩阵与 TransitionGuard 测试。"""


from app.agent_loop.transition_guard import (
    RouteContext,
    RouteDecision,
    TransitionGuard,
)


class TestUserSourceTransitions:
    def test_new_app_routes_to_plan(self):
        ctx = RouteContext(source_mode="user", state_revision=0)
        decision = RouteDecision(
            target="plan",
            reason_code="new_app",
            rationale="new app request",
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None

    def test_precise_one_file_bug_can_route_to_implement(self):
        ctx = RouteContext(source_mode="user", state_revision=0)
        decision = RouteDecision(
            target="implement",
            reason_code="low_risk_modify",
            rationale="single file bug fix",
            evidence_refs=["src/App.vue"],
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None

    def test_design_change_cannot_bypass_plan(self):
        ctx = RouteContext(source_mode="user", state_revision=0)
        decision = RouteDecision(
            target="implement",
            reason_code="low_risk_modify",
            rationale="change design system",
            evidence_refs=[],
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "no_evidence" in rejection.failed_rules


class TestPlanSourceTransitions:
    def test_plan_to_implement_requires_confirmed_design(self):
        ctx = RouteContext(
            source_mode="plan",
            state_revision=1,
            plan_has_confirmed_design=False,
            plan_has_implementation_plan=True,
        )
        decision = RouteDecision(
            target="implement",
            reason_code="plan_completed",
            rationale="plan done",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "design_not_confirmed" in rejection.failed_rules

    def test_plan_to_implement_requires_implementation_plan(self):
        ctx = RouteContext(
            source_mode="plan",
            state_revision=1,
            plan_has_confirmed_design=True,
            plan_has_implementation_plan=False,
        )
        decision = RouteDecision(
            target="implement",
            reason_code="plan_completed",
            rationale="plan done",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "no_implementation_plan" in rejection.failed_rules

    def test_plan_to_implement_with_unresolved_rejected(self):
        ctx = RouteContext(
            source_mode="plan",
            state_revision=1,
            plan_has_confirmed_design=True,
            plan_has_implementation_plan=True,
            plan_has_unresolved=True,
        )
        decision = RouteDecision(
            target="implement",
            reason_code="plan_completed",
            rationale="plan done",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "unresolved_questions" in rejection.failed_rules


class TestValidateSourceTransitions:
    def test_validate_passed_routes_finished(self):
        ctx = RouteContext(
            source_mode="validate",
            state_revision=1,
            validation_passed=True,
        )
        decision = RouteDecision(
            target="finished",
            reason_code="validate_passed",
            rationale="all checks passed",
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None

    def test_validate_open_repair_issues_routes_with_ids(self):
        ctx = RouteContext(
            source_mode="validate",
            state_revision=1,
            validation_has_repair_issues=True,
        )
        decision = RouteDecision(
            target="implement",
            reason_code="validate_has_repair_issues",
            rationale="rebuild after repair",
            active_issue_ids=["i1", "i2"],
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None

    def test_validate_repair_routes_without_issue_ids_rejected(self):
        ctx = RouteContext(
            source_mode="validate",
            state_revision=1,
            validation_has_repair_issues=True,
        )
        decision = RouteDecision(
            target="implement",
            reason_code="validate_has_repair_issues",
            rationale="rebuild after repair",
            active_issue_ids=[],
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "missing_issue_ids" in rejection.failed_rules

    def test_validate_not_passed_cannot_route_finished(self):
        ctx = RouteContext(
            source_mode="validate",
            state_revision=1,
            validation_passed=False,
        )
        decision = RouteDecision(
            target="finished",
            reason_code="validate_passed",
            rationale="claiming passed",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "validation_not_passed" in rejection.failed_rules


class TestUnknownTransitions:
    def test_unknown_transition_is_rejected(self):
        ctx = RouteContext(source_mode="plan", state_revision=1)
        decision = RouteDecision(
            target="validate",
            reason_code="validate_passed",
            rationale="invalid",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "not allowed" in rejection.failed_rules[0]


class TestProgressAndGuards:
    def test_cycle_detected_must_route_to_blocked_or_wait_user(self):
        ctx = RouteContext(source_mode="plan", state_revision=1, progress_cycle=True)
        decision = RouteDecision(
            target="plan",
            reason_code="plan_blocked",
            rationale="stuck",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "cycle_detected" in rejection.failed_rules

    def test_stagnation_allows_routing_to_plan(self):
        ctx = RouteContext(source_mode="plan", state_revision=1, progress_stagnation=True)
        decision = RouteDecision(
            target="plan",
            reason_code="plan_blocked",
            rationale="no progress",
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None
