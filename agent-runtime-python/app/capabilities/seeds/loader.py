import json
import logging
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.seeds.types import SeedDefinition

logger = logging.getLogger("app.capabilities.seeds.loader")

SCHEMA_VERSION = "ac-seed/v1"


def _parse_seed_json(seed_json_path: Path) -> SeedDefinition | None:
    try:
        data = json.loads(seed_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read seed.json: %s - %s", seed_json_path, e)
        return None

    schema_version = data.get("schemaVersion")
    if schema_version != SCHEMA_VERSION:
        logger.warning("Unsupported seed schema version: %s in %s", schema_version, seed_json_path)
        return None

    seed_id = data.get("id")
    if not isinstance(seed_id, str) or not seed_id:
        logger.warning("seed.json missing 'id' field: %s", seed_json_path)
        return None

    name = data.get("name")
    if not isinstance(name, str) or not name:
        logger.warning("seed.json missing 'name' field: %s", seed_json_path)
        return None

    description = data.get("description")
    if not isinstance(description, str):
        description = ""

    code_gen_type = data.get("codeGenType")
    if not isinstance(code_gen_type, str) or not code_gen_type:
        logger.warning("seed.json missing 'codeGenType' field: %s", seed_json_path)
        return None

    raw_triggers = data.get("triggers")
    if not isinstance(raw_triggers, list):
        triggers: tuple[str, ...] = ()
    else:
        triggers = tuple(str(t) for t in raw_triggers)

    entry = data.get("entry")
    if not isinstance(entry, str):
        entry = ""

    files_dir_name = data.get("filesDir")
    if not isinstance(files_dir_name, str):
        files_dir_name = "files"

    seed_dir = seed_json_path.parent
    files_dir = seed_dir / files_dir_name

    copy_mode = data.get("copyMode")
    if not isinstance(copy_mode, str) or copy_mode not in ("missing-only", "overwrite"):
        copy_mode = "missing-only"

    return SeedDefinition(
        id=seed_id,
        name=name,
        description=description,
        code_gen_type=code_gen_type,
        triggers=triggers,
        entry=entry,
        files_dir=files_dir,
        copy_mode=copy_mode,
        source_path=seed_json_path,
    )


class SeedLoader:
    def load(self, path_config: AssetPathConfig) -> SeedRegistry:
        registry = SeedRegistry()
        roots = path_config.roots_by_priority()
        seen_ids: set[str] = set()

        for root in roots:
            seeds_dir = root / "seeds"
            if not seeds_dir.is_dir():
                continue

            for seed_dir in sorted(seeds_dir.iterdir()):
                if not seed_dir.is_dir():
                    continue

                seed_json = seed_dir / "seed.json"
                if not seed_json.is_file():
                    continue

                seed_id = seed_dir.name
                if seed_id in seen_ids:
                    logger.warning(
                        "Seed id already loaded from higher-priority root, skipping: %s",
                        seed_id,
                    )
                    continue

                try:
                    seed = _parse_seed_json(seed_json)
                    if seed is None:
                        continue
                    registry.register(seed)
                    seen_ids.add(seed_id)
                except ValueError as e:
                    logger.error("Duplicate seed id during load: %s - %s", seed_id, e)
                    raise
                except Exception as e:
                    logger.warning("Failed to load seed asset %s: %s", seed_json, e)
                    continue

        logger.info("Loaded %d seed(s)", len(seen_ids))
        return registry
