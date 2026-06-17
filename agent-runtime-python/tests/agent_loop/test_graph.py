import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.graph import route_after_step


class TestRouteAfterStep:
    def test_continue_plan(self):
        state = AgentLoopState(mode="plan", status="running", iteration=1)
        assert route_after_step(state) == "plan"

    def test_continue_implement(self):
        state = AgentLoopState(mode="implement", status="running", iteration=2)
        assert route_after_step(state) == "implement"

    def test_finish_on_completed(self):
        state = AgentLoopState(status="completed")
        assert route_after_step(state) == "finish"

    def test_finish_on_failed(self):
        state = AgentLoopState(status="failed")
        assert route_after_step(state) == "finish"

    def test_finish_on_max_iterations(self):
        state = AgentLoopState(iteration=50, max_iterations=50)
        assert route_after_step(state) == "finish"

    def test_finish_on_max_iterations_exceeded(self):
        state = AgentLoopState(iteration=51, max_iterations=50)
        assert route_after_step(state) == "finish"

    def test_finish_on_max_mode_switches(self):
        state = AgentLoopState(mode_switches=6, max_mode_switches=6)
        assert route_after_step(state) == "finish"

    def test_finish_on_max_mode_switches_exceeded(self):
        state = AgentLoopState(mode_switches=7, max_mode_switches=6)
        assert route_after_step(state) == "finish"

    def test_mode_takes_priority_over_iteration_when_both_safe(self):
        state = AgentLoopState(mode="plan", status="running", iteration=30, mode_switches=3)
        assert route_after_step(state) == "plan"

    def test_force_implement_on_plan_iterations_exceeded(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=15, max_plan_iterations=15)
        result = route_after_step(state)
        assert result == "implement"
        assert state.mode == "implement"

    def test_force_implement_on_plan_iterations_exceeded_boundary(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=16, max_plan_iterations=15)
        result = route_after_step(state)
        assert result == "implement"
        assert state.mode == "implement"

    def test_plan_iterations_below_limit_stays_plan(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=14, max_plan_iterations=15)
        assert route_after_step(state) == "plan"

    def test_plan_iterations_limit_does_not_affect_implement_mode(self):
        state = AgentLoopState(mode="implement", status="running", plan_iterations=20, max_plan_iterations=15)
        assert route_after_step(state) == "implement"
