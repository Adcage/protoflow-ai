from dataclasses import dataclass, field
from typing import Any


@dataclass
class DesignSystemDefinition:
    id: str
    name: str
    description: str
    tokens: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
