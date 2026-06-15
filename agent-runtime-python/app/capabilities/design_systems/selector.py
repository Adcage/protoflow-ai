import logging

from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.design_systems.types import DesignSystemDefinition
from app.capabilities.skills.types import SkillDefinition

logger = logging.getLogger("app.capabilities.design_systems.selector")

DESIGN_SYSTEM_ID_HINTS: dict[str, str] = {
    "ant": "ant",
    "antd": "ant",
    "ant design": "ant",
    "enterprise": "enterprise",
    "clean": "clean",
    "dashboard": "dashboard",
    "material": "material",
    "tailwind": "tailwind",
}


class DesignSystemSelector:
    def select(
        self,
        prompt: str,
        code_gen_type: str,
        skill: SkillDefinition | None,
        registry: DesignSystemRegistry,
    ) -> DesignSystemDefinition | None:
        all_ds = registry.all()
        if len(all_ds) == 0:
            return None

        # Priority 1: prompt explicitly specifies a supported design system
        hinted_id = self._extract_hinted_id(prompt)
        if hinted_id is not None:
            try:
                ds = registry.get(hinted_id)
                logger.info("Design system selected by prompt hint: %s", hinted_id)
                return ds
            except KeyError:
                logger.warning("Prompt hinted design system not found: %s", hinted_id)

        # Priority 2: skill scenario=operations and ant exists -> ant
        if skill is not None and getattr(skill, "scenario", "").lower() == "operations":
            try:
                ds = registry.get("ant")
                logger.info("Design system selected by skill scenario=operations: ant")
                return ds
            except KeyError:
                pass

        # Priority 3: code_gen_type=vue_project and default exists -> default
        if code_gen_type == "vue_project":
            try:
                ds = registry.get("default")
                logger.info("Design system selected: default")
                return ds
            except KeyError:
                pass

        # Priority 4: fallback to first id alphabetically
        fallback = min(all_ds, key=lambda d: d.id)
        logger.info("Design system selected by fallback (smallest id): %s", fallback.id)
        return fallback

    def _extract_hinted_id(self, prompt: str) -> str | None:
        prompt_lower = prompt.lower()
        for hint, ds_id in DESIGN_SYSTEM_ID_HINTS.items():
            if hint in prompt_lower:
                return ds_id
        return None
