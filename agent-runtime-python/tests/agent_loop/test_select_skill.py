"""Phase 3 select_skill 兼容入口测试。"""

import pytest
from types import SimpleNamespace
from typing import Any

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.select_skill import SelectSkillTool
from app.agent_loop.tools.plan_tools import ChooseSkillTool
from app.capabilities.skills.selector import SkillNotFoundError, SkillRegistryProvider


def _init_envelope(state: AgentLoopState) -> None:
    state._state_envelope = state._to_envelope()


class TestSelectSkillCompatibility:
    @pytest.mark.asyncio
    async def test_select_skill_delegates_to_choose_skill(self):
        state = AgentLoopState()
        _init_envelope(state)
        state._state_envelope.workflow.plan.plan_stage = "inspect_existing_project"

        from app.agent_loop.tools.plan_tools import RecordProjectInspectionTool

        inspection_tool = RecordProjectInspectionTool()
        inspection_tool.set_state(state)
        await inspection_tool._arun(
            decision="not_applicable",
            summary="新建项目",
        )
        assert state._state_envelope.workflow.plan.plan_stage == "select_skill"

        skill = SimpleNamespace(
            id="dashboard",
            name="Dashboard",
            description="x",
            source_path="/x/SKILL.md",
            references=("SKILL.md",),
        )
        provider = SkillRegistryProvider(
            _StubRegistry({"dashboard": skill})
        )

        choose_tool = ChooseSkillTool()
        choose_tool.set_state(state)
        choose_tool.set_skill_registry_provider(provider)

        select_tool = SelectSkillTool()
        select_tool.set_state(state)
        select_tool.set_delegate(choose_tool._arun)

        result = await select_tool._arun(
            skill_id="dashboard",
            reason="data dashboard",
        )
        plan = state._state_envelope.workflow.plan
        assert plan.selected_skill_id == "dashboard"
        assert plan.capability_bundle.skills[0].capability_id == "dashboard"
        assert "已选择 Skill" in result

    @pytest.mark.asyncio
    async def test_select_skill_without_delegate_returns_error(self):
        state = AgentLoopState()
        _init_envelope(state)

        select_tool = SelectSkillTool()
        select_tool.set_state(state)
        result = await select_tool._arun(skill_id="dashboard", reason="x")
        assert "未配置" in result or "delegate" in result

    @pytest.mark.asyncio
    async def test_select_skill_without_state(self):
        select_tool = SelectSkillTool()
        result = await select_tool._arun(skill_id="dashboard", reason="x")
        assert "未绑定" in result


class _StubRegistry:
    def __init__(self, skills: dict[str, Any]) -> None:
        self._skills = skills

    def get(self, skill_id: str) -> Any:
        if skill_id not in self._skills:
            raise SkillNotFoundError(skill_id)
        return self._skills[skill_id]

    def all(self) -> list[Any]:
        return list(self._skills.values())
