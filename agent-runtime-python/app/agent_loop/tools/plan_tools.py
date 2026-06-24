"""Phase 3 Plan 专用提交工具。

每个工具都明确只读 / 写哪个 Plan 字段，并在执行前完成状态机门禁。
工具不调用任何文件写入工具、不修改 execution / validation / routing 分区。
"""

import logging
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.agent_loop.state_v2 import (
    CapabilityBundleRef,
    CapabilityRef,
    ConfirmedChoice,
    ConfirmedValue,
    Constraint,
    DesignSpecification,
    ImplementationPlan,
    ImplementationTask,
    PageSpec,
    PlanStateV2,
    PlanTestItem,
    Rationale,
    RequirementBrief,
)
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.tools.plan_tools")


def _resolve_envelope(state_obj: Any) -> Any:
    return getattr(state_obj, "_state_envelope", None)


def _enforce_plan_partition_writable(envelope: Any) -> None:
    """Plan 工具只写 plan 分区；进入工具前显式声明这是 plan 写入。

    所有 plan_tools 只修改 envelope.workflow.plan，因此只要 envelope.current_mode == "plan"
    且 envelope 存在即可。Tool 不会写入 execution / validation / routing 任何字段。
    """
    if envelope is None:
        return
    if envelope.workflow.current_mode != "plan":
        raise AgentRuntimeError(
            f"Plan 工具只能在 current_mode=plan 模式下调用，当前为 {envelope.workflow.current_mode}",
            code=AgentErrorCode.STATE_ERROR,
        )


def _bump_model_call_count(plan_state: PlanStateV2) -> int:
    return plan_state.increment_model_call()


def _ensure_stage(plan_state: PlanStateV2, expected: tuple[str, ...]) -> None:
    if plan_state.plan_stage not in expected:
        raise AgentRuntimeError(
            f"当前 PlanStage={plan_state.plan_stage} 不允许该提交操作；"
            f"需要在 {expected} 阶段进行",
            code=AgentErrorCode.STATE_ERROR,
        )


def _ensure_no_blocked_hard_limit(plan_state: PlanStateV2) -> None:
    if plan_state.reached_hard_limit():
        raise AgentRuntimeError(
            "Plan 模型调用硬上限已到，模型不能再提交推进；只能进入 blocked 或 waiting_for_user",
            code=AgentErrorCode.STATE_ERROR,
        )


def _lines(text: str) -> list[str]:
    """把字符串按换行拆成非空行列表，兼容已传 list 的情况。"""
    if isinstance(text, list):
        return [s.strip() for s in text if isinstance(s, str) and s.strip()]
    return [s.strip() for s in text.split("\n") if s.strip()] if text else []


class SubmitRequirementBriefInput(BaseModel):
    application_direction: str = Field(description="应用方向")
    target_users: str = Field(description="目标用户")
    primary_scenarios: str = Field(default="", description="主要使用场景（多项用换行分隔）")
    functional_scope: str = Field(default="", description="功能范围（多项用换行分隔）")
    content_and_data: str = Field(default="", description="内容与数据需求（多项用换行分隔）")
    responsive_targets: str = Field(default="", description="响应式目标（多项用换行分隔）")
    accessibility_expectations: str = Field(default="", description="可访问性期望（多项用换行分隔）")
    existing_project_constraints: str = Field(default="", description="已有项目约束（多项用换行分隔）")
    technical_constraints: str = Field(default="", description="技术约束（多项用换行分隔）")
    unresolved_questions: str = Field(default="", description="尚未解决的需求问题（多项用换行分隔）")


class SubmitRequirementBriefTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "submit_requirement_brief"
    description: str = (
        "提交结构化需求摘要（RequirementBrief），仅在 discover_direction / discover_scope 阶段使用。"
        "禁止在此工具中包含视觉、配色或具体实现细节。"
    )
    args_schema: Type[BaseModel] = SubmitRequirementBriefInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        application_direction: str = "",
        target_users: str = "",
        primary_scenarios: str = "",
        functional_scope: str = "",
        content_and_data: str = "",
        responsive_targets: str = "",
        accessibility_expectations: str = "",
        existing_project_constraints: str = "",
        technical_constraints: str = "",
        unresolved_questions: str = "",
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        _ensure_stage(plan_state, ("discover_direction", "discover_scope"))
        _ensure_no_blocked_hard_limit(plan_state)
        _bump_model_call_count(plan_state)

        if not application_direction.strip() or not target_users.strip():
            raise AgentRuntimeError(
                "application_direction 与 target_users 必填",
                code=AgentErrorCode.STATE_ERROR,
            )

        brief = RequirementBrief(
            application_direction=ConfirmedValue(
                value=application_direction.strip(),
                source="user",
                confirmed=False,
            ),
            target_users=ConfirmedValue(
                value=target_users.strip(),
                source="user",
                confirmed=False,
            ),
            primary_scenarios=[
                ConfirmedValue(value=v, source="user", confirmed=False)
                for v in _lines(primary_scenarios)
            ],
            functional_scope=[
                ConfirmedValue(value=v, source="user", confirmed=False)
                for v in _lines(functional_scope)
            ],
            content_and_data=[
                ConfirmedValue(value=v, source="user", confirmed=False)
                for v in _lines(content_and_data)
            ],
            responsive_targets=[
                ConfirmedValue(value=v, source="user", confirmed=False)
                for v in _lines(responsive_targets)
            ],
            accessibility_expectations=[
                ConfirmedValue(value=v, source="user", confirmed=False)
                for v in _lines(accessibility_expectations)
            ],
            existing_project_constraints=[
                Constraint(description=v, source="project")
                for v in _lines(existing_project_constraints)
            ],
            technical_constraints=[
                Constraint(description=v, source="project")
                for v in _lines(technical_constraints)
            ],
            unresolved_questions=_lines(unresolved_questions),
        )
        plan_state.requirement_brief = brief
        if plan_state.plan_stage == "discover_direction":
            plan_state.advance_stage("discover_scope")
        envelope.next_revision()
        logger.info(
            "plan_tools | submit_requirement_brief | direction=%s users=%s",
            application_direction,
            target_users,
        )
        return "已记录需求摘要，可继续 discover_scope 阶段；如已涵盖范围，可进入 inspect_existing_project 或 select_skill。"


class RecordProjectInspectionInput(BaseModel):
    decision: str = Field(
        description="inspected 表示已完成只读检查；not_applicable 表示项目为新建"
    )
    summary: str = Field(description="检查总结（最多 1000 字）")
    evidence_files: list[str] = Field(default_factory=list, description="只读检查读取的相对路径")


class RecordProjectInspectionTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "record_project_inspection"
    description: str = (
        "在已有项目修改时记录只读项目检查结果。decision 必须是 inspected 或 not_applicable。"
        "这是 modify 流程进入 select_skill 阶段的硬门禁。"
    )
    args_schema: Type[BaseModel] = RecordProjectInspectionInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        decision: str,
        summary: str,
        evidence_files: list[str] | None = None,
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan

        if plan_state.has_project_inspection():
            raise AgentRuntimeError(
                "project_inspection 已记录，不得重复提交；当前阶段不可回退",
                code=AgentErrorCode.STATE_ERROR,
            )

        _ensure_stage(plan_state, ("discover_scope", "inspect_existing_project"))
        _ensure_no_blocked_hard_limit(plan_state)
        _bump_model_call_count(plan_state)

        if decision not in {"inspected", "not_applicable"}:
            raise AgentRuntimeError(
                "decision 必须是 inspected 或 not_applicable",
                code=AgentErrorCode.STATE_ERROR,
            )
        if decision == "inspected" and not evidence_files:
            raise AgentRuntimeError(
                "inspected 决策必须提供 evidence_files（至少 1 个）",
                code=AgentErrorCode.STATE_ERROR,
            )
        if len(summary) > 1000:
            raise AgentRuntimeError(
                "summary 超过 1000 字限制",
                code=AgentErrorCode.STATE_ERROR,
            )

        plan_state.project_inspection = {
            "decision": decision,
            "summary": summary,
            "evidence_files": list(evidence_files or []),
            "recorded_at_revision": envelope.workflow.revision,
        }
        if plan_state.plan_stage in ("discover_scope", "inspect_existing_project"):
            plan_state.advance_stage("select_skill")
        envelope.next_revision()
        return "项目检查已记录；已进入 select_skill 阶段。"


