import json
import logging
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.design_systems.types import DesignSystemDefinition, DesignSystemFiles

logger = logging.getLogger("app.capabilities.design_systems.loader")

REQUIRED_FILES_KEYS = {"design"}
OPTIONAL_FILES_KEYS = {
    "tokens",
    "design_tokens",
    "designTokens",
    "components_manifest",
    "componentsManifest",
    "components",
    "usage",
}


def _resolve_file(ds_dir: Path, filename: str | None) -> Path | None:
    if filename is None:
        return None
    resolved = ds_dir / filename
    if resolved.is_file():
        return resolved
    logger.warning("Design system file not found: %s", resolved)
    return None


def _parse_manifest(manifest_path: Path) -> DesignSystemDefinition | None:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read manifest %s: %s", manifest_path, e)
        return None

    ds_id = data.get("id")
    if not isinstance(ds_id, str) or not ds_id:
        logger.warning("Manifest missing 'id' field: %s", manifest_path)
        return None

    name = data.get("name")
    if not isinstance(name, str) or not name:
        logger.warning("Manifest missing 'name' field: %s", manifest_path)
        return None

    category = str(data.get("category", ""))
    description = str(data.get("description", ""))
    import_mode = str(data.get("importMode", "normalized"))

    raw_files = data.get("files")
    if not isinstance(raw_files, dict):
        logger.warning("Manifest missing or invalid 'files' field: %s", manifest_path)
        return None

    design_filename = raw_files.get("design")
    if not isinstance(design_filename, str) or not design_filename:
        logger.warning("Manifest 'files.design' is required: %s", manifest_path)
        return None

    ds_dir = manifest_path.parent

    design_path = _resolve_file(ds_dir, design_filename)
    if design_path is None:
        logger.warning("Required design file missing for %s: %s", ds_id, design_filename)
        return None

    components_manifest_value = (
        raw_files.get("components_manifest")
        or raw_files.get("componentsManifest")
        or data.get("componentsManifest")
    )
    design_tokens_value = raw_files.get("design_tokens") or raw_files.get("designTokens")
    usage_value = raw_files.get("usage") or data.get("usage")

    tokens_path = _resolve_file(ds_dir, raw_files.get("tokens"))
    design_tokens_path = _resolve_file(ds_dir, design_tokens_value)
    components_manifest_path = _resolve_file(ds_dir, components_manifest_value)
    components_path = _resolve_file(ds_dir, raw_files.get("components"))
    usage_path = _resolve_file(ds_dir, usage_value)

    files = DesignSystemFiles(
        design=design_path,
        tokens=tokens_path,
        design_tokens=design_tokens_path,
        components_manifest=components_manifest_path,
        components=components_path,
        usage=usage_path,
    )

    suggested_craft: tuple[str, ...] = ()
    raw_craft = data.get("craft")
    if isinstance(raw_craft, dict):
        raw_suggested = raw_craft.get("suggested")
        if isinstance(raw_suggested, list):
            suggested_craft = tuple(str(c) for c in raw_suggested)

    return DesignSystemDefinition(
        id=ds_id,
        name=name,
        category=category,
        description=description,
        import_mode=import_mode,
        files=files,
        suggested_craft=suggested_craft,
        source_path=manifest_path,
    )


class DesignSystemLoader:
    def load(self, path_config: AssetPathConfig) -> DesignSystemRegistry:
        registry = DesignSystemRegistry()
        roots = path_config.roots_by_priority()
        seen_ids: set[str] = set()

        for root in roots:
            ds_root = root / "design-systems"
            if not ds_root.is_dir():
                continue

            for ds_dir in sorted(ds_root.iterdir()):
                if not ds_dir.is_dir():
                    continue

                manifest_path = ds_dir / "manifest.json"
                if not manifest_path.is_file():
                    continue

                ds_id = ds_dir.name
                if ds_id in seen_ids:
                    logger.warning(
                        "Design system id already loaded from higher-priority root, skipping: %s",
                        ds_id,
                    )
                    continue

                definition = _parse_manifest(manifest_path)
                if definition is None:
                    continue

                try:
                    registry.register(definition)
                    seen_ids.add(ds_id)
                except ValueError as e:
                    logger.error("Duplicate design system id during load: %s - %s", ds_id, e)
                    raise

        logger.info("Loaded %d design system(s)", len(seen_ids))
        return registry
