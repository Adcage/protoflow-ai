from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeedDefinition:
    id: str
    name: str
    description: str
    file_patterns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
