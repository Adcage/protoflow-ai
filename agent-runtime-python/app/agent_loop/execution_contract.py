"""ExecutionContract: 统一 Implement 输入协议。

Phase 2 Task 2-1: 让直接实现、计划实现和校验返工统一为一种 Implement 输入。
三类来源（direct、plan、validation_repair）产生相同合同结构，
Implement 只读取 execution_contract，不再从分散字段推断执行范围。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import uuid4

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

if TYPE_CHECKING:
    from app.agent_loop.plan_types import ImplementationPlan

ContractSource = Literal["direct", "plan", "validation_repair"]

_WILDCARD_PATTERNS = {"*", "**", "/*", "/**", "*/", "**/"}
_VAGUE_DESCRIPTIONS = {"相关文件", "相关", "所有文件", "全部文件", "all files"}


class DirectImplementationBrief(BaseModel):
    """Route 直接实现时的最小输入协议。

    必须包含精确的文件范围、验收标准和验证要求，
    禁止使用通配符或模糊描述。
    """

    generation_mode: str
    goal: str
    allowed_files: list[str]
    acceptance_criteria: list[str]
    verification_requirements: list[str]

    @field_validator("generation_mode")
    @classmethod
    def _generation_mode_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise AgentRuntimeError(
                "DirectImplementationBrief.generation_mode 必填且不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("goal")
    @classmethod
    def _goal_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise AgentRuntimeError(
                "DirectImplementationBrief.goal 必填且不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("allowed_files")
    @classmethod
    def _allowed_files_non_empty_and_exact(cls, v: list[str]) -> list[str]:
        if not v:
            raise AgentRuntimeError(
                "DirectImplementationBrief.allowed_files 必须包含至少一个具体文件路径",
                code=AgentErrorCode.STATE_ERROR,
            )
        for f in v:
            stripped = f.strip()
            if not stripped:
                raise AgentRuntimeError(
                    "DirectImplementationBrief.allowed_files 不允许包含空路径",
                    code=AgentErrorCode.STATE_ERROR,
                )
            if stripped in _WILDCARD_PATTERNS or any(
                pattern in stripped for pattern in ("*", "**")
            ):
                raise AgentRuntimeError(
                    f"DirectImplementationBrief.allowed_files 不允许使用通配符: {stripped}",
                    code=AgentErrorCode.STATE_ERROR,
                )
            if stripped in _VAGUE_DESCRIPTIONS:
                raise AgentRuntimeError(
                    f"DirectImplementationBrief.allowed_files 不允许使用模糊描述: {stripped}",
                    code=AgentErrorCode.STATE_ERROR,
                )
        return v

    @field_validator("acceptance_criteria")
    @classmethod
    def _acceptance_criteria_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise AgentRuntimeError(
                "DirectImplementationBrief.acceptance_criteria 必须包含至少一条验收标准",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("verification_requirements")
    @classmethod
    def _verification_requirements_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise AgentRuntimeError(
                "DirectImplementationBrief.verification_requirements 必须包含至少一条验证要求",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v


class ContractTask(BaseModel):
    """ExecutionContract 中的单个任务。

    由 Plan 的 ImplementationTask 映射而来，
    或由 DirectImplementationBrief 自动生成。
    """

    task_id: str
    goal: str
    allowed_files: list[str]
    prohibited_changes: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    verification_requirements: list[str] = Field(default_factory=list)


class ExecutionContract(BaseModel):
    """统一 Implement 输入协议。

    三类来源（direct、plan、validation_repair）产生相同结构，
    Implement 只读取此合同，不再从分散字段推断执行范围。
    """

    contract_id: str = Field(default_factory=lambda: str(uuid4()))
    contract_version: int = 1
    source: ContractSource
    generation_mode: str
    expected_artifact_format: str
    goal: str
    tasks: list[ContractTask]
    acceptance_criteria: list[str] = Field(default_factory=list)
    verification_requirements: list[str] = Field(default_factory=list)
    prohibited_changes: list[str] = Field(default_factory=list)
    active_issue_ids: list[str] = Field(default_factory=list)

    @field_validator("generation_mode")
    @classmethod
    def _generation_mode_not_unresolved(cls, v: str) -> str:
        if v == "unresolved":
            raise AgentRuntimeError(
                "ExecutionContract.generation_mode 不允许为 unresolved",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("tasks")
    @classmethod
    def _tasks_non_empty(cls, v: list[ContractTask]) -> list[ContractTask]:
        if not v:
            raise AgentRuntimeError(
                "ExecutionContract.tasks 必须包含至少一个 ContractTask",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @model_validator(mode="after")
    def _validation_repair_requires_issue_ids(self) -> "ExecutionContract":
        if self.source == "validation_repair" and not self.active_issue_ids:
            raise AgentRuntimeError(
                "source=validation_repair 时 active_issue_ids 必须非空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return self


def from_direct_brief(
    brief: DirectImplementationBrief,
    expected_artifact_format: str,
) -> ExecutionContract:
    """将 DirectImplementationBrief 标准化为 ExecutionContract。

    source="direct"，自动生成单个 direct_task_001 任务。
    """
    task = ContractTask(
        task_id="direct_task_001",
        goal=brief.goal,
        allowed_files=list(brief.allowed_files),
        acceptance_criteria=list(brief.acceptance_criteria),
        verification_requirements=list(brief.verification_requirements),
    )
    return ExecutionContract(
        source="direct",
        generation_mode=brief.generation_mode,
        expected_artifact_format=expected_artifact_format,
        goal=brief.goal,
        tasks=[task],
        acceptance_criteria=list(brief.acceptance_criteria),
        verification_requirements=list(brief.verification_requirements),
    )


def from_implementation_plan(
    plan: "ImplementationPlan",
    generation_mode: str,
    expected_artifact_format: str,
) -> ExecutionContract:
    """将 ImplementationPlan 标准化为 ExecutionContract。

    source="plan"，映射 plan.tasks 为 ContractTask 列表，
    保留 prohibited_changes。
    """
    from app.agent_loop.state_v2 import ImplementationPlan

    if not isinstance(plan, ImplementationPlan):
        raise AgentRuntimeError(
            "from_implementation_plan 需要 ImplementationPlan 实例",
            code=AgentErrorCode.STATE_ERROR,
        )

    contract_tasks = []
    for plan_task in plan.tasks:
        contract_task = ContractTask(
            task_id=plan_task.task_id,
            goal=plan_task.goal,
            allowed_files=list(plan_task.allowed_files),
            prohibited_changes=list(plan_task.prohibited_files),
            acceptance_criteria=list(plan_task.acceptance_criteria),
            verification_requirements=list(plan_task.test_requirements),
        )
        contract_tasks.append(contract_task)

    if not contract_tasks and plan.summary:
        contract_tasks.append(
            ContractTask(
                task_id="plan_task_001",
                goal=plan.summary[:200],
                allowed_files=[],
                verification_requirements=list(plan.test_plan or []),
                acceptance_criteria=list(plan.acceptance_criteria),
            )
        )

    return ExecutionContract(
        source="plan",
        generation_mode=generation_mode,
        expected_artifact_format=expected_artifact_format,
        goal=plan.summary or "Implement plan tasks",
        tasks=contract_tasks,
        acceptance_criteria=list(plan.acceptance_criteria),
        prohibited_changes=list(plan.prohibited_changes),
    )


def from_validation_repair(
    generation_mode: str,
    expected_artifact_format: str,
    active_issue_ids: list[str],
    goal: str,
    allowed_files: list[str],
) -> ExecutionContract:
    """从校验返工创建 ExecutionContract。

    source="validation_repair"，active_issue_ids 必须非空。
    """
    if not active_issue_ids:
        raise AgentRuntimeError(
            "from_validation_repair: active_issue_ids 必须非空",
            code=AgentErrorCode.STATE_ERROR,
        )

    task = ContractTask(
        task_id="repair_task_001",
        goal=goal,
        allowed_files=list(allowed_files),
    )
    return ExecutionContract(
        source="validation_repair",
        generation_mode=generation_mode,
        expected_artifact_format=expected_artifact_format,
        goal=goal,
        tasks=[task],
        active_issue_ids=list(active_issue_ids),
    )
