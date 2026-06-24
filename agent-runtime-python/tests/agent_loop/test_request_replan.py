import inspect

import pytest

from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcherNode
from app.agent_loop.nodes.route_step import RouteStepNode
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.decide_route import apply_route_decision
from app.agent_loop.tools.request_replan import RequestReplanTool
from app.agent_loop.transition_guard import RouteContext


def _build_minimal_context(state: AgentLoopState) -> RouteContext:
    from app.agent_loop.progress import ProgressDetector
    pd = ProgressDetector()
    from app.agent_loop.nodes.route_step import _build_route_context
    return _build_route_context(state, pd)


@pytest.mark.asyncio
async def test_request_replan_sets_structured_signal_without_changing_mode():
    state = AgentLoopState(mode="implement", status="running")
    tool = RequestReplanTool()
    tool.set_state(state)

    result = await tool._arun(reason="计划缺少路由和文件职责")

    assert state.mode == "implement"
    assert state.implement_replan_requested is True
    assert state.implement_replan_reason == "计划缺少路由和文件职责"
    assert state.implement_just_finished is True
    assert state.validate_just_finished is False
    assert "计划缺少路由和文件职责" in result


def test_route_fallback_returns_to_plan_for_structured_replan_request():
    state = AgentLoopState(
        mode="plan",
        implement_just_finished=True,
        implement_replan_requested=True,
        implement_replan_reason="计划缺少状态流转",
    )
    node = object.__new__(RouteStepNode)

    node._apply_safe_fallback(state, _build_minimal_context(state))

    assert state.mode == "plan"
    assert state.route_decision["mode"] == "plan"


def test_entering_new_implement_phase_resets_phase_files_and_replan_signal():
    state = AgentLoopState(
        mode="plan",
        implement_phase_files=["old.vue"],
        implement_replan_requested=True,
        implement_replan_reason="旧原因",
    )

    apply_route_decision(
        state,
        source="plan",
        mode="implement",
        code_gen_type="",
        reason="计划已完整",
    )

    assert state.implement_phase_files == []
    assert state.implement_replan_requested is False
    assert state.implement_replan_reason == ""


def test_implement_dispatcher_does_not_reset_phase_files_each_iteration():
    source = inspect.getsource(ImplementDispatcherNode.__call__)
    assert "implement_phase_files = []" not in source