class ChooseSkillInput(BaseModel):
    skill_id: str = Field(description="Skill ID（来自能力索引）")
    reason: str = Field(description="与需求的对应理由，必须引用需求或项目证据")
    loaded_resources: list[str] = Field(
        default_factory=list, description="本次会话内已加载的资源相对路径"
    )


class ChooseSkillTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "choose_skill"
    description: str = (
        "选择并记录 Skill 引用。仅持久化 ID / digest / loaded_resources，"
        "不写入 Skill 正文。选择工具拒绝启用 Seed/Craft。"
    )
    args_schema: Type[BaseModel] = ChooseSkillInput

    _state: object | None = None
    _skill_registry_provider: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def set_skill_registry_provider(self, provider: object) -> None:
        self._skill_registry_provider = provider

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, skill_id: str, reason: str, loaded_resources: list[str] | None = None) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        _ensure_stage(plan_state, ("select_skill",))
        _ensure_no_blocked_hard_limit(plan_state)
        _bump_model_call_count(plan_state)

        if not plan_state.has_project_inspection():
            raise AgentRuntimeError(
                "project_inspection 尚未记录，不得跳过项目检查直接选择 Skill",
                code=AgentErrorCode.STATE_ERROR,
            )

        if not reason.strip():
            raise AgentRuntimeError(
                "reason 必填：必须说明 Skill 与需求/项目证据的对应关系",
                code=AgentErrorCode.STATE_ERROR,
            )
        if self._skill_registry_provider is None:
            raise AgentRuntimeError(
                "SkillRegistry provider 未配置",
                code=AgentErrorCode.STATE_ERROR,
            )

        from app.capabilities.skills.selector import SkillNotFoundError

        try:
            skill_def, digest, source_path, references = self._skill_registry_provider.resolve_skill(
                skill_id
            )
        except SkillNotFoundError as e:
            raise AgentRuntimeError(
                f"Skill '{skill_id}' 未在索引中找到",
                code=AgentErrorCode.STATE_ERROR,
            ) from e

        # 先固化当前 revision 作为选择时的状态版本，再推进 revision
        revision_at_select = envelope.workflow.revision
        ref = CapabilityRef(
            capability_id=skill_def.id,
            kind="skill",
            source_path=source_path,
            content_digest=digest,
            loaded_resources=list(loaded_resources or references or []),
            selected_reason=reason,
            selected_at_revision=revision_at_select,
            enabled=True,
        )
        plan_state.capability_bundle = CapabilityBundleRef(skills=[ref])
        plan_state.selected_skill_id = skill_def.id
        plan_state.advance_stage("propose_design")
        envelope.next_revision()
        return (
            f"已选择 Skill '{skill_def.name}'（digest={digest[:12]}…），"
            "可进入 propose_design 阶段并加载该 Skill 的规则。"
        )


