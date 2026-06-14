from dataclasses import dataclass, field
from typing import Any


@dataclass
class TemplateDefinition:
    id: str
    name: str
    description: str
    code_gen_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
