"""Implement 完成门禁工具测试。"""

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.complete_implementation import (
    CompleteImplementationTool,
)
from app.core.exceptions import AgentRuntimeError


@pytest.fixture
def state_with_files() -> AgentLoopState:
    state = AgentLoopState(mode="implement", status="running")
    state.implement_phase_files = ["src/App.vue"]
    return state


@pytest.mark.asyncio
async def test_complete_rejects_when_no_files_and_no_limitations():
    state = AgentLoopState(mode="implement", status="running")
    tool = CompleteImplementationTool()
    tool.set_state(state)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=[],
        known_limitations=[],
    )

    assert "无文件变更" in result
    assert state.implement_just_finished is False


@pytest.mark.asyncio
async def test_complete_rejects_when_files_but_no_verification(state_with_files):
    tool = CompleteImplementationTool()
    tool.set_state(state_with_files)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=[],
    )

    assert "验证证据" in result
    assert state_with_files.implement_just_finished is False


@pytest.mark.asyncio
async def test_complete_accepts_with_files_and_verification(state_with_files):
    tool = CompleteImplementationTool()
    tool.set_state(state_with_files)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=["build_output"],
    )

    assert "门禁已通过" in result
    assert state_with_files.implement_just_finished is True


@pytest.mark.asyncio
async def test_complete_accepts_verified_no_code_task():
    state = AgentLoopState(mode="implement", status="running")
    tool = CompleteImplementationTool()
    tool.set_state(state)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=["docs_review"],
        known_limitations=["文档分析任务，无需代码变更"],
    )

    assert "门禁已通过" in result
    assert state.implement_just_finished is True


@pytest.mark.asyncio
async def test_complete_rejects_invalid_run_kind():
    state = AgentLoopState(mode="implement", status="running")
    state.implement_phase_files = ["src/App.vue"]
    tool = CompleteImplementationTool()
    tool.set_state(state)

    with pytest.raises(AgentRuntimeError) as exc_info:
        await tool._arun(
            run_kind="invalid_kind",
            source_plan_version=1,
            completed_task_ids=["t1"],
            verification_refs=["build"],
        )
    assert "run_kind" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_accepts_validation_repair_run_kind():
    state = AgentLoopState(mode="implement", status="running")
    state.implement_phase_files = ["src/App.vue"]
    tool = CompleteImplementationTool()
    tool.set_state(state)

    result = await tool._arun(
        run_kind="validation_repair",
        source_plan_version=1,
        completed_task_ids=["t1"],
        addressed_issue_ids=["issue-1"],
        verification_refs=["build_output"],
    )

    assert "门禁已通过" in result
    assert state.implement_just_finished is True