class ProposeDesignInput(BaseModel):
    information_architecture: list[dict] = Field(
        default_factory=list,
        description="页面级信息架构：[{page_id, name, purpose, primary_actions, components}]",
    )
    visual_direction: str = Field(description="视觉方向描述")
    color_system: str = Field(description="配色系统描述")
    typography: str = Field(description="字体与排版方案")
    component_language: str = Field(description="组件语言/库描述")
    interaction_model: str = Field(description="关键交互模型描述")
    responsive_strategy: str = Field(description="响应式策略描述")
    accessibility_rules: str = Field(default="", description="可访问性规则（多项用换行分隔）")
    content_strategy: str = Field(default="", description="内容策略（多项用换行分隔）")
    design_rationale: list[dict] = Field(
        default_factory=list,
        description="决策理由：[{decision, reason, source_refs}]",
    )
    alternative_options: list[dict] = Field(
        default_factory=list,
        description="每个关键设计维度的备选方案：[{key, option_id, description}]",
    )


class ProposeDesignTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "propose_design"
    description: str = (
        "提交结构化设计建议（DesignSpecification）。design_version 由编排层自动分配；"
        "每个字段必须包含至少 2~3 个备选 option 的差异说明。确认前必须经过 confirm_design 阶段。"
    )
    args_schema: Type[BaseModel] = ProposeDesignInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        information_architecture: list[dict] | None = None,
        visual_direction: str = "",
        color_system: str = "",
        typography: str = "",
        component_language: str = "",
        interaction_model: str = "",
        responsive_strategy: str = "",
        accessibility_rules: str = "",
        content_strategy: str = "",
        design_rationale: list[dict] | None = None,
        alternative_options: list[dict] | None = None,
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        _ensure_stage(plan_state, ("propose_design", "select_skill"))
        _ensure_no_blocked_hard_limit(plan_state)
        _bump_model_call_count(plan_state)

        for field_name in (
            "visual_direction",
            "color_system",
            "typography",
            "component_language",
            "interaction_model",
            "responsive_strategy",
        ):
            value = locals().get(field_name, "")
            if not value or not value.strip():
                raise AgentRuntimeError(
                    f"{field_name} 必填：每个关键设计维度都必须有具体描述",
                    code=AgentErrorCode.STATE_ERROR,
                )

        alternatives = list(alternative_options or [])
        if not alternatives:
            raise AgentRuntimeError(
                "每个关键设计维度必须至少给出 2~3 个互斥候选，请在 alternative_options 中提供",
                code=AgentErrorCode.STATE_ERROR,
            )

        def _build_choice(text: str, alt_key: str) -> ConfirmedChoice:
            alts = [a for a in alternatives if a.get("key") == alt_key]
            return ConfirmedChoice(
                selected_option_id=None,
                description=text,
                source="user",
                confirmed=False,
                alternative_option_ids=[a.get("option_id", "") for a in alts],
                rationale="",
            )

        spec = DesignSpecification(
            design_version=plan_state.design_spec_revision + 1,
            information_architecture=[
                _build_page_spec(p) for p in (information_architecture or [])
            ],
            visual_direction=_build_choice(visual_direction, "visual_direction"),
            color_system=_build_choice(color_system, "color_system"),
            typography=_build_choice(typography, "typography"),
            component_language=_build_choice(component_language, "component_language"),
            interaction_model=_build_choice(interaction_model, "interaction_model"),
            responsive_strategy=_build_choice(responsive_strategy, "responsive_strategy"),
            accessibility_rules=[s.strip() for s in accessibility_rules.split("\n") if s.strip()] if accessibility_rules else [],
            content_strategy=[s.strip() for s in content_strategy.split("\n") if s.strip()] if content_strategy else [],
            design_rationale=[
                _build_rationale(r) for r in (design_rationale or [])
            ],
            confirmation_message_id=None,
            confirmed=False,
            confirmed_at=None,
        )
        plan_state.design_specification = spec
        plan_state.design_spec_revision = spec.design_version
        plan_state.advance_stage("confirm_design")
        envelope.next_revision()

        if hasattr(self._state, "conversation_messages"):
            self._state.conversation_messages.append({
                "role": "system",
                "source": "plan",
                "content": (
                    "提交的设计方案摘要（供 ask_user 时直接引用）：\n"
                    f"- 视觉方向：{visual_direction}\n"
                    f"- 配色系统：{color_system}\n"
                    f"- 字体排版：{typography}\n"
                    f"- 组件语言：{component_language}\n"
                    f"- 交互模型：{interaction_model}\n"
                    f"- 响应式策略：{responsive_strategy}"
                ),
            })

        return (
            "设计建议已提交，等待用户确认。请在回复中完整展示所有维度与备选，"
            "然后调用 ask_user 让用户在 '没有需要调整' 和 '需要调整' 之间选择。"
        )


