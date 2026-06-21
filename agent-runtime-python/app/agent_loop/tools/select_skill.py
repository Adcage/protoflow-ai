import logging
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("app.agent_loop.tools.select_skill")


class SelectSkillInput(BaseModel):
    skill_id: str = Field(
        description="要选择的 Skill ID，如 dashboard、landing-page、web-prototype、frontend-design"
    )
    reason: str = Field(default="", description="选择原因")


class SelectSkillTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = "select_skill"
    description: str = (
        "从可用 Skill 列表中选择一个最适合当前任务的 Skill。"
        "选择 Skill 后可以读取其详细规则和参考资源，也可以执行其目录下的脚本。"
    )
    args_schema: Type[BaseModel] = SelectSkillInput

    _state: object | None = None

    def set_state(self, state: object) -> None:
        self._state = state

    def _run(self, skill_id: str, reason: str = "") -> str:
        raise NotImplementedError("Use async version")

    async def _arun(self, skill_id: str, reason: str = "") -> str:
        if self._state is None:
            return "错误：未绑定 AgentLoopState"

        state = self._state
        index = getattr(state, "_asset_index", None)
        if index is None:
            return "错误：资产索引未加载，无法选择 Skill"

        try:
            skill_def = index.skill_registry.get(skill_id)
        except KeyError:
            available = [s.id for s in index.skill_registry.all()]
            return f"未找到 Skill '{skill_id}'。可用 Skill: {', '.join(available)}"

        from app.capabilities.common.loader_result import SelectedCapabilities
        from app.capabilities.common.capability_selection import CapabilitySelection

        selection = CapabilitySelection(
            skill_ids=(skill_id,),
            selection_source="agent_loop",
            reason=reason,
        )
        state.selected_capabilities = SelectedCapabilities(
            selection=selection,
            skills=[skill_def],
        )

        state.selected_skill_id = skill_id

        logger.info("select_skill | skill=%s reason=%s", skill_id, reason)
        skill_dir = str(skill_def.source_path.parent)
        return f"已选择 Skill: {skill_def.name} — {skill_def.description}\n\nSkill 目录路径: {skill_dir}\n你可以读取该目录下的资源，或执行其脚本。"
