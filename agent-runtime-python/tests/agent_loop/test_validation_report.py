"""Validate 结构化报告提交工具测试。"""

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.submit_validation_report import (
    SubmitValidationReportTool,
)
from app.core.exceptions import AgentRuntimeError


@pytest.mark.asyncio
async def test_validation_report_passed_with_no_issues():
    state = AgentLoopState(mode="validate", status="running")
    tool = SubmitValidationReportTool()
    tool.set_state(state)

    result = await tool._arun(
        issues=[],
        passed=True,
        coverage_gaps=[],
        recommended_transition="finished",
    )

    assert "已提交" in result
    assert "通过" in result
    assert state.validate_just_finished is True
    assert state.validation_status == "passed"


@pytest.mark.asyncio
async def test_validation_report_failed_with_repair_issues():
    state = AgentLoopState(mode="validate", status="running")
    tool = SubmitValidationReportTool()
    tool.set_state(state)

    issues = [
        {
            "issue_id": "build-1",
            "category": "build",
            "severity": "error",
            "title": "Build failed",
            "evidence": ["build_log.txt:42"],
            "affected_files": ["src/App.vue"],
            "expected_behavior": "Build succeeds",
            "actual_behavior": "TypeError on line 42",
            "repair_requirements": ["Fix type mismatch"],
            "allowed_files": ["src/App.vue"],
            "disposition": "implement_repair",
        }
    ]

    result = await tool._arun(
        issues=issues,
        passed=False,
        coverage_gaps=[],
        recommended_transition="implement",
    )

    assert "已提交" in result
    assert "未通过" in result
    assert state.validate_just_finished is True
    assert state.validation_status == "failed"
    assert len(state.validation_failures) == 1


@pytest.mark.asyncio
async def test_validation_report_rejects_error_without_evidence():
    state = AgentLoopState(mode="validate", status="running")
    tool = SubmitValidationReportTool()
    tool.set_state(state)

    issues = [
        {
            "issue_id": "build-1",
            "category": "build",
            "severity": "error",
            "title": "Build failed",
            "evidence": [],
            "disposition": "implement_repair",
        }
    ]

    with pytest.raises(AgentRuntimeError) as exc_info:
        await tool._arun(issues=issues, passed=False, recommended_transition="implement")
    assert "evidence" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validation_report_rejects_error_without_repair_requirements():
    state = AgentLoopState(mode="validate", status="running")
    tool = SubmitValidationReportTool()
    tool.set_state(state)

    issues = [
        {
            "issue_id": "build-1",
            "category": "build",
            "severity": "error",
            "title": "Build failed",
            "evidence": ["build_log.txt:42"],
            "repair_requirements": [],
            "disposition": "implement_repair",
        }
    ]

    with pytest.raises(AgentRuntimeError) as exc_info:
        await tool._arun(issues=issues, passed=False, recommended_transition="implement")
    assert "repair_requirements" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validation_report_warnings_dont_require_evidence():
    state = AgentLoopState(mode="validate", status="running")
    tool = SubmitValidationReportTool()
    tool.set_state(state)

    issues = [
        {
            "issue_id": "lint-1",
            "category": "lint",
            "severity": "warning",
            "title": "Unused import",
            "disposition": "implement_repair",
        }
    ]

    result = await tool._arun(
        issues=issues, passed=True, recommended_transition="finished"
    )
    assert "已提交" in result
