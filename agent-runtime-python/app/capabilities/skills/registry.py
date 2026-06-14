import logging
from app.capabilities.skills.types import SkillDefinition

logger = logging.getLogger("app.capabilities.skills.registry")


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        if skill.id in self._skills:
            raise ValueError(f"Duplicate skill id: {skill.id}")
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> SkillDefinition:
        if skill_id not in self._skills:
            raise KeyError(f"Skill not found: {skill_id}")
        return self._skills[skill_id]
