from dataclasses import dataclass, field
from typing import Any


@dataclass
class CraftDefinition:
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
