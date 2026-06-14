import logging
from app.capabilities.craft.types import CraftDefinition

logger = logging.getLogger("app.capabilities.craft.registry")


class CraftRegistry:
    def __init__(self) -> None:
        self._crafts: dict[str, CraftDefinition] = {}

    def register(self, craft: CraftDefinition) -> None:
        if craft.id in self._crafts:
            raise ValueError(f"Duplicate craft id: {craft.id}")
        self._crafts[craft.id] = craft

    def get(self, craft_id: str) -> CraftDefinition:
        if craft_id not in self._crafts:
            raise KeyError(f"Craft not found: {craft_id}")
        return self._crafts[craft_id]
