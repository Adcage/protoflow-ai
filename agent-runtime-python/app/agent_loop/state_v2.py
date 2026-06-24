from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.agent_loop.phase_report import PhaseCompletionReport
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


PlanStage = Literal[
    "discover_direction",
    "discover_scope",
    "inspect_existing_project",
    "select_skill",
    "propose_design",
    "confirm_design",
    "write_implementation_plan",
    "completed",
    "waiting_for_user",
    "blocked",
]

CapabilityKind = Literal["skill", "design_system", "template", "seed", "craft"]
ConfirmedValueSource = Literal["user", "project", "skill"]


class ConfirmedValue(BaseModel):
    value: str
    source: ConfirmedValueSource
    confirmation_message_id: str | None = None
    confirmed: bool = False
    skipped_by_user: bool = False
    note: str = ""


class Constraint(BaseModel):
    description: str
    source: ConfirmedValueSource
    confirmation_message_id: str | None = None
    evidence_ref: str | None = None


class PageSpec(BaseModel):
    page_id: str
    name: str
    purpose: str
    primary_actions: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)


class ConfirmedChoice(BaseModel):
    selected_option_id: str | None = None
    description: str
    source: ConfirmedValueSource
    confirmation_message_id: str | None = None
    confirmed: bool = False
    alternative_option_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class Rationale(BaseModel):
    decision: str
    reason: str
    source_refs: list[str] = Field(default_factory=list)


class RequirementBrief(BaseModel):
    application_direction: ConfirmedValue
    target_users: ConfirmedValue
    primary_scenarios: list[ConfirmedValue] = Field(default_factory=list)
    functional_scope: list[ConfirmedValue] = Field(default_factory=list)
    content_and_data: list[ConfirmedValue] = Field(default_factory=list)
    existing_project_constraints: list[Constraint] = Field(default_factory=list)
    technical_constraints: list[Constraint] = Field(default_factory=list)
    responsive_targets: list[ConfirmedValue] = Field(default_factory=list)
    accessibility_expectations: list[ConfirmedValue] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class CapabilityRef(BaseModel):
    capability_id: str
    kind: CapabilityKind
    source_path: str
    content_digest: str
    loaded_resources: list[str] = Field(default_factory=list)
    selected_reason: str
    selected_at_revision: int
    enabled: bool = True

    @model_validator(mode="after")
    def _enforce_seed_craft_disabled(self) -> "CapabilityRef":
        if self.kind in {"seed", "craft"} and self.enabled:
            raise AgentRuntimeError(
                f"Capability kind={self.kind} 当前阶段必须保持 disabled",
                code=AgentErrorCode.STATE_ERROR,
            )
        return self


class CapabilityBundleRef(BaseModel):
    skills: list[CapabilityRef] = Field(default_factory=list)
    design_systems: list[CapabilityRef] = Field(default_factory=list)
    templates: list[CapabilityRef] = Field(default_factory=list)
    seeds: list[CapabilityRef] = Field(default_factory=list)
    craft: list[CapabilityRef] = Field(default_factory=list)

    def all_refs(self) -> list[CapabilityRef]:
        return (
            list(self.skills)
            + list(self.design_systems)
            + list(self.templates)
            + list(self.seeds)
            + list(self.craft)
        )


class DesignSpecification(BaseModel):
    design_version: int = 0
    information_architecture: list[PageSpec] = Field(default_factory=list)
    visual_direction: ConfirmedChoice
    color_system: ConfirmedChoice
    typography: ConfirmedChoice
    component_language: ConfirmedChoice
    interaction_model: ConfirmedChoice
    responsive_strategy: ConfirmedChoice
    accessibility_rules: list[str] = Field(default_factory=list)
    content_strategy: list[str] = Field(default_factory=list)
    design_rationale: list[Rationale] = Field(default_factory=list)
    confirmation_message_id: str | None = None
    confirmed: bool = False
    confirmed_at: str | None = None


class ImplementationTask(BaseModel):
    task_id: str
    goal: str
    allowed_files: list[str]
    prohibited_files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    test_requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "ImplementationTask":
        if not self.task_id or not self.task_id.strip():
            raise AgentRuntimeError(
                "ImplementationTask.task_id 必填",
                code=AgentErrorCode.STATE_ERROR,
            )
        if not self.goal or not self.goal.strip():
            raise AgentRuntimeError(
                f"ImplementationTask.task_id={self.task_id} 的 goal 必填",
                code=AgentErrorCode.STATE_ERROR,
            )
        if not self.allowed_files:
            raise AgentRuntimeError(
                f"ImplementationTask.task_id={self.task_id} 必须包含至少一个 allowed_files",
                code=AgentErrorCode.STATE_ERROR,
            )
        return self


