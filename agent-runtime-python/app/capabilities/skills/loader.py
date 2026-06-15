import logging
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.common.frontmatter import parse_frontmatter
from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import (
    SkillCraftRequirement,
    SkillDefinition,
    SkillDesignSystemRequirement,
    SkillPreview,
)

logger = logging.getLogger("app.capabilities.skills.loader")


def _map_frontmatter_to_skill(
    doc_metadata: dict[str, object],
    body: str,
    source_path: Path,
    skill_id: str,
) -> SkillDefinition | None:
    name = doc_metadata.get("name")
    if not isinstance(name, str) or not name:
        logger.warning("Skill asset missing 'name' field: %s", source_path)
        return None

    description = doc_metadata.get("description")
    if not isinstance(description, str):
        description = ""

    raw_triggers = doc_metadata.get("triggers")
    if not isinstance(raw_triggers, list):
        logger.warning("Skill asset missing or invalid 'triggers' field: %s", source_path)
        return None
    triggers = tuple(str(t) for t in raw_triggers)

    od = doc_metadata.get("od")
    if not isinstance(od, dict):
        od = {}

    mode = str(od.get("mode", ""))
    platform = str(od.get("platform", ""))
    scenario = str(od.get("scenario", ""))

    preview = None
    raw_preview = od.get("preview")
    if isinstance(raw_preview, dict) and "type" in raw_preview and "entry" in raw_preview:
        preview = SkillPreview(type=str(raw_preview["type"]), entry=str(raw_preview["entry"]))

    design_system = SkillDesignSystemRequirement()
    raw_ds = od.get("design_system")
    if isinstance(raw_ds, dict):
        ds_requires = bool(raw_ds.get("requires", False))
        ds_sections = raw_ds.get("sections")
        ds_sections_tuple = (
            tuple(str(s) for s in ds_sections) if isinstance(ds_sections, list) else ()
        )
        design_system = SkillDesignSystemRequirement(
            requires=ds_requires, sections=ds_sections_tuple
        )

    craft = SkillCraftRequirement()
    raw_craft = od.get("craft")
    if isinstance(raw_craft, dict):
        craft_requires = raw_craft.get("requires")
        craft_tuple = (
            tuple(str(c) for c in craft_requires) if isinstance(craft_requires, list) else ()
        )
        craft = SkillCraftRequirement(requires=craft_tuple)

    ac = doc_metadata.get("ac")
    if not isinstance(ac, dict):
        ac = {}

    when_to_use = str(ac.get("when_to_use", ""))
    target_code_gen_types = tuple(str(v) for v in ac.get("target_code_gen_types", []) if v)
    related_templates = tuple(str(v) for v in ac.get("related_templates", []) if v)
    recommended_seeds = tuple(str(v) for v in ac.get("recommended_seeds", []) if v)
    output_contract = str(ac.get("output_contract", ""))

    known_keys = {"name", "description", "triggers", "od", "ac"}
    metadata = {k: v for k, v in doc_metadata.items() if k not in known_keys}

    return SkillDefinition(
        id=skill_id,
        name=name,
        description=description,
        triggers=triggers,
        mode=mode,
        platform=platform,
        scenario=scenario,
        preview=preview,
        design_system=design_system,
        craft=craft,
        body=body,
        source_path=source_path,
        metadata=metadata,
        when_to_use=when_to_use,
        target_code_gen_types=target_code_gen_types,
        related_templates=related_templates,
        recommended_seeds=recommended_seeds,
        output_contract=output_contract,
    )


class SkillLoader:
    def load(self, path_config: AssetPathConfig) -> SkillRegistry:
        registry = SkillRegistry()
        roots = path_config.roots_by_priority()
        seen_ids: set[str] = set()

        for root in roots:
            skills_dir = root / "skills"
            if not skills_dir.is_dir():
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue

                skill_file = skill_dir / "SKILL.md"
                if not skill_file.is_file():
                    continue

                skill_id = skill_dir.name
                if skill_id in seen_ids:
                    logger.warning(
                        "Skill id already loaded from higher-priority root, skipping: %s", skill_id
                    )
                    continue

                try:
                    doc = parse_frontmatter(skill_file)
                    skill = _map_frontmatter_to_skill(doc.metadata, doc.body, skill_file, skill_id)
                    if skill is None:
                        continue
                    registry.register(skill)
                    seen_ids.add(skill_id)
                except ValueError as e:
                    logger.error("Duplicate skill id during load: %s - %s", skill_id, e)
                    raise
                except Exception as e:
                    logger.warning("Failed to load skill asset %s: %s", skill_file, e)
                    continue

        logger.info("Loaded %d skill(s)", len(seen_ids))
        return registry
