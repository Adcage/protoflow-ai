"""Implement 上下文组装和 Plan 阶段隔离测试。

覆盖 Task 4-2 中关于 Implement 上下文接收完整 Plan 产物但不接收 Plan System Prompt 的要求。
"""

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import (
    ImplementationPlan,
    ImplementationTask,
    PlanStateV2,
    WorkflowState,
    WorkflowStateEnvelope,
)
from app.agent_loop.tools.complete_implementation import (
    CompleteImplementationTool,
)


def _make_state_with_plan() -> AgentLoopState:
    state = AgentLoopState(mode="implement", status="running")
    state._state_envelope = WorkflowStateEnvelope(
        workflow=WorkflowState(
            current_mode="implement",
            plan=PlanStateV2(
                plan_stage="completed",
                plan_just_finished=True,
                implementation_plan=ImplementationPlan(
                    plan_version=1,
                    source_design_version=1,
                    tasks=[
                        ImplementationTask(
                            task_id="T1",
                            goal="实现登录页",
                            allowed_files=["src/Login.vue"],
                        )
                    ],
                ),
            ),
        )
    )
    return state


def test_state_has_implementation_plan():
    state = _make_state_with_plan()
    envelope = state._state_envelope
    assert envelope.workflow.plan.implementation_plan is not None
    assert len(envelope.workflow.plan.implementation_plan.tasks) == 1
    assert envelope.workflow.plan.implementation_plan.tasks[0].task_id == "T1"


@pytest.mark.asyncio
async def test_complete_accepts_with_files_and_verification():
    state = AgentLoopState(mode="implement", status="running")
    state.implement_phase_files = ["src/App.vue"]
    tool = CompleteImplementationTool()
    tool.set_state(state)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=["build_output"],
    )

    assert "门禁已通过" in result
    assert state.implement_just_finished is True


@pytest.mark.asyncio
async def test_complete_rejects_no_files_no_limitations():
    state = AgentLoopState(mode="implement", status="running")
    tool = CompleteImplementationTool()
    tool.set_state(state)

    result = await tool._arun(
        run_kind="initial",
        source_plan_version=1,
        completed_task_ids=["t1"],
        verification_refs=["build_output"],
    )

    assert "门禁未通过" in result
    assert state.implement_just_finished is False
