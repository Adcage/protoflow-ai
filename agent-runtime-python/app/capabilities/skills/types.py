from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillDefinition:
    id: str
    name: str
    description: str
    version: str = "1.0"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
