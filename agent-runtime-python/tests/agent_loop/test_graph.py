from app.agent_loop.state import AgentLoopState
from app.agent_loop.graph import route_after_plan_step, route_after_implement_step, route_after_validate_step


class TestRouteAfterPlanStep:
    """测试 plan_step 完成后的路由逻辑。

    Phase 4 固定流转：
    - plan_just_finished=True → implement_step（不再经过 route_step）
    - waiting_for_user/completed/failed → finish
    - iteration 达到 max_iterations → finish
    - 否则 → plan_step
    """

    def test_continue_plan_without_finished_flag(self):
        state = AgentLoopState(mode="plan", status="running", iteration=1)
        assert route_after_plan_step(state) == "plan_step"

    def test_plan_just_finished_routes_to_implement_step(self):
        state = AgentLoopState(mode="plan", status="running", plan_just_finished=True)
        assert route_after_plan_step(state) == "implement_step"

    def test_finish_on_completed(self):
        state = AgentLoopState(status="completed")
        assert route_after_plan_step(state) == "finish"

    def test_finish_on_failed(self):
        state = AgentLoopState(status="failed")
        assert route_after_plan_step(state) == "finish"

    def test_finish_on_max_iterations(self):
        state = AgentLoopState(iteration=50, max_iterations=50)
        assert route_after_plan_step(state) == "finish"

    def test_finish_on_max_iterations_exceeded(self):
        state = AgentLoopState(iteration=51, max_iterations=50)
        assert route_after_plan_step(state) == "finish"

    def test_finish_on_max_mode_switches(self):
        state = AgentLoopState(mode_switches=6, max_mode_switches=6)
        assert route_after_plan_step(state) == "finish"

    def test_finish_on_max_mode_switches_exceeded(self):
        state = AgentLoopState(mode_switches=7, max_mode_switches=6)
        assert route_after_plan_step(state) == "finish"

    def test_plan_iterations_at_old_limit_stays_plan(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=15, max_plan_iterations=15)
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_plan_iterations_above_old_limit_stays_plan(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=16, max_plan_iterations=15)
        result = route_after_plan_step(state)
        assert result == "plan_step"

    def test_plan_iterations_below_limit_stays_plan(self):
        state = AgentLoopState(mode="plan", status="running", plan_iterations=14, max_plan_iterations=15)
        assert route_after_plan_step(state) == "plan_step"

    def test_finish_on_waiting_for_user(self):
        state = AgentLoopState(status="waiting_for_user", iteration=3)
        assert route_after_plan_step(state) == "finish"


class TestRouteAfterImplementStep:
    """测试 implement_step 完成后的路由逻辑。

    Phase 4 固定流转：
    - implement_just_finished + replan_requested → route_step
    - implement_just_finished → validate_step
    - 终止条件 → finish
    - 否则 → implement_step
    """

    def test_continue_implement_without_finished_flag(self):
        state = AgentLoopState(mode="implement", status="running", iteration=1)
        assert route_after_implement_step(state) == "implement_step"

    def test_implement_just_finished_routes_to_validate_step(self):
        state = AgentLoopState(mode="implement", status="running", implement_just_finished=True)
        assert route_after_implement_step(state) == "validate_step"

    def test_implement_replan_requested_routes_to_route_step(self):
        state = AgentLoopState(
            mode="implement", status="running",
            implement_just_finished=True, implement_replan_requested=True,
        )
        assert route_after_implement_step(state) == "route_step"

    def test_finish_on_completed(self):
        state = AgentLoopState(status="completed")
        assert route_after_implement_step(state) == "finish"

    def test_finish_on_max_iterations(self):
        state = AgentLoopState(iteration=50, max_iterations=50)
        assert route_after_implement_step(state) == "finish"


class TestRouteAfterValidateStep:
    """测试 validate_step 完成后的路由逻辑。

    Phase 4 固定流转：
    - validate_just_finished + passed → finish
    - validate_just_finished + not_passed → route_step
    - 超限 → route_step
    - 终止条件 → finish
    - 否则 → validate_step
    """

    def test_continue_validate_without_finished_flag(self):
        state = AgentLoopState(mode="validate", status="running", iteration=1)
        assert route_after_validate_step(state) == "validate_step"

    def test_validate_passed_routes_to_finish(self):
        state = AgentLoopState(
            mode="validate", status="running",
            validate_just_finished=True, validation_status="passed",
        )
        assert route_after_validate_step(state) == "finish"

    def test_validate_failed_routes_to_route_step(self):
        state = AgentLoopState(
            mode="validate", status="running",
            validate_just_finished=True, validation_status="failed",
        )
        assert route_after_validate_step(state) == "route_step"

    def test_validate_pending_routes_to_route_step(self):
        state = AgentLoopState(
            mode="validate", status="running",
            validate_just_finished=True, validation_status="pending",
        )
        assert route_after_validate_step(state) == "route_step"

    def test_validate_iterations_exceeded_routes_to_route_step(self):
        state = AgentLoopState(
            mode="validate", status="running",
            validate_iterations=3, max_validate_iterations=3,
        )
        assert route_after_validate_step(state) == "route_step"

    def test_finish_on_completed(self):
        state = AgentLoopState(status="completed")
        assert route_after_validate_step(state) == "finish"
