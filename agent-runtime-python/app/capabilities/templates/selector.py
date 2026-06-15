import logging

from app.capabilities.templates.registry import TemplateRegistry
from app.capabilities.templates.types import TemplateDefinition

logger = logging.getLogger("app.capabilities.templates.selector")


class TemplateSelector:
    def select(
        self,
        prompt: str,
        code_gen_type: str,
        skill_id: str | None = None,
        registry: TemplateRegistry | None = None,
        *,
        recommended_template_ids: tuple[str, ...] = (),
    ) -> TemplateDefinition | None:
        if registry is None:
            return None

        if recommended_template_ids:
            for template_id in recommended_template_ids:
                try:
                    template = registry.get(template_id)
                except KeyError:
                    continue
                if not template.code_gen_type or template.code_gen_type == code_gen_type:
                    return template

        prompt_lower = prompt.lower()
        candidates: list[tuple[int, str, TemplateDefinition]] = []

        for template in registry.all():
            if template.code_gen_type and template.code_gen_type != code_gen_type:
                continue

            score = sum(10 for trigger in template.triggers if trigger.lower() in prompt_lower)

            if skill_id and skill_id == template.id:
                score += 5

            if score > 0:
                candidates.append((score, template.id, template))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][2]
