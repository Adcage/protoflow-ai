"""Phase 3 Plan 状态机与结构化设计产物测试。"""

import json

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_codec import decode_loop_state
from app.agent_loop.state_v2 import (
    CapabilityBundleRef,
    CapabilityRef,
    ConfirmedChoice,
    ConfirmedValue,
    DesignSpecification,
    ImplementationPlan,
    ImplementationTask,
    PlanStateV2,
    RequirementBrief,
    WorkflowStateEnvelope,
)
from app.core.exceptions import AgentRuntimeError


def _envelope(state: AgentLoopState) -> WorkflowStateEnvelope:
    env = getattr(state, "_state_envelope", None)
    if env is None:
        env = state._to_envelope()
        state._state_envelope = env
    return env


class TestPlanStageTransitions:
    def test_initial_stage_is_discover_direction(self):
        state = AgentLoopState()
        env = _envelope(state)
        assert env.workflow.plan.plan_stage == "discover_direction"

    def test_stage_advance_allowed(self):
        plan = PlanStateV2(plan_stage="discover_direction")
        plan.advance_stage("discover_scope")
        assert plan.plan_stage == "discover_scope"
        assert plan.previous_plan_stage == "discover_direction"

    def test_stage_advance_rejects_illegal(self):
        plan = PlanStateV2(plan_stage="discover_direction")
        with pytest.raises(AgentRuntimeError):
            plan.advance_stage("write_implementation_plan")

    def test_advance_to_completed_only_via_write(self):
        plan = PlanStateV2(plan_stage="discover_direction")
        plan.advance_stage("discover_scope")
        plan.advance_stage("inspect_existing_project")
        plan.advance_stage("select_skill")
        plan.advance_stage("propose_design")
        plan.advance_stage("confirm_design")
        plan.advance_stage("write_implementation_plan")
        plan.advance_stage("completed")
        assert plan.plan_stage == "completed"

    def test_blocked_to_blocked_allowed(self):
        plan = PlanStateV2(plan_stage="blocked")
        plan.advance_stage("blocked")
        assert plan.plan_stage == "blocked"


class TestPlanCallBudget:
    def test_soft_limit_30(self):
        plan = PlanStateV2(plan_soft_limit=30, plan_hard_limit=60)
        for _ in range(29):
            plan.increment_model_call()
        assert not plan.reached_soft_limit()
        plan.increment_model_call()
        assert plan.reached_soft_limit()

    def test_hard_limit_60(self):
        plan = PlanStateV2(plan_soft_limit=30, plan_hard_limit=60)
        for _ in range(60):
            plan.increment_model_call()
        assert plan.reached_hard_limit()
        assert plan.model_call_count == 60

    def test_budget_does_not_reset_across_resume(self):
        plan = PlanStateV2(plan_hard_limit=60)
        for _ in range(40):
            plan.increment_model_call()
        # Simulate resume by serializing/deserializing; counter must be preserved
        round_trip = PlanStateV2.model_validate(json.loads(json.dumps(plan.model_dump())))
        assert round_trip.model_call_count == 40


class TestPlanPartitionOwnership:
    def test_plan_cannot_write_execution(self):
        state = AgentLoopState()
        env = _envelope(state)
        env.workflow.current_mode = "plan"
        assert env.workflow.plan_writes_partition_violation("execution")
        assert env.workflow.plan_writes_partition_violation("validation")
        assert env.workflow.plan_writes_partition_violation("routing")
        assert not env.workflow.plan_writes_partition_violation("plan")
        assert not env.workflow.plan_writes_partition_violation("conversation")

    def test_implement_can_write_execution(self):
        state = AgentLoopState()
        env = _envelope(state)
        env.workflow.current_mode = "implement"
        assert not env.workflow.plan_writes_partition_violation("execution")
        # plan 模式未启用时 plan_writes_partition_violation 永远 False
        assert not env.workflow.plan_writes_partition_violation("plan")


