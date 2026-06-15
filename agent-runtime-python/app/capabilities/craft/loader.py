import logging
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.common.frontmatter import parse_frontmatter
from app.capabilities.craft.registry import CraftRegistry
from app.capabilities.craft.types import CraftDefinition

logger = logging.getLogger("app.capabilities.craft.loader")


def _default_name_from_id(craft_id: str) -> str:
    return " ".join(part.capitalize() for part in craft_id.replace("_", "-").split("-"))


def _map_frontmatter_to_craft(
    doc_metadata: dict[str, object],
    body: str,
    source_path: Path,
    craft_id: str,
) -> CraftDefinition | None:
    name = doc_metadata.get("name")
    if not isinstance(name, str) or not name:
        name = _default_name_from_id(craft_id)

    description = doc_metadata.get("description")
    if not isinstance(description, str):
        description = ""

    raw_applies_to = doc_metadata.get("appliesTo")
    if raw_applies_to is None:
        applies_to: tuple[str, ...] = ()
    elif isinstance(raw_applies_to, list):
        applies_to = tuple(str(item) for item in raw_applies_to)
    else:
        applies_to = ()

    priority = doc_metadata.get("priority")
    if not isinstance(priority, int):
        priority = 100

    return CraftDefinition(
        id=craft_id,
        name=name,
        description=description,
        applies_to=applies_to,
        priority=priority,
        body=body,
        source_path=source_path,
    )


class CraftLoader:
    def load(self, path_config: AssetPathConfig) -> CraftRegistry:
        registry = CraftRegistry()
        roots = path_config.roots_by_priority()
        seen_ids: set[str] = set()

        for root in roots:
            craft_dir = root / "craft"
            if not craft_dir.is_dir():
                continue

            for md_file in sorted(craft_dir.glob("*.md")):
                craft_id = md_file.stem
                if craft_id in seen_ids:
                    logger.warning(
                        "Craft id already loaded from higher-priority root, skipping: %s", craft_id
                    )
                    continue

                try:
                    doc = parse_frontmatter(md_file)
                    craft = _map_frontmatter_to_craft(doc.metadata, doc.body, md_file, craft_id)
                    if craft is None:
                        continue
                    registry.register(craft)
                    seen_ids.add(craft_id)
                except ValueError as e:
                    logger.error("Duplicate craft id during load: %s - %s", craft_id, e)
                    raise
                except Exception as e:
                    logger.warning("Failed to load craft asset %s: %s", md_file, e)
                    continue

        logger.info("Loaded %d craft(s)", len(seen_ids))
        return registry
