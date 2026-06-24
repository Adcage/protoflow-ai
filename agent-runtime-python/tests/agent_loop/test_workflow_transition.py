import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import WorkflowState, WorkflowStateEnvelope
from app.agent_loop.transition import apply_workflow_transition
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


def _make_state_with_envelope(mode="plan", **kwargs):
    state = AgentLoopState(mode=mode, **kwargs)
    envelope = WorkflowStateEnvelope(
        workflow=WorkflowState(
            current_mode=mode if mode != "finish" else "finished",
            mode_switches=state.mode_switches,
        )
    )
    state._state_envelope = envelope
    return state


class TestPlanCompletedTransitionsDirectlyToImplement:
    def test_plan_completed_goes_to_implement(self):
        state = _make_state_with_envelope(mode="plan")
        apply_workflow_transition(state, source="plan", target="implement", reason_code="plan_completed")
        assert state.mode == "implement"
        assert state._state_envelope.workflow.current_mode == "implement"

    def test_plan_completed_preserves_just_finished_for_condition_edge(self):
        """plan_just_finished 不在 transition 中清除，留给 graph 条件边消费。"""
        state = _make_state_with_envelope(mode="plan")
        state.plan_just_finished = True
        apply_workflow_transition(state, source="plan", target="implement", reason_code="plan_completed")
        assert state.plan_just_finished is True

    def test_plan_completed_increments_revision_and_switches(self):
        state = _make_state_with_envelope(mode="plan")
        initial_switches = state.mode_switches
        initial_revision = state._state_envelope.workflow.revision
        apply_workflow_transition(state, source="plan", target="implement", reason_code="plan_completed")
        assert state.mode_switches == initial_switches + 1
        assert state._state_envelope.workflow.revision == initial_revision + 1


class TestImplementationCompletedTransitionsDirectlyToValidate:
    def test_implement_completed_goes_to_validate(self):
        state = _make_state_with_envelope(mode="implement")
        apply_workflow_transition(state, source="implement", target="validate", reason_code="implement_completed")
        assert state.mode == "validate"
        assert state._state_envelope.workflow.current_mode == "validate"

    def test_implement_completed_preserves_just_finished_for_condition_edge(self):
        """implement_just_finished 不在 transition 中清除，留给 graph 条件边消费。"""
        state = _make_state_with_envelope(mode="implement")
        state.implement_just_finished = True
        state.implement_replan_requested = False
        apply_workflow_transition(state, source="implement", target="validate", reason_code="implement_completed")
        assert state.implement_just_finished is True
        assert state.implement_replan_requested is False


class TestValidationPassedTransitionsDirectlyToFinish:
    def test_validate_passed_goes_to_finish(self):
        state = _make_state_with_envelope(mode="validate")
        apply_workflow_transition(state, source="validate", target="finished", reason_code="validate_passed")
        assert state.mode == "finish"
        assert state._state_envelope.workflow.current_mode == "finished"

    def test_validate_passed_preserves_just_finished_for_condition_edge(self):
        """validate_just_finished 不在 transition 中清除，留给 graph 条件边消费。"""
        state = _make_state_with_envelope(mode="validate")
        state.validate_just_finished = True
        apply_workflow_transition(state, source="validate", target="finished", reason_code="validate_passed")
        assert state.validate_just_finished is True


class TestValidationFailedTransitionsToRoute:
    def test_validate_failed_goes_to_route(self):
        state = _make_state_with_envelope(mode="validate")
        apply_workflow_transition(state, source="validate", target="route", reason_code="validate_failed")
        assert state.mode == "plan"
        assert state._state_envelope.workflow.current_mode == "route"

    def test_validate_failed_preserves_just_finished_for_condition_edge(self):
        """validate_just_finished 不在 transition 中清除，留给 graph 条件边消费。"""
        state = _make_state_with_envelope(mode="validate")
        state.validate_just_finished = True
        apply_workflow_transition(state, source="validate", target="route", reason_code="validate_failed")
        assert state.validate_just_finished is True


class TestImplementReplanTransitionsToRoute:
    def test_implement_replan_goes_to_route(self):
        state = _make_state_with_envelope(mode="implement")
        state.implement_replan_requested = True
        apply_workflow_transition(state, source="implement", target="route", reason_code="implement_replan_requested")
        assert state.mode == "plan"
        assert state._state_envelope.workflow.current_mode == "route"
        assert state.implement_replan_requested is False


class TestNonTransitionModuleCannotAssignMode:
    def test_direct_mode_assignment_not_via_transition(self):
        state = _make_state_with_envelope(mode="plan")
        state.mode = "implement"
        envelope_mode = state._state_envelope.workflow.current_mode
        assert envelope_mode == "plan"

    def test_disallowed_transition_raises(self):
        state = _make_state_with_envelope(mode="plan")
        with pytest.raises(AgentRuntimeError) as exc_info:
            apply_workflow_transition(state, source="plan", target="validate", reason_code="validate_passed")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_wrong_source_mode_raises(self):
        state = _make_state_with_envelope(mode="plan")
        with pytest.raises(AgentRuntimeError) as exc_info:
            apply_workflow_transition(state, source="implement", target="validate", reason_code="implement_completed")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_invalid_reason_code_raises(self):
        state = _make_state_with_envelope(mode="plan")
        with pytest.raises(AgentRuntimeError) as exc_info:
            apply_workflow_transition(state, source="plan", target="implement", reason_code="wrong_code")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR


class TestTransitionFailureIsAtomic:
    def test_failed_transition_does_not_change_mode(self):
        state = _make_state_with_envelope(mode="plan")
        original_mode = state.mode
        original_envelope_mode = state._state_envelope.workflow.current_mode
        with pytest.raises(AgentRuntimeError):
            apply_workflow_transition(state, source="implement", target="validate", reason_code="implement_completed")
        assert state.mode == original_mode
        assert state._state_envelope.workflow.current_mode == original_envelope_mode

    def test_failed_transition_does_not_increment_revision(self):
        state = _make_state_with_envelope(mode="plan")
        original_revision = state._state_envelope.workflow.revision
        with pytest.raises(AgentRuntimeError):
            apply_workflow_transition(state, source="plan", target="implement", reason_code="bad_reason")
        assert state._state_envelope.workflow.revision == original_revision

    def test_failed_transition_does_not_increment_switches(self):
        state = _make_state_with_envelope(mode="plan")
        original_switches = state.mode_switches
        with pytest.raises(AgentRuntimeError):
            apply_workflow_transition(state, source="plan", target="validate", reason_code="validate_passed")
        assert state.mode_switches == original_switches

    def test_failed_transition_does_not_clear_flags(self):
        state = _make_state_with_envelope(mode="plan")
        state.plan_just_finished = True
        with pytest.raises(AgentRuntimeError):
            apply_workflow_transition(state, source="plan", target="validate", reason_code="validate_passed")
        assert state.plan_just_finished is True