class TestPlanStructuredDesignProducts:
    def test_requirement_brief_round_trip(self):
        brief = RequirementBrief(
            application_direction=ConfirmedValue(value="仪表盘", source="user", confirmed=True),
            target_users=ConfirmedValue(value="运营人员", source="user", confirmed=True),
            primary_scenarios=[ConfirmedValue(value="日活监控", source="user", confirmed=True)],
        )
        plan = PlanStateV2(requirement_brief=brief)
        round_trip = PlanStateV2.model_validate(plan.model_dump())
        assert round_trip.requirement_brief.application_direction.value == "仪表盘"
        assert round_trip.requirement_brief.primary_scenarios[0].value == "日活监控"

    def test_implementation_plan_requires_tasks(self):
        with pytest.raises(AgentRuntimeError):
            ImplementationPlan(
                plan_version=1,
                source_design_version=1,
                tasks=[],
            )

    def test_implementation_plan_requires_source_design_version(self):
        with pytest.raises(AgentRuntimeError):
            ImplementationPlan(
                plan_version=1,
                source_design_version=0,
                tasks=[ImplementationTask(task_id="t1", goal="g", allowed_files=["x"])],
            )

    def test_implementation_task_requires_allowed_files(self):
        with pytest.raises(AgentRuntimeError):
            ImplementationTask(task_id="t1", goal="g", allowed_files=[])

    def test_capability_ref_seed_disabled_enforced(self):
        with pytest.raises(AgentRuntimeError):
            CapabilityRef(
                capability_id="seed-1",
                kind="seed",
                source_path="/x",
                content_digest="d",
                selected_reason="r",
                selected_at_revision=1,
                enabled=True,
            )

    def test_capability_ref_skill_enabled(self):
        ref = CapabilityRef(
            capability_id="dashboard",
            kind="skill",
            source_path="/x",
            content_digest="abc",
            selected_reason="r",
            selected_at_revision=1,
            enabled=True,
        )
        assert ref.enabled is True

    def test_capability_ref_seed_disabled_ok(self):
        ref = CapabilityRef(
            capability_id="seed-1",
            kind="seed",
            source_path="/x",
            content_digest="d",
            selected_reason="r",
            selected_at_revision=1,
            enabled=False,
        )
        assert ref.enabled is False

    def test_design_specification_confirmed_flag(self):
        spec = DesignSpecification(
            visual_direction=ConfirmedChoice(description="v", source="user", confirmed=False),
            color_system=ConfirmedChoice(description="c", source="user", confirmed=False),
            typography=ConfirmedChoice(description="t", source="user", confirmed=False),
            component_language=ConfirmedChoice(description="cl", source="user", confirmed=False),
            interaction_model=ConfirmedChoice(description="i", source="user", confirmed=False),
            responsive_strategy=ConfirmedChoice(description="r", source="user", confirmed=False),
        )
        assert spec.confirmed is False

    def test_capability_bundle_all_refs(self):
        bundle = CapabilityBundleRef(
            skills=[
                CapabilityRef(
                    capability_id="s1",
                    kind="skill",
                    source_path="/x",
                    content_digest="d",
                    selected_reason="r",
                    selected_at_revision=1,
                )
            ]
        )
        assert len(bundle.all_refs()) == 1


class TestPlanSerialization:
    def test_plan_state_serializes_round_trip(self):
        state = AgentLoopState()
        env = _envelope(state)
        env.workflow.plan.plan_session_id = "plan_test"
        env.workflow.plan.model_call_count = 5
        env.workflow.plan.requirement_brief = RequirementBrief(
            application_direction=ConfirmedValue(value="X", source="user", confirmed=True),
            target_users=ConfirmedValue(value="Y", source="user", confirmed=True),
        )
        env.next_revision()
        state._state_envelope = env

        json_str = state.serialize()
        data = json.loads(json_str)
        plan = data["workflow"]["plan"]
        assert plan["plan_session_id"] == "plan_test"
        assert plan["model_call_count"] == 5
        assert plan["requirement_brief"]["application_direction"]["value"] == "X"
        assert plan["requirement_brief"]["target_users"]["value"] == "Y"

        restored = AgentLoopState.deserialize(json_str)
        r_env = _envelope(restored)
        assert r_env.workflow.plan.plan_session_id == "plan_test"
        assert r_env.workflow.plan.requirement_brief is not None
        assert r_env.workflow.plan.requirement_brief.application_direction.value == "X"

    def test_legacy_adapter_preserves_plan_session_id(self):
        legacy = {
            "mode": "plan",
            "status": "running",
            "iteration": 0,
            "plan_iterations": 3,
            "plan_session_id": "plan_legacy",
            "model_call_count": 3,
            "plan_stage": "select_skill",
        }
        env = decode_loop_state(legacy)
        assert env.workflow.plan.plan_session_id == "plan_legacy"
        assert env.workflow.plan.model_call_count == 3
        assert env.workflow.plan.plan_stage == "select_skill"


class TestPlanStageGuardRejected:
    def test_illegal_stage_transition_via_helper(self):
        from app.agent_loop.tools.plan_tools import (
            PlanStageGuardRejected,
            reject_plan_stage_violation,
        )

        with pytest.raises(PlanStageGuardRejected):
            reject_plan_stage_violation("nope")

    def test_advance_stage_raises_state_error(self):
        plan = PlanStateV2(plan_stage="completed")
        with pytest.raises(AgentRuntimeError):
            plan.advance_stage("discover_direction")
