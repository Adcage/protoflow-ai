"""Validate 阶段结构化校验报告提交工具。

只读校验产出详细 ValidationIssue 列表，不得修改任何文件。
error 级 issue 必须包含 evidence 和 repair_requirements。
"""

import logging
import uuid
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.submit_validation_report")


class ValidationIssueInput(BaseModel):
    issue_id: str = Field(description="问题唯一标识")
    category: str = Field(
        description="build | test | lint | type | runtime | requirement | design | security | permission | protocol | unknown"
    )
    severity: str = Field(description="error | warning | info")
    title: str = Field(description="问题标题")
    evidence: list[str] = Field(default_factory=list, description="证据引用列表")
    affected_files: list[str] = Field(default_factory=list, description="受影响文件列表")
    related_task_ids: list[str] = Field(default_factory=list, description="相关任务 ID")
    expected_behavior: str = Field(default="", description="期望行为")
    actual_behavior: str = Field(default="", description="实际行为")
    repair_requirements: list[str] = Field(default_factory=list, description="修复要求")
    allowed_files: list[str] = Field(default_factory=list, description="允许修复的文件范围")
    prohibited_changes: list[str] = Field(default_factory=list, description="禁止的变更")
    disposition: str = Field(
        description="implement_repair | return_plan | needs_user | blocked"
    )


class SubmitValidationReportInput(BaseModel):
    issues: list[ValidationIssueInput] = Field(default_factory=list, description="校验问题列表")
    passed: bool = Field(description="是否通过校验")
    coverage_gaps: list[str] = Field(default_factory=list, description="覆盖缺口")
    recommended_transition: str = Field(
        description="finished | implement | plan | wait_user | blocked"
    )


class SubmitValidationReportTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "submit_validation_report"
    description: str = (
        "提交结构化校验报告。error 级 issue 必须包含 evidence 和 repair_requirements。"
        "只读校验不会修改任何文件。问题只能由重新校验关闭。"
    )
    args_schema: Type[BaseModel] = SubmitValidationReportInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        issues: list[dict] | None = None,
        passed: bool = False,
        coverage_gaps: list[str] | None = None,
        recommended_transition: str = "finished",
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError("未绑定 AgentLoopState", code=AgentErrorCode.STATE_ERROR)

        from app.agent_loop.state import AgentLoopState
        if not isinstance(self._state, AgentLoopState):
            raise AgentRuntimeError("状态类型不正确", code=AgentErrorCode.STATE_ERROR)

        state: AgentLoopState = self._state

        for issue in (issues or []):
            if issue.get("severity") == "error" and not issue.get("evidence"):
                raise AgentRuntimeError(
                    f"error 级 issue '{issue.get('issue_id', '?')}' 必须包含 evidence",
                    code=AgentErrorCode.STATE_ERROR,
                )
            if issue.get("severity") == "error" and not issue.get("repair_requirements"):
                raise AgentRuntimeError(
                    f"error 级 issue '{issue.get('issue_id', '?')}' 必须包含 repair_requirements",
                    code=AgentErrorCode.STATE_ERROR,
                )

        state.validation_failures = list(issues or [])
        state.validation_status = "passed" if passed else "failed"
        state.validate_just_finished = True

        report_id = f"vr_{uuid.uuid4().hex[:8]}"
        logger.info(
            "submit_validation_report | report_id=%s passed=%s issues=%d transition=%s",
            report_id,
            passed,
            len(issues or []),
            recommended_transition,
        )
        return (
            f"校验报告 {report_id} 已提交：{'通过' if passed else '未通过'}，"
            f"{len(issues or [])} 个问题。推荐下一步: {recommended_transition}。"
        )