def _build_page_spec(raw: dict) -> PageSpec:
    if not isinstance(raw, dict):
        raise AgentRuntimeError(
            "information_architecture 中的页面必须是对象",
            code=AgentErrorCode.STATE_ERROR,
        )
    required = {"page_id", "name", "purpose"}
    missing = required - set(raw.keys())
    if missing:
        raise AgentRuntimeError(
            f"information_architecture 页面缺少必填字段: {missing}",
            code=AgentErrorCode.STATE_ERROR,
        )
    return PageSpec(
        page_id=str(raw["page_id"]),
        name=str(raw["name"]),
        purpose=str(raw["purpose"]),
        primary_actions=[str(p) for p in raw.get("primary_actions", []) or []],
        components=[str(c) for c in raw.get("components", []) or []],
    )


def _build_rationale(raw: dict) -> Rationale:
    if not isinstance(raw, dict):
        raise AgentRuntimeError(
            "design_rationale 中每条理由必须是对象",
            code=AgentErrorCode.STATE_ERROR,
        )
    if "decision" not in raw or "reason" not in raw:
        raise AgentRuntimeError(
            "rationale 必须包含 decision 和 reason 字段",
            code=AgentErrorCode.STATE_ERROR,
        )
    return Rationale(
        decision=str(raw["decision"]),
        reason=str(raw["reason"]),
        source_refs=[str(s) for s in raw.get("source_refs", []) or []],
    )


class ConfirmDesignInput(BaseModel):
    message_id: str = Field(description="用户对设计最终确认的消息 ID")


class ConfirmDesignTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "confirm_design"
    description: str = (
        "由用户消息触发的设计确认工具。模型不得自己调用；调用必须由编排层在收到用户"
        "明确肯定（如'没有需要调整'、'可以'、'按这个方案'）后自动提交。"
    )
    args_schema: Type[BaseModel] = ConfirmDesignInput

    _state: object | None = None
    _orchestrator_only: bool = True

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, message_id: str) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        if plan_state.design_specification is None:
            raise AgentRuntimeError(
                "design_specification 尚未提交，无法确认",
                code=AgentErrorCode.STATE_ERROR,
            )
        if not message_id.strip():
            raise AgentRuntimeError(
                "message_id 必填：必须可追溯到具体用户消息",
                code=AgentErrorCode.STATE_ERROR,
            )

        # 如果已经进入 write_implementation_plan 或 completed，说明设计已确认
        if plan_state.plan_stage not in ("confirm_design",):
            return (
                "设计已经确认过了。当前 PlanStage 为 "
                + plan_state.plan_stage
                + "，请根据当前阶段提交对应内容，不要再调用确认工具。"
            )

        _ensure_design_asked_user(self._state)

        spec = plan_state.design_specification
        spec.confirmed = True
        spec.confirmation_message_id = message_id.strip()
        spec.confirmed_at = _now_iso()
        plan_state.design_specification = spec
        plan_state.advance_stage("write_implementation_plan")
        envelope.next_revision()
        return "设计已确认，可进入 write_implementation_plan 阶段并立即生成实施计划。"