class PlanTestItem(BaseModel):
    test_id: str
    description: str
    target: str
    expected: str


class ImplementationPlan(BaseModel):
    plan_version: int = 0
    source_design_version: int
    tasks: list[ImplementationTask]
    test_plan: list[PlanTestItem] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    prohibited_changes: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _validate_tasks_present(self) -> "ImplementationPlan":
        if not self.tasks:
            raise AgentRuntimeError(
                "ImplementationPlan 必须包含至少一个 ImplementationTask",
                code=AgentErrorCode.STATE_ERROR,
            )
        if self.source_design_version <= 0:
            raise AgentRuntimeError(
                "ImplementationPlan.source_design_version 必须 > 0",
                code=AgentErrorCode.STATE_ERROR,
            )
        for task in self.tasks:
            if not task.task_id or not task.goal or not task.allowed_files:
                raise AgentRuntimeError(
                    f"ImplementationTask 缺少必填字段: {task.task_id or '<unknown>'}",
                    code=AgentErrorCode.STATE_ERROR,
                )
        return self


class PlanStateV2(BaseModel):
    plan_iterations: int = 0
    max_plan_iterations: int = 60
    plan_soft_limit: int = 30
    plan_hard_limit: int = 60
    model_call_count: int = 0
    plan_session_id: str | None = None
    plan_stage: PlanStage = "discover_direction"
    previous_plan_stage: PlanStage | None = None
    capability_bundle: CapabilityBundleRef = Field(default_factory=CapabilityBundleRef)
    requirement_brief: RequirementBrief | None = None
    design_specification: DesignSpecification | None = None
    implementation_plan: ImplementationPlan | None = None
    selected_skill_id: str | None = None
    implementation_outline: dict | None = None
    clarification_questions: list[dict] = Field(default_factory=list)
    plan_just_finished: bool = False
    is_waiting_for_user: bool = False
    project_inspection: dict | None = None
    skill_context_changed: bool = False
    pending_question_set_id: str | None = None
    design_spec_revision: int = 0
    implementation_plan_revision: int = 0

    def advance_stage(self, next_stage: PlanStage) -> None:
        allowed: dict[PlanStage, set[PlanStage]] = {
            "discover_direction": {"discover_scope"},
            "discover_scope": {"inspect_existing_project", "select_skill"},
            "inspect_existing_project": {"select_skill", "discover_scope"},
            "select_skill": {"propose_design"},
            "propose_design": {"confirm_design", "discover_scope", "select_skill"},
            "confirm_design": {"write_implementation_plan", "propose_design"},
            "write_implementation_plan": {"completed"},
            "completed": {"completed"},
            "waiting_for_user": {
                "discover_direction",
                "discover_scope",
                "select_skill",
                "propose_design",
                "confirm_design",
                "write_implementation_plan",
            },
            "blocked": {"discover_direction", "discover_scope", "propose_design", "blocked"},
        }
        if next_stage not in allowed.get(self.plan_stage, set()):
            raise AgentRuntimeError(
                f"PlanStage 非法跃迁: {self.plan_stage} -> {next_stage}",
                code=AgentErrorCode.STATE_ERROR,
            )
        self.previous_plan_stage = self.plan_stage
        self.plan_stage = next_stage

    def increment_model_call(self) -> int:
        self.model_call_count += 1
        return self.model_call_count

    def reached_hard_limit(self) -> bool:
        return self.model_call_count >= self.plan_hard_limit

    def reached_soft_limit(self) -> bool:
        return self.model_call_count >= self.plan_soft_limit

    def has_project_inspection(self) -> bool:
        if not self.project_inspection:
            return False
        decision = self.project_inspection.get("decision")
        return decision in {"inspected", "not_applicable"}


class ExecutionStateV2(BaseModel):
    files_touched: list[str] = Field(default_factory=list)
    implement_phase_files: list[str] = Field(default_factory=list)
    implement_replan_requested: bool = False
    implement_replan_reason: str = ""
    implement_just_finished: bool = False
    execution_run_kind: str = "initial"
    source_plan_version: int = 0
    active_task_id: str | None = None
    execution_tasks: list[dict] = Field(default_factory=list)
    active_issue_ids: list[str] = Field(default_factory=list)
    call_budget_soft_limit: int = 0
    call_budget_hard_limit: int = 0
    call_budget_model_call_count: int = 0
    completion_candidate: dict | None = None
    execution_contract: dict | None = None


