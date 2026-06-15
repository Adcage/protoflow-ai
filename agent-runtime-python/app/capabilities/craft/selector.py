import logging

from app.capabilities.craft.registry import CraftRegistry
from app.capabilities.craft.types import CraftDefinition

logger = logging.getLogger("app.capabilities.craft.selector")

DEFAULT_CRAFT_IDS: tuple[str, ...] = ("anti-slop", "state-coverage")


class CraftSelector:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = aliases or {}

    def _resolve_id(self, craft_id: str) -> str:
        return self._aliases.get(craft_id, craft_id)

    def select(
        self,
        code_gen_type: str,
        registry: CraftRegistry,
        required_craft_ids: tuple[str, ...] = (),
        suggested_craft_ids: tuple[str, ...] = (),
        default_craft_ids: tuple[str, ...] | None = None,
        aliases: dict[str, str] | None = None,
    ) -> tuple[CraftDefinition, ...]:
        if aliases is not None:
            self._aliases = aliases

        candidate_ids: list[str] = []

        for craft_id in required_craft_ids:
            resolved = self._resolve_id(craft_id)
            if resolved not in candidate_ids:
                candidate_ids.append(resolved)

        for craft_id in suggested_craft_ids:
            resolved = self._resolve_id(craft_id)
            if resolved not in candidate_ids:
                candidate_ids.append(resolved)

        defaults = default_craft_ids if default_craft_ids is not None else DEFAULT_CRAFT_IDS
        for craft_id in defaults:
            resolved = self._resolve_id(craft_id)
            if resolved not in candidate_ids:
                candidate_ids.append(resolved)

        resolved: list[CraftDefinition] = []
        for craft_id in candidate_ids:
            try:
                craft = registry.get(craft_id)
            except KeyError:
                logger.warning("Craft id not found in registry, skipping: %s", craft_id)
                continue

            if craft.applies_to and code_gen_type not in craft.applies_to:
                continue

            resolved.append(craft)

        resolved.sort(key=lambda c: c.priority)
        return tuple(resolved)
