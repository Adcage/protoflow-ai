
from app.agent_loop.graph import route_after_plan_step
from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import PlanStateV2, WorkflowState, WorkflowStateEnvelope


def _make_state_with_plan_state(
    *,
    model_call_count: int = 0,
    plan_stage: str = "discover_direction",
    plan_soft_limit: int = 30,
    plan_hard_limit: int = 60,
    plan_just_finished: bool = False,
    status: str = "running",
    mode: str = "plan",
    iteration: int = 0,
    max_iterations: int = 50,
) -> AgentLoopState:
    state = AgentLoopState(
        mode=mode,
        status=status,
        iteration=iteration,
        max_iterations=max_iterations,
        plan_just_finished=plan_just_finished,
    )
    plan_state = PlanStateV2(
        model_call_count=model_call_count,
        plan_stage=plan_stage,
        plan_soft_limit=plan_soft_limit,
        plan_hard_limit=plan_hard_limit,
        plan_just_finished=plan_just_finished,
    )
    envelope = WorkflowStateEnvelope(
        workflow=WorkflowState(
            current_mode=mode if mode != "finish" else "finished",
            plan=plan_state,
        )
    )
    state._state_envelope = envelope
    return state


class TestPlanIteration15DoesNotRouteWhenStageIncomplete:
    """Input 15th iteration with incomplete Plan; expect continues Plan (not routed to Route)."""

    def test_15_model_calls_incomplete_stage_continues_plan(self):
        state = _make_state_with_plan_state(
            model_call_count=15,
            plan_stage="select_skill",
        )
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_15_old_plan_iterations_incomplete_stage_continues_plan(self):
        state = _make_state_with_plan_state(
            model_call_count=15,
            plan_stage="propose_design",
        )
        state.plan_iterations = 15
        state.max_plan_iterations = 15
        result = route_after_plan_step(state)
        assert result == "plan_step"


class TestPlanSoftLimitDoesNotCompleteOrRoute:
    """Input 30th model call with missing design confirmation; expect still not completed and produces self-check signal."""

    def test_soft_limit_no_design_confirmation_stays_plan(self):
        state = _make_state_with_plan_state(
            model_call_count=30,
            plan_stage="confirm_design",
            plan_soft_limit=30,
            plan_hard_limit=60,
        )
        assert state._state_envelope.workflow.plan.reached_soft_limit()
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_soft_limit_plan_not_just_finished(self):
        state = _make_state_with_plan_state(
            model_call_count=30,
            plan_stage="write_implementation_plan",
            plan_soft_limit=30,
            plan_hard_limit=60,
            plan_just_finished=False,
        )
        assert not state.plan_just_finished
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_soft_limit_with_completed_stage_routes_via_just_finished(self):
        state = _make_state_with_plan_state(
            model_call_count=30,
            plan_stage="completed",
            plan_soft_limit=30,
            plan_hard_limit=60,
            plan_just_finished=True,
        )
        result = route_after_plan_step(state)
        assert result == "implement_step"


class TestPlanHardLimitBlocksWithoutImplement:
    """Input 60th model call with missing gate conditions; expect blocked, cannot Route to Implement."""

    def test_hard_limit_sets_failed_status_routes_to_finish(self):
        state = _make_state_with_plan_state(
            model_call_count=60,
            plan_stage="blocked",
            plan_hard_limit=60,
            status="failed",
        )
        result = route_after_plan_step(state)
        assert result == "finish"

    def test_hard_limit_blocks_even_with_high_plan_iterations(self):
        state = _make_state_with_plan_state(
            model_call_count=60,
            plan_stage="blocked",
            plan_hard_limit=60,
            status="failed",
        )
        state.plan_iterations = 100
        result = route_after_plan_step(state)
        assert result == "finish"

    def test_hard_limit_cannot_route_to_implement(self):
        state = _make_state_with_plan_state(
            model_call_count=60,
            plan_stage="blocked",
            plan_hard_limit=60,
            status="failed",
        )
        result = route_after_plan_step(state)
        assert result != "route_step"
        assert result != "implement_step"

    def test_reached_hard_limit_method_true(self):
        plan_state = PlanStateV2(
            model_call_count=60,
            plan_hard_limit=60,
        )
        assert plan_state.reached_hard_limit()


class TestPlanResumePreservesModelCallCount:
    """Input paused then resumed; expect count continues (not reset)."""

    def test_resume_preserves_model_call_count(self):
        plan_state = PlanStateV2(
            model_call_count=25,
            plan_stage="confirm_design",
            plan_soft_limit=30,
            plan_hard_limit=60,
        )
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(plan=plan_state)
        )
        state = AgentLoopState(mode="plan", status="waiting_for_user")
        state._state_envelope = envelope

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored._state_envelope.workflow.plan.model_call_count == 25

    def test_resume_after_soft_limit_continues(self):
        state = _make_state_with_plan_state(
            model_call_count=31,
            plan_stage="write_implementation_plan",
            plan_soft_limit=30,
            plan_hard_limit=60,
        )
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored._state_envelope.workflow.plan.model_call_count == 31
        assert restored._state_envelope.workflow.plan.reached_soft_limit()

    def test_resume_model_call_count_not_reset_to_zero(self):
        plan_state = PlanStateV2(
            model_call_count=45,
            plan_stage="confirm_design",
        )
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(plan=plan_state)
        )
        state = AgentLoopState(mode="plan", status="running")
        state._state_envelope = envelope

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored._state_envelope.workflow.plan.model_call_count == 45


class TestPlanCompletionRoutesOnce:
    """Input legitimate complete plan; expect enters Implement directly (Phase 4 fixed transition)."""

    def test_completed_plan_routes_to_implement_step(self):
        state = _make_state_with_plan_state(
            model_call_count=10,
            plan_stage="completed",
            plan_just_finished=True,
        )
        result = route_after_plan_step(state)
        assert result == "implement_step"

    def test_not_finished_plan_stays_in_plan(self):
        state = _make_state_with_plan_state(
            model_call_count=10,
            plan_stage="write_implementation_plan",
            plan_just_finished=False,
        )
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_plan_just_finished_false_does_not_route(self):
        state = _make_state_with_plan_state(
            model_call_count=5,
            plan_stage="select_skill",
            plan_just_finished=False,
        )
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_only_just_finished_triggers_implement(self):
        state1 = _make_state_with_plan_state(
            model_call_count=10,
            plan_stage="completed",
            plan_just_finished=False,
        )
        assert route_after_plan_step(state1) == "plan_step"

        state2 = _make_state_with_plan_state(
            model_call_count=10,
            plan_stage="completed",
            plan_just_finished=True,
        )
        assert route_after_plan_step(state2) == "implement_step"
