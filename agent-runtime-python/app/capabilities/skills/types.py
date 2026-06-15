from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SkillPreview:
    type: str
    entry: str


@dataclass(frozen=True)
class SkillDesignSystemRequirement:
    requires: bool = False
    sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillCraftRequirement:
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    triggers: tuple[str, ...]
    mode: str
    platform: str
    scenario: str
    preview: SkillPreview | None
    design_system: SkillDesignSystemRequirement
    craft: SkillCraftRequirement
    body: str
    source_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)
    when_to_use: str = ""
    target_code_gen_types: tuple[str, ...] = ()
    related_templates: tuple[str, ...] = ()
    recommended_seeds: tuple[str, ...] = ()
    output_contract: str = ""