def _ensure_design_asked_user(state: object) -> None:
    """检查在 design_confirm 阶段是否已通过 ask_user 询问用户意见。"""
    questions = getattr(state, "clarification_questions", None) or []
    has_design_question = any(
        isinstance(q, dict) and q.get("stage") == "design_confirm"
        for q in questions
    )
    if has_design_question:
        return
    from app.core.error_codes import AgentErrorCode
    raise AgentRuntimeError(
        "设计确认前必须先通过 ask_user 向用户展示设计方案并获取反馈。"
        "请先调用 ask_user(stage='design_confirm', questions=[...]) 让用户选择，"
        "用户回复确认后再调用 confirm_design。",
        code=AgentErrorCode.STATE_ERROR,
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class WriteImplementationPlanInput(BaseModel):
    tasks: list[dict] = Field(
        ...,
        description=(
            "ImplementationTask 列表：每项包含 task_id, goal, allowed_files, prohibited_files, "
            "dependencies, inputs, outputs, test_requirements, acceptance_criteria"
        ),
    )
    test_plan: list[dict] = Field(default_factory=list, description="TestRequirement 列表")
    acceptance_criteria: list[str] = Field(default_factory=list)
    prohibited_changes: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="一句话摘要（最多 200 字）")


class WriteImplementationPlanTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "write_implementation_plan"
    description: str = (
        "在 write_implementation_plan 阶段调用，将结构化 ImplementationPlan 写入状态。"
        "不写项目文件；不修改 Plan 设计。"
    )
    args_schema: Type[BaseModel] = WriteImplementationPlanInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        tasks: list[dict],
        test_plan: list[dict] | None = None,
        acceptance_criteria: list[str] | None = None,
        prohibited_changes: list[str] | None = None,
        summary: str = "",
    ) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        _ensure_stage(plan_state, ("write_implementation_plan",))
        _ensure_no_blocked_hard_limit(plan_state)
        _bump_model_call_count(plan_state)

        if plan_state.design_specification is None or not plan_state.design_specification.confirmed:
            raise AgentRuntimeError(
                "DesignSpecification 未确认前不得生成实施计划",
                code=AgentErrorCode.STATE_ERROR,
            )

        impl_tasks = [_build_implementation_task(t) for t in tasks]
        impl_tests = [_build_test_requirement(t) for t in (test_plan or [])]
        design_version = plan_state.design_specification.design_version

        plan_model = ImplementationPlan(
            plan_version=plan_state.implementation_plan_revision + 1,
            source_design_version=design_version,
            tasks=impl_tasks,
            test_plan=impl_tests,
            acceptance_criteria=list(acceptance_criteria or []),
            prohibited_changes=list(prohibited_changes or []),
            summary=summary[:200],
        )
        plan_state.implementation_plan = plan_model
        plan_state.implementation_plan_revision = plan_model.plan_version
        plan_state.advance_stage("completed")
        plan_state.plan_just_finished = True
        from app.agent_loop.state import AgentLoopState as _AgentLoopState

        if isinstance(self._state, _AgentLoopState):
            self._state.plan_just_finished = True
            self._state.implementation_outline = {"text": summary[:200] or "实施计划已写入", "tasks": len(impl_tasks)}
        envelope.next_revision()
        return (
            f"已写入 ImplementationPlan v{plan_model.plan_version}（来源设计版本 v{design_version}），"
            "Plan 阶段完成；编排层将进入 Route 决定下一阶段。"
        )


