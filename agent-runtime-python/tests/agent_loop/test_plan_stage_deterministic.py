"""Task 3R-2: PlanStage 确定性迁移和重复提交门禁测试。

验证：
1. 新建项目 not_applicable 确定性推进到 select_skill
2. inspected 必须提供 evidence_files
3. 重复提交 project_inspection 被拒绝
4. 暂停恢复后不能覆盖已记录的 project_inspection
5. 选择 Skill 后不能回退到 inspection 阶段
"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.plan_tools import (
    ChooseSkillTool,
    RecordProjectInspectionTool,
)
from app.capabilities.skills.selector import (
    SkillNotFoundError,
    SkillRegistryProvider,
)
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


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


class TestRecordNewProjectInspectionAdvancesToSelectSkill:
    @pytest.mark.asyncio
    async def test_not_applicable_from_discover_scope_advances_to_select_skill(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        result = await tool._arun(decision="not_applicable", summary="新建项目，无需检查")
        plan = state._state_envelope.workflow.plan
        assert plan.project_inspection["decision"] == "not_applicable"
        assert plan.has_project_inspection()
        assert plan.plan_stage == "select_skill"
        assert "已进入 select_skill" in result

    @pytest.mark.asyncio
    async def test_not_applicable_from_inspect_existing_project_advances_to_select_skill(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        result = await tool._arun(decision="not_applicable", summary="空工作区，无需检查")
        plan = state._state_envelope.workflow.plan
        assert plan.project_inspection["decision"] == "not_applicable"
        assert plan.has_project_inspection()
        assert plan.plan_stage == "select_skill"
        assert "已进入 select_skill" in result

    @pytest.mark.asyncio
    async def test_inspected_from_inspect_existing_project_advances_to_select_skill(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        result = await tool._arun(
            decision="inspected",
            summary="Vue 3 + Element Plus 项目",
            evidence_files=["package.json", "src/main.ts"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.project_inspection["decision"] == "inspected"
        assert plan.project_inspection["evidence_files"] == ["package.json", "src/main.ts"]
        assert plan.has_project_inspection()
        assert plan.plan_stage == "select_skill"
        assert "已进入 select_skill" in result


class TestRecordExistingProjectRequiresEvidenceFiles:
    @pytest.mark.asyncio
    async def test_inspected_without_evidence_rejected(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(decision="inspected", summary="已检查", evidence_files=[])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    @pytest.mark.asyncio
    async def test_inspected_with_evidence_accepted(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(
            decision="inspected",
            summary="已检查",
            evidence_files=["src/App.vue"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.has_project_inspection()
        assert plan.plan_stage == "select_skill"


class TestRecordProjectInspectionRejectsDuplicateAfterAdvance:
    @pytest.mark.asyncio
    async def test_second_call_rejected_after_first_succeeds(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(
            decision="inspected",
            summary="第一次检查",
            evidence_files=["package.json"],
        )
        plan = state._state_envelope.workflow.plan
        assert plan.plan_stage == "select_skill"
        revision_after_first = state._state_envelope.workflow.revision

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(
                decision="inspected",
                summary="重复检查",
                evidence_files=["package.json"],
            )
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR
        assert "不得重复提交" in exc_info.value.message
        assert state._state_envelope.workflow.plan.plan_stage == "select_skill"
        assert state._state_envelope.workflow.revision == revision_after_first
        assert plan.project_inspection["summary"] == "第一次检查"

    @pytest.mark.asyncio
    async def test_not_applicable_duplicate_rejected(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(decision="not_applicable", summary="新建项目")
        plan = state._state_envelope.workflow.plan
        assert plan.plan_stage == "select_skill"

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(decision="not_applicable", summary="再次提交")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR
        assert "不得重复提交" in exc_info.value.message


class TestStaleResumeCannotOverwriteProjectInspection:
    @pytest.mark.asyncio
    async def test_resume_attempt_rejected(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = RecordProjectInspectionTool()
        tool.set_state(state)

        await tool._arun(
            decision="inspected",
            summary="原始检查",
            evidence_files=["src/main.ts"],
        )
        original_inspection = state._state_envelope.workflow.plan.project_inspection.copy()
        original_revision = state._state_envelope.workflow.revision

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(
                decision="not_applicable",
                summary="恢复时尝试覆盖",
            )
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR
        assert state._state_envelope.workflow.plan.project_inspection == original_inspection
        assert state._state_envelope.workflow.revision == original_revision


class TestSelectSkillCannotRewindInspectionStage:
    @pytest.mark.asyncio
    async def test_choose_skill_rejects_inspect_existing_project_stage(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"
        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(skill_id="dashboard", reason="需要数据展示")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    @pytest.mark.asyncio
    async def test_choose_skill_rejects_discover_scope_stage(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "discover_scope"
        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(skill_id="dashboard", reason="需要数据展示")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    @pytest.mark.asyncio
    async def test_choose_skill_rejects_without_project_inspection(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "select_skill"
        assert not state._state_envelope.workflow.plan.has_project_inspection()

        tool = ChooseSkillTool()
        tool.set_state(state)
        tool.set_skill_registry_provider(_build_provider())

        with pytest.raises(AgentRuntimeError) as exc_info:
            await tool._arun(skill_id="dashboard", reason="需要数据展示")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR
        assert "project_inspection 尚未记录" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_choose_skill_succeeds_after_inspection(self):
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

        skill_tool = ChooseSkillTool()
        skill_tool.set_state(state)
        skill_tool.set_skill_registry_provider(_build_provider())

        result = await skill_tool._arun(skill_id="dashboard", reason="需要数据展示")
        plan = state._state_envelope.workflow.plan
        assert plan.selected_skill_id == "dashboard"
        assert plan.plan_stage == "propose_design"
        assert "已选择 Skill" in result

    @pytest.mark.asyncio
    async def test_cannot_go_back_to_inspection_after_skill_selected(self):
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

        skill_tool = ChooseSkillTool()
        skill_tool.set_state(state)
        skill_tool.set_skill_registry_provider(_build_provider())
        await skill_tool._arun(skill_id="dashboard", reason="需要数据展示")
        assert state._state_envelope.workflow.plan.plan_stage == "propose_design"

        reinspection_tool = RecordProjectInspectionTool()
        reinspection_tool.set_state(state)
        with pytest.raises(AgentRuntimeError) as exc_info:
            await reinspection_tool._arun(
                decision="inspected",
                summary="尝试回退",
                evidence_files=["package.json"],
            )
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR
        assert "不得重复提交" in exc_info.value.message
