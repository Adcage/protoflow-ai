import pytest

from app.agent_loop.state import AgentLoopState


class TestAgentLoopState:
    def test_default_state(self):
        state = AgentLoopState()
        assert state.mode == "plan"
        assert state.status == "running"
        assert state.iteration == 0
        assert state.max_iterations == 50
        assert state.mode_switches == 0
        assert state.max_mode_switches == 6
        assert state.selected_capabilities is None
        assert state.implementation_outline is None
        assert state.clarification_questions == []

    def test_mode_transition(self):
        state = AgentLoopState()
        state.mode = "implement"
        state.mode_switches += 1
        assert state.mode == "implement"
        assert state.mode_switches == 1

    def test_completed_status(self):
        state = AgentLoopState(status="completed")
        assert state.status == "completed"

    def test_max_iterations_exceeded(self):
        state = AgentLoopState(iteration=51, max_iterations=50)
        assert state.iteration >= state.max_iterations
