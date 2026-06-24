from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactCheckResult:
    id: str
    status: str
    message: str
    severity: str


@dataclass
class ArtifactManifest:
    version: int = 2
    kind: str = ""
    title: str = ""
    entry: str = ""
    generation_mode: str = "application"
    artifact_format: str = ""
    code_gen_type: str = ""
    supporting_files: list[str] = field(default_factory=list)
    status: str = "complete"
    source_skill_id: str = ""
    source_skill_ids: list[str] = field(default_factory=list)
    source_seed_id: str = ""
    source_template_id: str = ""
    source_template_ids: list[str] = field(default_factory=list)
    design_system_id: str = ""
    craft_ids: list[str] = field(default_factory=list)
    selection_source: str = ""
    project_mode: str = ""
    checks: list[ArtifactCheckResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
