from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactManifest:
    version: int
    kind: str
    title: str
    entry: str
    code_gen_type: str
    supporting_files: list[str] = field(default_factory=list)
    status: str = "complete"
    source_skill_id: str = ""
    source_seed_id: str = ""
    source_template_id: str = ""
    design_system_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
