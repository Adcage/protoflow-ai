import json
from pathlib import Path

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.seeds.loader import SeedLoader
from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.seeds.types import SeedDefinition


VUE_BASIC_SEED_JSON = {
    "schemaVersion": "ac-seed/v1",
    "id": "vue-basic",
    "name": "Vue Basic Seed",
    "description": "Vue 3 basic starter with App.vue and src structure.",
    "codeGenType": "vue_project",
    "entry": "src/App.vue",
    "filesDir": "files",
    "copyMode": "missing-only",
}


def _write_seed_json(seed_dir: Path, data: dict) -> None:
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "seed.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class TestSeedLoader:
    def test_load_vue_basic_seed(self, tmp_path: Path):
        seed_dir = tmp_path / "seeds" / "vue-basic"
        _write_seed_json(seed_dir, VUE_BASIC_SEED_JSON)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        seed = registry.get("vue-basic")
        assert isinstance(seed, SeedDefinition)
        assert seed.name == "Vue Basic Seed"
        assert seed.description == "Vue 3 basic starter with App.vue and src structure."
        assert seed.code_gen_type == "vue_project"
        assert seed.entry == "src/App.vue"
        assert seed.files_dir == seed_dir / "files"
        assert seed.copy_mode == "missing-only"

    def test_files_dir_resolved_to_absolute_path(self, tmp_path: Path):
        seed_dir = tmp_path / "seeds" / "vue-basic"
        _write_seed_json(seed_dir, VUE_BASIC_SEED_JSON)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        seed = registry.get("vue-basic")
        assert seed.files_dir.is_absolute()

    def test_copy_mode_defaults_to_missing_only(self, tmp_path: Path):
        data = dict(VUE_BASIC_SEED_JSON)
        del data["copyMode"]
        seed_dir = tmp_path / "seeds" / "vue-basic"
        _write_seed_json(seed_dir, data)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        seed = registry.get("vue-basic")
        assert seed.copy_mode == "missing-only"

    def test_files_dir_defaults_to_files(self, tmp_path: Path):
        data = dict(VUE_BASIC_SEED_JSON)
        del data["filesDir"]
        seed_dir = tmp_path / "seeds" / "vue-basic"
        _write_seed_json(seed_dir, data)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        seed = registry.get("vue-basic")
        assert seed.files_dir == seed_dir / "files"

    def test_load_skips_invalid_schema_version(self, tmp_path: Path):
        data = dict(VUE_BASIC_SEED_JSON)
        data["schemaVersion"] = "ac-seed/v2"
        seed_dir = tmp_path / "seeds" / "bad-version"
        _write_seed_json(seed_dir, data)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_skips_missing_id(self, tmp_path: Path):
        data = dict(VUE_BASIC_SEED_JSON)
        del data["id"]
        seed_dir = tmp_path / "seeds" / "no-id"
        _write_seed_json(seed_dir, data)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_skips_missing_code_gen_type(self, tmp_path: Path):
        data = dict(VUE_BASIC_SEED_JSON)
        del data["codeGenType"]
        seed_dir = tmp_path / "seeds" / "no-cgt"
        _write_seed_json(seed_dir, data)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_no_seeds_dir(self, tmp_path: Path):
        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_load_skips_directory_without_seed_json(self, tmp_path: Path):
        (tmp_path / "seeds" / "empty").mkdir(parents=True)

        config = AssetPathConfig(bundled_root=tmp_path)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_duplicate_id_across_roots_skips_lower_priority(self, tmp_path: Path):
        root_project = tmp_path / "project"
        root_bundled = tmp_path / "bundled"
        for root in (root_project, root_bundled):
            seed_dir = root / "seeds" / "vue-basic"
            _write_seed_json(seed_dir, VUE_BASIC_SEED_JSON)

        config = AssetPathConfig(bundled_root=root_bundled, project_root=root_project)
        loader = SeedLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 1

    def test_higher_priority_root_overrides(self, tmp_path: Path):
        root_project = tmp_path / "project"
        root_bundled = tmp_path / "bundled"

        project_data = dict(VUE_BASIC_SEED_JSON)
        project_data["name"] = "Vue Basic Custom"
        _write_seed_json(root_project / "seeds" / "vue-basic", project_data)
        _write_seed_json(root_bundled / "seeds" / "vue-basic", VUE_BASIC_SEED_JSON)

        config = AssetPathConfig(bundled_root=root_bundled, project_root=root_project)
        loader = SeedLoader()
        registry = loader.load(config)

        seed = registry.get("vue-basic")
        assert seed.name == "Vue Basic Custom"


class TestSeedRegistry:
    def test_all_returns_registered_seeds(self):
        registry = SeedRegistry()
        seed = SeedDefinition(
            id="test",
            name="Test",
            description="Test seed",
            code_gen_type="vue_project",
            entry="src/App.vue",
            files_dir=Path("/files"),
            copy_mode="missing-only",
            source_path=Path("/seed.json"),
        )
        registry.register(seed)
        result = registry.all()
        assert len(result) == 1
        assert result[0].id == "test"

    def test_all_returns_empty_tuple_when_no_seeds(self):
        registry = SeedRegistry()
        assert registry.all() == ()

    def test_register_duplicate_raises(self):
        registry = SeedRegistry()
        seed = SeedDefinition(
            id="dup",
            name="Dup",
            description="",
            code_gen_type="vue_project",
            entry="",
            files_dir=Path("/files"),
            copy_mode="missing-only",
            source_path=Path("/seed.json"),
        )
        registry.register(seed)
        try:
            registry.register(seed)
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_get_missing_raises_key_error(self):
        registry = SeedRegistry()
        try:
            registry.get("missing")
            assert False, "Expected KeyError"
        except KeyError:
            pass