class ValidationStateV2(BaseModel):
    validate_iterations: int = 0
    validation_failures: list[dict] = Field(default_factory=list)
    validation_check_results: list[dict] | None = None
    validation_status: Literal["pending", "passed", "failed"] = "pending"
    validate_just_finished: bool = False
    validation_issues: list[dict] = Field(default_factory=list)
    validation_report_id: str | None = None
    validation_coverage_gaps: list[str] = Field(default_factory=list)
    validation_recommended_transition: str | None = None


class RoutingStateV2(BaseModel):
    route_decided: bool = False
    route_decision: dict | None = None
    route_iterations: int = 0
    recommended_code_gen_type: str | None = None


class ConversationStateV2(BaseModel):
    conversation_messages: list[dict] = Field(default_factory=list)


class ArtifactTypeState(BaseModel):
    model_config = {"frozen": True}

    requested: str
    effective: str
    recommended: str | None = None
    recommendation_reason: str | None = None

    @model_validator(mode="after")
    def _effective_defaults_to_requested(self) -> "ArtifactTypeState":
        if not self.effective:
            object.__setattr__(self, "effective", self.requested)
        return self


class ProgressStateV2(BaseModel):
    pass


_SOURCE_MODE_OWNED_PARTITIONS: dict[str, frozenset[str]] = {
    "plan": frozenset({"plan"}),
    "implement": frozenset({"execution"}),
    "validate": frozenset({"validation"}),
    "route": frozenset({"routing"}),
}


class WorkflowState(BaseModel):
    current_mode: Literal[
        "plan", "implement", "validate", "route", "finished", "blocked"
    ] = "route"
    revision: int = 0
    iteration: int = 0
    max_iterations: int = 50
    mode_switches: int = 0
    max_mode_switches: int = 6
    is_test: bool = False
    prompt_modules_applied: list[str] = Field(default_factory=list)
    final_summary: str = ""

    plan: PlanStateV2 = Field(default_factory=PlanStateV2)
    execution: ExecutionStateV2 = Field(default_factory=ExecutionStateV2)
    validation: ValidationStateV2 = Field(default_factory=ValidationStateV2)
    routing: RoutingStateV2 = Field(default_factory=RoutingStateV2)
    conversation: ConversationStateV2 = Field(default_factory=ConversationStateV2)
    artifact_type: ArtifactTypeState | None = None
    generation_mode: Literal["application", "unresolved"] | None = None
    progress: ProgressStateV2 = Field(default_factory=ProgressStateV2)

    phase_reports: list[PhaseCompletionReport] = Field(default_factory=list)

    resolved_model: dict[str, Any] | None = None
    executed_tool_calls: list[dict] = Field(default_factory=list)

    migration_warnings: list[str] = Field(default_factory=list)

    def next_revision(self) -> int:
        self.revision += 1
        return self.revision

    def submit_phase_report(self, report: PhaseCompletionReport) -> None:
        if report.state_revision != self.revision:
            raise AgentRuntimeError(
                f"PhaseCompletionReport state_revision={report.state_revision} "
                f"与当前 revision={self.revision} 不匹配",
                code=AgentErrorCode.STATE_ERROR,
            )
        owned = _SOURCE_MODE_OWNED_PARTITIONS.get(report.source_mode, frozenset())
        if report.source_mode != "route" and owned and report.source_mode != self.current_mode:
            raise AgentRuntimeError(
                f"模式 {report.source_mode} 无权在当前模式 {self.current_mode} 下提交阶段报告",
                code=AgentErrorCode.STATE_ERROR,
            )
        self.phase_reports.append(report)

    def plan_writes_partition_violation(self, partition: str) -> bool:
        """Plan 模式只允许写入 plan 与 conversation 分区。

        Plan 调用 Implement/Validate/Routing 字段写入工具时返回 True 表示违规。
        """
        if self.current_mode != "plan":
            return False
        return partition not in {"plan", "conversation"}

    def is_plan_hard_limit_reached(self) -> bool:
        return self.plan.reached_hard_limit()


class WorkflowStateEnvelope(BaseModel):
    schema_version: Literal[2, 3] = 3
    workflow: WorkflowState = Field(default_factory=WorkflowState)

    def next_revision(self) -> int:
        return self.workflow.next_revision()
