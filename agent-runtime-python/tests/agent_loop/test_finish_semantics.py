from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent_loop.nodes.finish import FinishNode
from app.agent_loop.state import AgentLoopState
from app.runtime.context import ExecutionContext, CodeGenType, RunMode
from app.runtime.events import RuntimeEventType
from app.runtime.services import RuntimeServices


def _make_services():
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    services = MagicMock(spec=RuntimeServices)
    services.event_bus = event_bus
    return services


def _make_context():
    return ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="test",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="/tmp/ws",
        run_mode=RunMode.GENERATE,
    )


def _emitted_event_types(bus):
    return [call.args[0].event_type for call in bus.emit.await_args_list]


def _find_event_data(bus, event_type):
    for call in bus.emit.await_args_list:
        ev = call.args[0]
        if ev.event_type == event_type:
            return ev.data
    return None


@pytest.mark.asyncio
async def test_finish_does_not_promote_running_to_completed():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(status="running", iteration=5, max_iterations=50)

    result = await node(state)

    assert result.status != "completed", (
        f"FinishNode must not promote running→completed, got: {result.status}"
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_max_iterations_ends_failed_with_reason():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(status="running", iteration=50, max_iterations=50)

    result = await node(state)

    assert result.status == "failed"
    assert "迭代上限" in result.final_summary or "迭代" in result.final_summary


@pytest.mark.asyncio
async def test_zero_file_generation_cannot_complete():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(status="running", iteration=3, files_touched=[])

    result = await node(state)

    assert result.status != "completed", (
        f"Zero files + running must not become completed, got: {result.status}"
    )


@pytest.mark.asyncio
async def test_valid_final_success_remains_completed():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(
        status="completed",
        iteration=10,
        files_touched=["src/App.vue", "src/main.ts"],
        final_summary="生成完成",
    )

    result = await node(state)

    assert result.status == "completed"
    assert result.final_summary == "生成完成"


@pytest.mark.asyncio
async def test_finish_is_idempotent_for_non_success_state():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(
        status="failed",
        iteration=5,
        final_summary="计划被阻断",
    )

    result1 = await node(state)
    result2 = await node(result1)

    assert result1.status == "failed"
    assert result2.status == "failed"
    assert result1.final_summary == result2.final_summary

    completed_data_list = []
    for call in services.event_bus.emit.await_args_list:
        ev = call.args[0]
        if ev.event_type == RuntimeEventType.AGENT_LOOP_COMPLETED:
            completed_data_list.append(ev.data)

    assert len(completed_data_list) == 2

    done_events = [
        call.args[0]
        for call in services.event_bus.emit.await_args_list
        if call.args[0].event_type == RuntimeEventType.DONE
    ]
    for ev in done_events:
        assert "计划被阻断" in ev.data.get("message", "")


@pytest.mark.asyncio
async def test_route_finished_sets_failed_on_max_iterations():
    from app.agent_loop.graph import _route_finished

    state = AgentLoopState(status="running", iteration=50, max_iterations=50)
    result = _route_finished(state)

    assert result is True
    assert state.status == "failed"
    assert "迭代上限" in state.final_summary


@pytest.mark.asyncio
async def test_route_finished_sets_failed_on_max_mode_switches():
    from app.agent_loop.graph import _route_finished

    state = AgentLoopState(
        status="running",
        iteration=10,
        max_iterations=50,
        mode_switches=6,
        max_mode_switches=6,
    )
    result = _route_finished(state)

    assert result is True
    assert state.status == "failed"
    assert "模式切换上限" in state.final_summary


@pytest.mark.asyncio
async def test_route_finished_does_not_overwrite_existing_failed():
    from app.agent_loop.graph import _route_finished

    state = AgentLoopState(
        status="failed",
        iteration=50,
        max_iterations=50,
        final_summary="工具执行失败",
    )
    result = _route_finished(state)

    assert result is True
    assert state.status == "failed"
    assert state.final_summary == "工具执行失败"


@pytest.mark.asyncio
async def test_route_finished_preserves_completed():
    from app.agent_loop.graph import _route_finished

    state = AgentLoopState(status="completed", iteration=10, max_iterations=50)
    result = _route_finished(state)

    assert result is True
    assert state.status == "completed"


@pytest.mark.asyncio
async def test_finish_node_emits_completed_event_with_status():
    services = _make_services()
    node = FinishNode(_make_context(), services)
    state = AgentLoopState(status="failed", iteration=5, final_summary="异常终止")

    await node(state)

    completed_data = _find_event_data(services.event_bus, RuntimeEventType.AGENT_LOOP_COMPLETED)
    assert completed_data is not None
    assert completed_data["status"] == "failed"
    assert completed_data["iterations"] == 5
