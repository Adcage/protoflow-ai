from pathlib import Path


from app.capabilities.common.asset_index import (
    AssetIndex,
    AssetManager,
    create_default_asset_manager,
)
from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.craft.registry import CraftRegistry
from app.capabilities.craft.types import CraftDefinition
from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.design_systems.types import DesignSystemDefinition, DesignSystemFiles
from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.seeds.types import SeedDefinition
from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition
from app.capabilities.templates.registry import TemplateRegistry
from app.capabilities.templates.types import TemplateDefinition


def _make_skill_registry(skill_id: str = "test-skill") -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        SkillDefinition(
            id=skill_id,
            name=skill_id,
            description="test",
            body="body",
            source_path=Path("."),
        )
    )
    return registry


def _make_seed_registry(seed_id: str = "test-seed") -> SeedRegistry:
    registry = SeedRegistry()
    registry.register(
        SeedDefinition(
            id=seed_id,
            name=seed_id,
            description="test",
            code_gen_type="vue_project",
            entry="src/App.vue",
            files_dir=Path("/tmp/seed"),
            copy_mode="missing-only",
            source_path=Path("."),
        )
    )
    return registry


def _make_template_registry(template_id: str = "test-template") -> TemplateRegistry:
    registry = TemplateRegistry()
    registry.register(
        TemplateDefinition(
            id=template_id,
            name=template_id,
            description="test",
            code_gen_type="vue_project",
            entry="src/App.vue",
            max_prompt_files=3,
            files=(Path("files/src/App.vue"),),
            source_path=Path("."),
        )
    )
    return registry


def _make_ds_registry(ds_id: str = "default") -> DesignSystemRegistry:
    registry = DesignSystemRegistry()
    registry.register(
        DesignSystemDefinition(
            id=ds_id,
            name=ds_id,
            category="product",
            description="test",
            import_mode="normalized",
            files=DesignSystemFiles(design=Path("/tmp/DESIGN.md")),
            suggested_craft=("anti-ai-slop",),
            source_path=Path("."),
        )
    )
    return registry


def _make_craft_registry(craft_id: str = "anti-ai-slop") -> CraftRegistry:
    registry = CraftRegistry()
    registry.register(
        CraftDefinition(
            id=craft_id,
            name=craft_id,
            description="test",
            applies_to=(),
            priority=50,
            body="no lorem ipsum",
            source_path=Path("."),
        )
    )
    return registry


class TestAssetIndex:
    def test_asset_index_fields(self):
        idx = AssetIndex(
            skill_registry=_make_skill_registry(),
            seed_registry=_make_seed_registry(),
            template_registry=_make_template_registry(),
            design_system_registry=_make_ds_registry(),
            craft_registry=_make_craft_registry(),
        )
        assert len(idx.skill_registry.all()) == 1
        assert len(idx.seed_registry.all()) == 1
        assert len(idx.template_registry.all()) == 1
        assert len(idx.design_system_registry.all()) == 1
        assert len(idx.craft_registry.all()) == 1


class TestAssetManager:
    def test_get_index_lazy(self, tmp_path: Path):
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "skills").mkdir()
        (bundled / "seeds").mkdir()
        (bundled / "templates").mkdir()
        (bundled / "design-systems").mkdir()
        (bundled / "craft").mkdir()

        config = AssetPathConfig(bundled_root=bundled)
        mgr = AssetManager(path_config=config)
        assert mgr._index is None
        idx = mgr.get_index()
        assert mgr._index is not None
        assert idx is mgr._index

    def test_refresh_reloads(self, tmp_path: Path):
        bundled = tmp_path / "bundled"
        bundled.mkdir()
        (bundled / "skills").mkdir()
        (bundled / "seeds").mkdir()
        (bundled / "templates").mkdir()
        (bundled / "design-systems").mkdir()
        (bundled / "craft").mkdir()

        config = AssetPathConfig(bundled_root=bundled)
        mgr = AssetManager(path_config=config)
        idx1 = mgr.get_index()
        idx2 = mgr.refresh()
        assert idx1 is not idx2
        assert mgr._index is idx2

    def test_load_from_bundled_root(self, tmp_path: Path):
        bundled = tmp_path / "bundled"
        skills_dir = bundled / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "dashboard"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: dashboard\n"
            "description: Dashboard skill\n"
            "---\n\n# Dashboard\n",
            encoding="utf-8",
        )

        (bundled / "seeds").mkdir()
        (bundled / "templates").mkdir()
        (bundled / "design-systems").mkdir()
        (bundled / "craft").mkdir()

        config = AssetPathConfig(bundled_root=bundled)
        mgr = AssetManager(path_config=config)
        idx = mgr.get_index()
        assert len(idx.skill_registry.all()) == 1
        assert idx.skill_registry.all()[0].id == "dashboard"


class TestCreateDefaultAssetManager:
    def test_creates_manager(self):
        mgr = create_default_asset_manager()
        assert isinstance(mgr, AssetManager)
        assert mgr._path_config.bundled_root is not None
