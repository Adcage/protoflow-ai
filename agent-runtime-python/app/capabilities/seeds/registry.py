import logging
from app.capabilities.seeds.types import SeedDefinition

logger = logging.getLogger("app.capabilities.seeds.registry")


class SeedRegistry:
    def __init__(self) -> None:
        self._seeds: dict[str, SeedDefinition] = {}

    def register(self, seed: SeedDefinition) -> None:
        if seed.id in self._seeds:
            raise ValueError(f"Duplicate seed id: {seed.id}")
        self._seeds[seed.id] = seed

    def get(self, seed_id: str) -> SeedDefinition:
        if seed_id not in self._seeds:
            raise KeyError(f"Seed not found: {seed_id}")
        return self._seeds[seed_id]
