from dataclasses import dataclass
from pathlib import Path

from app.capabilities.seeds.prompt_module import SeedModule
from app.capabilities.seeds.types import SeedDefinition


@dataclass
class FakeSelectedCapabilities:
    seed: SeedDefinition | None = None


@dataclass
class FakeState:
    selected_capabilities: FakeSelectedCapabilities | None = None


class TestSeedModuleEnabled:
    def test_disabled_when_no_selected_capabilities(self):
        module = SeedModule()
        assert module.enabled(None, FakeState()) is False

    def test_disabled_when_no_seed(self):
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=None)
        assert module.enabled(None, FakeState(selected_capabilities=caps)) is False

    def test_enabled_when_seed_selected(self):
        seed = SeedDefinition(
            id="vue-basic",
            name="Vue Basic",
            description="",
            code_gen_type="vue_project",
            entry="src/App.vue",
            files_dir=Path("/seeds/vue-basic/files"),
            copy_mode="missing-only",
            source_path=Path("/seeds/vue-basic/seed.json"),
        )
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=seed)
        assert module.enabled(None, FakeState(selected_capabilities=caps)) is True


class TestSeedModuleRender:
    def _make_seed(self, entry: str = "src/App.vue") -> SeedDefinition:
        return SeedDefinition(
            id="vue-basic",
            name="Vue Basic",
            description="",
            code_gen_type="vue_project",
            entry=entry,
            files_dir=Path("/seeds/vue-basic/files"),
            copy_mode="missing-only",
            source_path=Path("/seeds/vue-basic/seed.json"),
        )

    def test_render_includes_seed_id(self):
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=self._make_seed())
        result = module.render(None, FakeState(selected_capabilities=caps))

        assert "## Seed" in result
        assert "`vue-basic`" in result

    def test_render_includes_entry_file(self):
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=self._make_seed(entry="src/App.vue"))
        result = module.render(None, FakeState(selected_capabilities=caps))

        assert "Entry file: src/App.vue" in result

    def test_render_includes_seed_constraints(self):
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=self._make_seed())
        result = module.render(None, FakeState(selected_capabilities=caps))

        assert "### Seed Constraints" in result
        assert "The seed has already initialized the workspace." in result
        assert "Keep package.json, src/main.ts and src/App.vue consistent." in result
        assert (
            "Add components only when they reduce complexity or match the selected template."
            in result
        )
        assert (
            "Remove visible placeholder content introduced by the seed before finalizing." in result
        )

    def test_render_returns_empty_when_no_selected_capabilities(self):
        module = SeedModule()
        result = module.render(None, FakeState(selected_capabilities=None))

        assert result == ""

    def test_render_returns_empty_when_no_seed(self):
        module = SeedModule()
        caps = FakeSelectedCapabilities(seed=None)
        result = module.render(None, FakeState(selected_capabilities=caps))

        assert result == ""