def _build_implementation_task(raw: dict) -> ImplementationTask:
    if not isinstance(raw, dict):
        raise AgentRuntimeError(
            "ImplementationTask 必须是对象",
            code=AgentErrorCode.STATE_ERROR,
        )
    required = {"task_id", "goal", "allowed_files"}
    missing = required - set(raw.keys())
    if missing:
        raise AgentRuntimeError(
            f"ImplementationTask 缺少必填字段: {missing}",
            code=AgentErrorCode.STATE_ERROR,
        )
    return ImplementationTask(
        task_id=str(raw["task_id"]),
        goal=str(raw["goal"]),
        allowed_files=[str(p) for p in raw.get("allowed_files", []) or []],
        prohibited_files=[str(p) for p in raw.get("prohibited_files", []) or []],
        dependencies=[str(d) for d in raw.get("dependencies", []) or []],
        inputs=[str(i) for i in raw.get("inputs", []) or []],
        outputs=[str(o) for o in raw.get("outputs", []) or []],
        test_requirements=[
            str(t) for t in raw.get("test_requirements", []) or []
        ],
        acceptance_criteria=[
            str(a) for a in raw.get("acceptance_criteria", []) or []
        ],
    )


def _build_test_requirement(raw: dict) -> PlanTestItem:
    if not isinstance(raw, dict):
        raise AgentRuntimeError(
            "TestRequirement 必须是对象",
            code=AgentErrorCode.STATE_ERROR,
        )
    required = {"test_id", "description", "target", "expected"}
    missing = required - set(raw.keys())
    if missing:
        raise AgentRuntimeError(
            f"TestRequirement 缺少必填字段: {missing}",
            code=AgentErrorCode.STATE_ERROR,
        )
    return PlanTestItem(
        test_id=str(raw["test_id"]),
        description=str(raw["description"]),
        target=str(raw["target"]),
        expected=str(raw["expected"]),
    )


class PlanStageGuardInput(BaseModel):
    reason: str = Field(description="blocked 或 waiting_for_user 的具体原因")
    target: str = Field(description="blocked | waiting_for_user")


class PlanStageGuardTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "plan_stage_guard"
    description: str = (
        "Plan 阶段用于进入 blocked 或 waiting_for_user。模型在硬上限、需求未澄清或无法推进时调用。"
        "不得用于伪装推进；不得直接调用以进入 implement。"
    )
    args_schema: Type[BaseModel] = PlanStageGuardInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, **_kwargs: Any) -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, reason: str, target: str) -> str:
        if self._state is None:
            raise AgentRuntimeError(
                "未绑定 AgentLoopState",
                code=AgentErrorCode.STATE_ERROR,
            )
        envelope = _resolve_envelope(self._state)
        if envelope is None:
            raise AgentRuntimeError(
                "WorkflowStateEnvelope 未初始化",
                code=AgentErrorCode.STATE_ERROR,
            )
        if target not in {"blocked", "waiting_for_user"}:
            raise AgentRuntimeError(
                "target 必须是 blocked 或 waiting_for_user",
                code=AgentErrorCode.STATE_ERROR,
            )
        _enforce_plan_partition_writable(envelope)
        plan_state: PlanStateV2 = envelope.workflow.plan
        plan_state.plan_stage = target
        from app.agent_loop.state import AgentLoopState

        if isinstance(self._state, AgentLoopState):
            if target == "waiting_for_user":
                self._state.status = "waiting_for_user"
                plan_state.is_waiting_for_user = True
            else:
                self._state.status = "failed"
                plan_state.is_waiting_for_user = False
        envelope.next_revision()
        return f"已记录 Plan 进入 {target}（原因：{reason[:120]}）。"


__all__ = [
    "SubmitRequirementBriefTool",
    "RecordProjectInspectionTool",
    "ChooseSkillTool",
    "ProposeDesignTool",
    "ConfirmDesignTool",
    "WriteImplementationPlanTool",
    "PlanStageGuardTool",
    "PLAN_STAGE_GUARD_REJECTED_CODE",
    "PlanStageGuardRejected",
]

PLAN_STAGE_GUARD_REJECTED_CODE = "PLAN_STAGE_GUARD_REJECTED"


class PlanStageGuardRejected(AgentRuntimeError):
    """Plan 阶段机门禁拒绝的特定异常。"""


def reject_plan_stage_violation(message: str) -> None:
    raise PlanStageGuardRejected(
        message,
        code=AgentErrorCode.STATE_ERROR,
    )
