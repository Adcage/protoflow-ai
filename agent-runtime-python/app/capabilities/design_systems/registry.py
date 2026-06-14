import logging
from app.capabilities.design_systems.types import DesignSystemDefinition

logger = logging.getLogger("app.capabilities.design_systems.registry")


class DesignSystemRegistry:
    def __init__(self) -> None:
        self._design_systems: dict[str, DesignSystemDefinition] = {}

    def register(self, design_system: DesignSystemDefinition) -> None:
        if design_system.id in self._design_systems:
            raise ValueError(f"Duplicate design system id: {design_system.id}")
        self._design_systems[design_system.id] = design_system

    def get(self, design_system_id: str) -> DesignSystemDefinition:
        if design_system_id not in self._design_systems:
            raise KeyError(f"Design system not found: {design_system_id}")
        return self._design_systems[design_system_id]
