from pathlib import Path

from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.seeds.selector import SeedSelector
from app.capabilities.seeds.types import SeedDefinition


def _make_seed(
    id: str,
    name: str,
    code_gen_type: str = "vue_project",
    copy_mode: str = "missing-only",
) -> SeedDefinition:
    return SeedDefinition(
        id=id,
        name=name,
        description=f"{name} seed",
        code_gen_type=code_gen_type,
        entry="src/App.vue",
        files_dir=Path(f"/seeds/{id}/files"),
        copy_mode=copy_mode,
        source_path=Path(f"/seeds/{id}/seed.json"),
    )


class TestSeedSelector:
    def test_generate_vue_project_defaults_to_vue_basic(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry)

        assert result is not None
        assert result.id == "vue-basic"

    def test_modify_mode_returns_none(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))

        selector = SeedSelector()
        result = selector.select("vue_project", "modify", registry)

        assert result is None

    def test_code_gen_type_mismatch_excluded(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic", code_gen_type="vue_project"))

        selector = SeedSelector()
        result = selector.select("single_file", "generate", registry)

        assert result is None

    def test_no_matching_seed_for_non_vue_project(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic", code_gen_type="vue_project"))

        selector = SeedSelector()
        result = selector.select("multi-file", "generate", registry)

        assert result is None

    def test_empty_registry_returns_none(self):
        registry = SeedRegistry()
        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry)

        assert result is None

    def test_vue_basic_default_not_found_returns_none(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-dashboard", "Vue Dashboard"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry)

        assert result is None

    def test_route_mode_returns_none(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))

        selector = SeedSelector()
        result = selector.select("vue_project", "route", registry)

        assert result is None

    def test_default_seed_id_overrides_vue_basic(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))
        registry.register(_make_seed("vue-dashboard", "Vue Dashboard"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry, default_seed_id="vue-dashboard")

        assert result is not None
        assert result.id == "vue-dashboard"

    def test_default_seed_id_code_gen_type_mismatch_ignored(self):
        registry = SeedRegistry()
        registry.register(_make_seed("html-basic", "HTML Basic", code_gen_type="single_file"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry, default_seed_id="html-basic")

        assert result is None

    def test_default_seed_id_missing_falls_back(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry, default_seed_id="nonexistent")

        assert result is not None
        assert result.id == "vue-basic"

    def test_default_seed_id_empty_uses_vue_basic(self):
        registry = SeedRegistry()
        registry.register(_make_seed("vue-basic", "Vue Basic"))

        selector = SeedSelector()
        result = selector.select("vue_project", "generate", registry, default_seed_id="")

        assert result is not None
        assert result.id == "vue-basic"
