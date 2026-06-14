import logging
from app.capabilities.templates.types import TemplateDefinition

logger = logging.getLogger("app.capabilities.templates.registry")


class TemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, TemplateDefinition] = {}

    def register(self, template: TemplateDefinition) -> None:
        if template.id in self._templates:
            raise ValueError(f"Duplicate template id: {template.id}")
        self._templates[template.id] = template

    def get(self, template_id: str) -> TemplateDefinition:
        if template_id not in self._templates:
            raise KeyError(f"Template not found: {template_id}")
        return self._templates[template_id]
