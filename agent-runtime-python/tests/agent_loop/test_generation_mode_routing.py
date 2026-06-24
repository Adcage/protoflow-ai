from __future__ import annotations

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.confirm_generation_mode import ConfirmGenerationModeTool
from app.agent_loop.tools.decide_route import apply_v2_route_decision
from app.agent_loop.transition_guard import RouteDecision
from app.core.exceptions import AgentRuntimeError
from app.generation_modes.registry import GenerationModeRegistry
from app.generation_modes.types import GenerationModeDefinition
from app.agent_loop.agents.application import ApplicationImplementAgent


def _make_state(generation_mode: str | None = None) -> AgentLoopState:
    state = AgentLoopState(mode="plan", status="running")
    envelope = state._to_envelope()
    if generation_mode is not None:
        envelope.workflow.generation_mode = generation_mode
    state._state_envelope = envelope
    return state


def _make_registry() -> GenerationModeRegistry:
    registry = GenerationModeRegistry()
    registry.register(GenerationModeDefinition(
        mode_id="application",
        plan_prompt_module_ids=("application_plan",),
        implement_agent_factory=ApplicationImplementAgent,
        validate_prompt_module_ids=("application_validate",),
        supported_artifact_formats=frozenset({"web_single_file", "web_multi_file", "vue_project"}),
    ))
    return registry


class TestExplicitGenerationModeCannotBeOverridden:
    def test_route_does_not_override_existing_generation_mode(self):
        state = _make_state(generation_mode="application")
        decision = RouteDecision(
            target="plan",
            reason_code="new_app",
            rationale="需要规划",
            generation_mode="unresolved",
        )
        apply_v2_route_decision(state, decision)
        envelope = state._state_envelope
        assert envelope.workflow.generation_mode == "application"


class TestMissingUnambiguousModeCanBeClassified:
    def test_route_sets_generation_mode_when_not_set(self):
        state = _make_state(generation_mode=None)
        decision = RouteDecision(
            target="plan",
            reason_code="new_app",
            rationale="新建应用",
            generation_mode="application",
        )
        apply_v2_route_decision(state, decision)
        envelope = state._state_envelope
        assert envelope.workflow.generation_mode == "application"


class TestAmbiguousModeRoutesToGenericPlan:
    def test_unresolved_generation_mode_stays_unresolved(self):
        state = _make_state(generation_mode="unresolved")
        assert state._state_envelope.workflow.generation_mode == "unresolved"


class TestGenericPlanCanAskAndResumeWithConfirmedMode:
    def test_confirm_generation_mode_tool_sets_mode(self):
        state = _make_state(generation_mode="unresolved")
        tool = ConfirmGenerationModeTool()
        tool.set_state(state)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            tool._arun(generation_mode="application", rationale="用户确认")
        )
        assert "application" in result
        assert state._state_envelope.workflow.generation_mode == "application"

    def test_confirm_generation_mode_rejects_already_confirmed(self):
        state = _make_state(generation_mode="application")
        tool = ConfirmGenerationModeTool()
        tool.set_state(state)

        import asyncio
        with pytest.raises(AgentRuntimeError, match="已确定"):
            asyncio.get_event_loop().run_until_complete(
                tool._arun(generation_mode="application")
            )


class TestDirectImplementRequiresCompleteBrief:
    def test_direct_implement_with_brief_creates_contract(self):
        state = _make_state(generation_mode=None)
        decision = RouteDecision(
            target="implement",
            reason_code="low_risk_modify",
            rationale="简单修改",
            generation_mode="application",
            direct_implementation_brief={
                "generation_mode": "application",
                "goal": "修改首页标题",
                "allowed_files": ["index.html"],
                "acceptance_criteria": ["标题已更新"],
                "verification_requirements": ["检查 index.html 标题"],
            },
        )
        apply_v2_route_decision(state, decision)
        envelope = state._state_envelope
        assert envelope.workflow.execution.execution_contract is not None
        contract = envelope.workflow.execution.execution_contract
        assert contract["generation_mode"] == "application"
        assert contract["source"] == "direct"

    def test_direct_implement_without_brief_no_contract(self):
        state = _make_state(generation_mode=None)
        decision = RouteDecision(
            target="implement",
            reason_code="low_risk_modify",
            rationale="简单修改",
            generation_mode="application",
        )
        apply_v2_route_decision(state, decision)
        envelope = state._state_envelope
        assert envelope.workflow.execution.execution_contract is None
