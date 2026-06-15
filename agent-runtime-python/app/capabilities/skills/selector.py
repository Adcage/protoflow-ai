import logging

from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition

logger = logging.getLogger("app.capabilities.skills.selector")


class SkillSelector:
    def select(self, prompt: str, registry: SkillRegistry) -> list[SkillDefinition]:
        """Return skills sorted by relevance score, highest first."""
        prompt_lower = prompt.lower()
        candidates: list[tuple[int, str, SkillDefinition]] = []

        for skill in registry.all():
            score = sum(10 for trigger in skill.triggers if trigger.lower() in prompt_lower)
            if skill.scenario and skill.scenario.lower() in prompt_lower:
                score += 3
            if score > 0:
                candidates.append((score, skill.id, skill))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in candidates]
