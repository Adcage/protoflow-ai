from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemplateDefinition:
    id: str
    name: str
    description: str
    code_gen_type: str
    triggers: tuple[str, ...]
    entry: str
    max_prompt_files: int
    files: tuple[Path, ...]
    source_path: Path
    references: tuple[Path, ...] = ()
    checklists: tuple[Path, ...] = ()
    kind: str = ""
