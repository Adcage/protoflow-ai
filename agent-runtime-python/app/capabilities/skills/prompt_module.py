import logging
from typing import Any

from app.capabilities.skills.types import SkillDefinition
from app.prompts.modules import PromptModule

logger = logging.getLogger("app.capabilities.skills.prompt_module")


class SelectedSkillModule(PromptModule):
    id = "selected_skill"

    def enabled(self, context: Any, state: Any) -> bool:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return False
        return getattr(caps, "skill", None) is not None

    def render(self, context: Any, state: Any) -> str:
        caps = getattr(state, "selected_capabilities", None)
        if caps is None:
            return ""
        skill: SkillDefinition | None = getattr(caps, "skill", None)
        if skill is None:
            return ""

        sections: list[str] = []
        sections.append(f"## Selected Skill: {skill.name}")
        sections.append("")
        sections.append("Use this workflow for the current generation.")
        sections.append("")
        sections.append(skill.body.strip())

        if skill.references:
            sections.append("")
            sections.append("## Skill 可用资源")
            sections.append("")
            sections.append("如需参考布局/清单，按需读取以下文件：")
            for ref in skill.references:
                sections.append(f"  - {ref}")
            sections.append("")
            sections.append("**注意：不要逐个读取所有参考文件，只按需读取最相关的 1-2 个。**")

        return "\n".join(sections)
