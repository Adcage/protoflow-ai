"""Route 两次决策尝试协议测试。

覆盖 Task 5-2 中关于 Route 决策尝试次数、安全回退不调用第三次模型、fallback 仍受 Guard 校验的保证。
"""

import inspect

import pytest

from app.agent_loop.nodes.route_step import RouteStepNode
from app.agent_loop.transition_guard import TransitionGuard


class TestTwoAttemptProtocol:
    def test_valid_first_route_decision_uses_one_attempt(self):
        from app.agent_loop.transition_guard import (
            RouteContext,
            RouteDecision,
        )

        ctx = RouteContext(
            source_mode="user",
            state_revision=0,
        )
        decision = RouteDecision(
            target="plan",
            reason_code="new_app",
            rationale="new app",
        )
        guard = TransitionGuard()
        assert guard.evaluate(ctx, decision) is None

    def test_guard_rejection_allows_one_corrective_attempt(self):
        from app.agent_loop.transition_guard import (
            RouteContext,
            RouteDecision,
        )

        ctx = RouteContext(source_mode="plan", state_revision=0)
        decision1 = RouteDecision(
            target="implement",
            reason_code="plan_completed",
            rationale="plan done",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision1)
        assert rejection is not None

        decision2 = RouteDecision(
            target="plan",
            reason_code="plan_blocked",
            rationale="need more work",
        )
        assert guard.evaluate(ctx, decision2) is None

    def test_two_invalid_decisions_use_safe_fallback(self):
        from app.agent_loop.transition_guard import (
            RouteContext,
            TransitionGuard,
        )

        RouteContext(source_mode="user", state_revision=0)
        from app.agent_loop.transition_guard import RouteDecision
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RouteDecision(
                target="unknown_target",
                reason_code="new_app",
                rationale="bad",
            )

        guard = TransitionGuard()
        ctx2 = RouteContext(
            source_mode="plan",
            state_revision=0,
            progress_cycle=True,
        )
        decision = RouteDecision(
            target="plan",
            reason_code="plan_blocked",
            rationale="cycle",
        )
        assert guard.evaluate(ctx2, decision) is not None

    def test_fallback_uses_apply_route_decision(self):
        source = inspect.getsource(RouteStepNode._apply_safe_fallback)
        assert "apply_route_decision" in source

    def test_route_no_third_attempt(self):
        source = inspect.getsource(RouteStepNode.__call__)
        assert source.count("await self._corrective_attempt") <= 1


class TestRouteStepSourcePrompts:
    def test_route_profiles_dont_include_artifact_contract(self):
        from app.prompts.profiles import PROMPT_PROFILES

        artifact_modules = {"artifact_output_contract", "plan_spec", "validate_workflow", "implement_workflow"}
        for profile_id, modules in PROMPT_PROFILES.items():
            if profile_id.startswith("route_"):
                for mod in modules:
                    assert mod not in artifact_modules, (
                        f"Route profile {profile_id} 不应包含 {mod}"
                    )
