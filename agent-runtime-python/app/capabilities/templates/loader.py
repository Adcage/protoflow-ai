import json
import logging
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.templates.registry import TemplateRegistry
from app.capabilities.templates.types import TemplateDefinition

logger = logging.getLogger("app.capabilities.templates.loader")


def _parse_template_json(
    data: dict[str, object], source_path: Path, template_id: str
) -> TemplateDefinition | None:
    name = data.get("name")
    if not isinstance(name, str) or not name:
        logger.warning("Template asset missing 'name' field: %s", source_path)
        return None

    description = data.get("description")
    if not isinstance(description, str):
        description = ""

    code_gen_type = data.get("codeGenType")
    if not isinstance(code_gen_type, str):
        code_gen_type = ""

    raw_triggers = data.get("triggers")
    triggers = tuple(str(t) for t in raw_triggers) if isinstance(raw_triggers, list) else ()

    entry = data.get("entry")
    if not isinstance(entry, str):
        entry = ""

    max_prompt_files = data.get("maxPromptFiles")
    if not isinstance(max_prompt_files, int):
        max_prompt_files = 3

    raw_files = data.get("files")
    files = tuple(Path(str(f)) for f in raw_files) if isinstance(raw_files, list) else ()

    raw_references = data.get("references")
    references = (
        tuple(Path(str(r)) for r in raw_references) if isinstance(raw_references, list) else ()
    )

    raw_checklists = data.get("checklists")
    checklists = (
        tuple(Path(str(c)) for c in raw_checklists) if isinstance(raw_checklists, list) else ()
    )

    kind = data.get("kind")
    if not isinstance(kind, str):
        kind = ""

    return TemplateDefinition(
        id=template_id,
        name=name,
        description=description,
        code_gen_type=code_gen_type,
        triggers=triggers,
        entry=entry,
        max_prompt_files=max_prompt_files,
        files=files,
        source_path=source_path,
        references=references,
        checklists=checklists,
        kind=kind,
    )


class TemplateLoader:
    def load(self, path_config: AssetPathConfig) -> TemplateRegistry:
        registry = TemplateRegistry()
        roots = path_config.roots_by_priority()
        seen_ids: set[str] = set()

        for root in roots:
            templates_dir = root / "templates"
            if not templates_dir.is_dir():
                continue

            for template_dir in sorted(templates_dir.iterdir()):
                if not template_dir.is_dir():
                    continue

                template_file = template_dir / "template.json"
                if not template_file.is_file():
                    continue

                template_id = template_dir.name
                if template_id in seen_ids:
                    logger.warning(
                        "Template id already loaded from higher-priority root, skipping: %s",
                        template_id,
                    )
                    continue

                try:
                    content = template_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    template = _parse_template_json(data, template_file, template_id)
                    if template is None:
                        continue
                    registry.register(template)
                    seen_ids.add(template_id)
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in template asset %s: %s", template_file, e)
                    continue
                except ValueError as e:
                    logger.error("Duplicate template id during load: %s - %s", template_id, e)
                    raise
                except Exception as e:
                    logger.warning("Failed to load template asset %s: %s", template_file, e)
                    continue

        logger.info("Loaded %d template(s)", len(seen_ids))
        return registry
