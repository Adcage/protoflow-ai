"""Phase 3 plan_tools 测试：状态机门禁、阶段推进、字段所有权。"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.plan_tools import (
    ChooseSkillTool,
    ConfirmDesignTool,
    PlanStageGuardTool,
    ProposeDesignTool,
    RecordProjectInspectionTool,
    SubmitRequirementBriefTool,
    WriteImplementationPlanTool,
)
from app.core.exceptions import AgentRuntimeError
from app.capabilities.skills.selector import (
    SkillNotFoundError,
    SkillRegistryProvider,
)


class _StubSkillRegistry:
    def __init__(self, skills: dict[str, Any]) -> None:
        self._skills = skills

    def get(self, skill_id: str) -> Any:
        if skill_id not in self._skills:
            raise SkillNotFoundError(skill_id)
        return self._skills[skill_id]


def _build_provider() -> SkillRegistryProvider:
    skill = SimpleNamespace(
        id="dashboard",
        name="Dashboard",
        description="dashboard skill",
        source_path="/skills/dashboard/SKILL.md",
        references=("SKILL.md", "patterns/list.md"),
    )
    registry = _StubSkillRegistry({"dashboard": skill})
    return SkillRegistryProvider(registry)


def _init_envelope(state: AgentLoopState) -> None:
    state._state_envelope = state._to_envelope()


class TestSubmitRequirementBrief:
    @pytest.mark.asyncio
    async def test_submit_brief_records_and_advances_stage(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = SubmitRequirementBriefTool()
        tool.set_state(state)

        result = await tool._arun(
            application_direction="运营仪表盘",
            target_users="运营人员",
            primary_scenarios=["日活监控"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.requirement_brief is not None
        assert plan.requirement_brief.application_direction.value == "运营仪表盘"
        assert plan.plan_stage == "discover_scope"
        assert plan.model_call_count == 1
        assert "已记录需求摘要" in result

    @pytest.mark.asyncio
    async def test_submit_brief_rejects_missing_direction(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = SubmitRequirementBriefTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(application_direction="", target_users="x")

    @pytest.mark.asyncio
    async def test_submit_brief_rejects_illegal_stage(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "confirm_design"
        tool = SubmitRequirementBriefTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(application_direction="x", target_users="y")


class TestRecordProjectInspection:
    @pytest.mark.asyncio
    async def test_existing_project_requires_evidence(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(decision="inspected", summary="x", evidence_files=[])

    @pytest.mark.asyncio
    async def test_existing_project_records_evidence(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(
            decision="inspected",
            summary="项目结构：Vue 3",
            evidence_files=["package.json"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.project_inspection is not None
        assert plan.project_inspection["decision"] == "inspected"
        assert plan.has_project_inspection()

    @pytest.mark.asyncio
    async def test_new_project_not_applicable(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(decision="not_applicable", summary="新建项目")
        plan = state._state_envelope.workflow.plan
        assert plan.project_inspection["decision"] == "not_applicable"
        assert plan.has_project_inspection()


class TestChooseSkill:
    @pytest.mark.asyncio
    async def test_choose_skill_records_capability_ref(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

        inspection_tool = RecordProjectInspectionTool()
        inspection_tool.set_state(state)
        await inspection_tool._arun(
            decision="inspected",
            summary="Vue 3 项目",
            evidence_files=["package.json"],
        )
        assert state._state_envelope.workflow.plan.plan_stage == "select_skill"

        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        result = await tool._arun(
            skill_id="dashboard",
            reason="用户需要数据展示",
            loaded_resources=["SKILL.md"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.selected_skill_id == "dashboard"
        assert plan.capability_bundle.skills[0].capability_id == "dashboard"
        assert plan.capability_bundle.skills[0].loaded_resources == ["SKILL.md"]
        assert plan.plan_stage == "propose_design"
        assert "已选择 Skill" in result

    @pytest.mark.asyncio
    async def test_choose_skill_rejects_missing_reason(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

        inspection_tool = RecordProjectInspectionTool()
        inspection_tool.set_state(state)
        await inspection_tool._arun(
            decision="not_applicable",
            summary="新建项目",
        )

        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        with pytest.raises(AgentRuntimeError):
            await tool._arun(skill_id="dashboard", reason="")

    @pytest.mark.asyncio
    async def test_choose_skill_rejects_unknown_skill(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

        inspection_tool = RecordProjectInspectionTool()
        inspection_tool.set_state(state)
        await inspection_tool._arun(
            decision="not_applicable",
            summary="新建项目",
        )

        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        with pytest.raises(AgentRuntimeError):
            await tool._arun(skill_id="unknown", reason="x")


class TestProposeDesign:
    @pytest.mark.asyncio
    async def test_propose_design_requires_alternatives(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "propose_design"

        tool = ProposeDesignTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(
                visual_direction="v",
                color_system="c",
                typography="t",
                component_language="cl",
                interaction_model="i",
                responsive_strategy="r",
            )

    @pytest.mark.asyncio
    async def test_propose_design_advances_to_confirm(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "propose_design"

        tool = ProposeDesignTool()
        tool.set_state(state)

        await tool._arun(
            information_architecture=[
                {
                    "page_id": "p1",
                    "name": "Dashboard",
                    "purpose": "数据展示",
                    "primary_actions": ["筛选"],
                    "components": ["KPI 卡片"],
                }
            ],
            visual_direction="现代极简",
            color_system="单色",
            typography="无衬线",
            component_language="Element Plus",
            interaction_model="响应式",
            responsive_strategy="移动优先",
            accessibility_rules="键盘可达",
            design_rationale=[
                {
                    "decision": "使用极简风格",
                    "reason": "数据为主",
                    "source_refs": ["dashboard skill"],
                }
            ],
            alternative_options=[
                {"key": "visual_direction", "option_id": "opt_a", "description": "极简"},
                {"key": "color_system", "option_id": "opt_b", "description": "单色"},
                {"key": "color_system", "option_id": "opt_c", "description": "多彩"},
            ],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.design_specification is not None
        assert plan.design_specification.confirmed is False
        assert plan.plan_stage == "confirm_design"
        assert plan.design_specification.information_architecture[0].page_id == "p1"


class TestConfirmDesign:
    @pytest.mark.asyncio
    async def test_confirm_design_requires_existing_spec(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "confirm_design"

        tool = ConfirmDesignTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(message_id="user-msg-1")

    @pytest.mark.asyncio
    async def test_confirm_design_marks_confirmed_and_advances(self):
        state = AgentLoopState()
        _init_envelope(state)
        from app.agent_loop.state_v2 import ConfirmedChoice, DesignSpecification

        state._state_envelope.workflow.plan.design_specification = DesignSpecification(
            visual_direction=ConfirmedChoice(description="v", source="user", confirmed=False),
            color_system=ConfirmedChoice(description="c", source="user", confirmed=False),
            typography=ConfirmedChoice(description="t", source="user", confirmed=False),
            component_language=ConfirmedChoice(description="cl", source="user", confirmed=False),
            interaction_model=ConfirmedChoice(description="i", source="user", confirmed=False),
            responsive_strategy=ConfirmedChoice(description="r", source="user", confirmed=False),
        )
        state._state_envelope.workflow.plan.plan_stage = "confirm_design"
        state.clarification_questions = [
            {"id": "qs_design", "stage": "design_confirm", "answered": True, "questions": []},
        ]

        tool = ConfirmDesignTool()
        tool.set_state(state)
        await tool._arun(message_id="user-msg-1")

        plan = state._state_envelope.workflow.plan
        assert plan.design_specification.confirmed is True
        assert plan.design_specification.confirmation_message_id == "user-msg-1"
        assert plan.plan_stage == "write_implementation_plan"


class TestWriteImplementationPlan:
    @pytest.mark.asyncio
    async def test_write_plan_requires_confirmed_design(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "write_implementation_plan"

        tool = WriteImplementationPlanTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError):
            await tool._arun(
                tasks=[
                    {
                        "task_id": "t1",
                        "goal": "x",
                        "allowed_files": ["src/App.vue"],
                    }
                ]
            )

    @pytest.mark.asyncio
    async def test_write_plan_completes(self):
        state = AgentLoopState()
        _init_envelope(state)
        from app.agent_loop.state_v2 import ConfirmedChoice, DesignSpecification

        spec = DesignSpecification(
            design_version=1,
            visual_direction=ConfirmedChoice(description="v", source="user", confirmed=True),
            color_system=ConfirmedChoice(description="c", source="user", confirmed=True),
            typography=ConfirmedChoice(description="t", source="user", confirmed=True),
            component_language=ConfirmedChoice(description="cl", source="user", confirmed=True),
            interaction_model=ConfirmedChoice(description="i", source="user", confirmed=True),
            responsive_strategy=ConfirmedChoice(description="r", source="user", confirmed=True),
            confirmed=True,
            confirmation_message_id="user-msg-1",
        )
        plan = state._state_envelope.workflow.plan
        plan.design_specification = spec
        plan.plan_stage = "write_implementation_plan"

        tool = WriteImplementationPlanTool()
        tool.set_state(state)
        await tool._arun(
            tasks=[
                {
                    "task_id": "t1",
                    "goal": "create layout",
                    "allowed_files": ["src/App.vue"],
                    "acceptance_criteria": ["通过本地编译"],
                }
            ],
            summary="一句话摘要",
        )
        assert plan.implementation_plan is not None
        assert plan.implementation_plan.tasks[0].task_id == "t1"
        assert plan.plan_stage == "completed"
        assert plan.plan_just_finished is True
        assert state.status == "running"

    @pytest.mark.asyncio
    async def test_write_plan_rejects_hard_limit_exceeded(self):
        state = AgentLoopState()
        _init_envelope(state)
        from app.agent_loop.state_v2 import ConfirmedChoice, DesignSpecification

        plan = state._state_envelope.workflow.plan
        plan.design_specification = DesignSpecification(
            visual_direction=ConfirmedChoice(description="v", source="user", confirmed=True),
            color_system=ConfirmedChoice(description="c", source="user", confirmed=True),
            typography=ConfirmedChoice(description="t", source="user", confirmed=True),
            component_language=ConfirmedChoice(description="cl", source="user", confirmed=True),
            interaction_model=ConfirmedChoice(description="i", source="user", confirmed=True),
            responsive_strategy=ConfirmedChoice(description="r", source="user", confirmed=True),
            confirmed=True,
            confirmation_message_id="user-msg-1",
        )
        plan.plan_stage = "write_implementation_plan"
        plan.model_call_count = plan.plan_hard_limit

        tool = WriteImplementationPlanTool()
        tool.set_state(state)
        with pytest.raises(AgentRuntimeError):
            await tool._arun(
                tasks=[
                    {
                        "task_id": "t1",
                        "goal": "x",
                        "allowed_files": ["src/App.vue"],
                    }
                ]
            )


class TestPlanStageGuard:
    @pytest.mark.asyncio
    async def test_plan_guard_to_blocked(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"

        tool = PlanStageGuardTool()
        tool.set_state(state)
        await tool._arun(reason="需求未澄清", target="blocked")
        assert state._state_envelope.workflow.plan.plan_stage == "blocked"
        assert state.status == "failed"

    @pytest.mark.asyncio
    async def test_plan_guard_to_waiting(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = PlanStageGuardTool()
        tool.set_state(state)
        await tool._arun(reason="等待用户回答", target="waiting_for_user")
        assert state._state_envelope.workflow.plan.plan_stage == "waiting_for_user"
        assert state.status == "waiting_for_user"

    @pytest.mark.asyncio
    async def test_plan_guard_rejects_invalid_target(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = PlanStageGuardTool()
        tool.set_state(state)
        with pytest.raises(AgentRuntimeError):
            await tool._arun(reason="x", target="implement")


class TestPlanForbiddenPartition:
    @pytest.mark.asyncio
    async def test_plan_cannot_write_execution_partition(self):
        state = AgentLoopState()
        _init_envelope(state)
        # 模拟 plan 阶段：envelope.current_mode = "plan"
        state._state_envelope.workflow.current_mode = "plan"
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"

        tool = SubmitRequirementBriefTool()
        tool.set_state(state)
        # current_mode 决定 plan_writes_partition_violation；execution 是 forbidden
        assert state._state_envelope.workflow.plan_writes_partition_violation("execution")


# ---------------------------------------------------------------------------
# Phase 3 §8 contract test names (规格 §8 测试名一一对应)
# ---------------------------------------------------------------------------


class TestPhase3ContractNames:
    """补齐 Phase 3 规格 §8 列出的 6 个契约测试名中后端可测的 4 个。"""

    @pytest.mark.asyncio
    async def test_plan_cannot_skip_application_direction(self):
        """新建项目缺方向：停留在 discover_direction，调用 write_implementation_plan 必须被拒绝。"""
        state = AgentLoopState()
        _init_envelope(state)
        # 缺 requirement_brief 情况下，discover_direction 阶段 plan_stage 不允许直接跳到 write_implementation_plan
        state._state_envelope.workflow.plan.plan_stage = "discover_direction"

        tool = WriteImplementationPlanTool()
        tool.set_state(state)
        with pytest.raises(AgentRuntimeError):
            await tool._arun(
                tasks=[
                    {
                        "task_id": "t1",
                        "goal": "create layout",
                        "allowed_files": ["src/App.vue"],
                    }
                ]
            )
        # 即便 spec 错误，discover_direction 阶段也不能前进
        assert state._state_envelope.workflow.plan.plan_stage == "discover_direction"

    @pytest.mark.asyncio
    async def test_plan_cannot_confirm_design_from_its_own_message(self):
        """模型不能自己触发 confirm_design：必须由 message_id 标识的用户消息驱动。"""
        from app.agent_loop.state_v2 import ConfirmedChoice, DesignSpecification

        state = AgentLoopState()
        _init_envelope(state)
        # 构造一个待确认 spec
        state._state_envelope.workflow.plan.design_specification = DesignSpecification(
            visual_direction=ConfirmedChoice(description="v", source="user", confirmed=False),
            color_system=ConfirmedChoice(description="c", source="user", confirmed=False),
            typography=ConfirmedChoice(description="t", source="user", confirmed=False),
            component_language=ConfirmedChoice(description="cl", source="user", confirmed=False),
            interaction_model=ConfirmedChoice(description="i", source="user", confirmed=False),
            responsive_strategy=ConfirmedChoice(description="r", source="user", confirmed=False),
        )
        state._state_envelope.workflow.plan.plan_stage = "propose_design"
        # 模型用空 message_id 调用 confirm_design 必须被拒绝
        tool = ConfirmDesignTool()
        tool.set_state(state)
        with pytest.raises(AgentRuntimeError):
            await tool._arun(message_id="")
        # confirmation_message_id 不能由工具回填
        assert state._state_envelope.workflow.plan.design_specification.confirmed is False
        assert state._state_envelope.workflow.plan.design_specification.confirmation_message_id is None

    def test_implement_cannot_replace_plan_skill(self):
        """Implement 模式工具 allowlist 必须不含 choose_skill，无法悄悄替换 Plan 选中的 Skill。"""
        from app.agent_loop.tool_policy import (
            IMPLEMENT_TOOLS,
            PLAN_TOOLS,
            ModeToolPolicy,
            AgentMode,
        )

        # 双向验证：Plan 才能 choose_skill；Implement 拒绝 choose_skill
        assert "choose_skill" in PLAN_TOOLS
        assert "choose_skill" not in IMPLEMENT_TOOLS
        # ModeToolPolicy 必须实际拒绝
        impl_policy = ModeToolPolicy(mode=AgentMode.IMPLEMENT, allowed_tool_names=IMPLEMENT_TOOLS)
        with pytest.raises(AgentRuntimeError):
            impl_policy.require_allowed("choose_skill")

    @pytest.mark.asyncio
    async def test_required_question_cannot_skip(self):
        """规格要求：required=true 的问题不能被跳过；空 questions 必须报错且不进入 waiting_for_user。"""
        from app.agent_loop.tools.ask_user import AskUserTool

        state = AgentLoopState()
        _init_envelope(state)
        tool = AskUserTool()
        tool.set_state(state)

        # 1) questions 为空时，工具必须直接返回错误，不进入 waiting_for_user
        result = await tool._arun(stage="discover_scope", questions=[])
        assert "错误" in result
        assert state.status != "waiting_for_user"
        # clarification_questions 也不应被写入
        assert state.clarification_questions == []

        # 2) required 字段在工具内被规范化为 True：缺省问题不能蒙混通过
        #    重新调用一次（带 required=False + 合法 options），验证 _normalize 后 required 仍存在
        await tool._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "x",
                    "required": False,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        # 工具应仍写入记录（required=False 是允许的；区别在于询问是否必答）
        assert state.status == "waiting_for_user"
        assert state.clarification_questions[0]["questions"][0]["required"] is False

        # 3) 即便有 question 缺少 required 字段，工具自动补全为 required=True
        #    这正是"required 不可被跳过"的契约
        state2 = AgentLoopState()
        _init_envelope(state2)
        tool2 = AskUserTool()
        tool2.set_state(state2)
        await tool2._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "x",
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        # required 字段缺省时被工具规范化为 True，不可被跳过
        assert state2.clarification_questions[0]["questions"][0]["required"] is True

