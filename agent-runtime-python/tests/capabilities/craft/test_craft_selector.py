from pathlib import Path

from app.capabilities.craft.registry import CraftRegistry
from app.capabilities.craft.selector import CraftSelector, DEFAULT_CRAFT_IDS
from app.capabilities.craft.types import CraftDefinition


def _make_craft(
    id: str,
    name: str,
    applies_to: tuple[str, ...] = (),
    priority: int = 50,
) -> CraftDefinition:
    return CraftDefinition(
        id=id,
        name=name,
        description=f"{name} craft",
        applies_to=applies_to,
        priority=priority,
        body=f"# {name}\n\nRules for {name}.",
        source_path=Path(f"/craft/{id}.md"),
    )


class TestCraftSelector:
    def test_default_crafts_always_selected(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(
            _make_craft(
                "state-coverage", "State Coverage", applies_to=("vue_project",), priority=30
            )
        )

        selector = CraftSelector()
        result = selector.select("vue_project", registry)

        ids = [c.id for c in result]
        assert "anti-ai-slop" in ids
        assert "state-coverage" in ids

    def test_skill_required_crafts_added(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(_make_craft("state-coverage", "State Coverage", priority=30))
        registry.register(_make_craft("accessibility-baseline", "Accessibility", priority=50))

        selector = CraftSelector()
        result = selector.select(
            "vue_project", registry, required_craft_ids=("accessibility-baseline",)
        )

        ids = [c.id for c in result]
        assert "accessibility-baseline" in ids
        assert "anti-ai-slop" in ids
        assert "state-coverage" in ids

    def test_design_system_suggested_crafts_added(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(_make_craft("state-coverage", "State Coverage", priority=30))
        registry.register(_make_craft("typography", "Typography", priority=40))

        selector = CraftSelector()
        result = selector.select("vue_project", registry, suggested_craft_ids=("typography",))

        ids = [c.id for c in result]
        assert "typography" in ids

    def test_deduplication_by_id(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(_make_craft("state-coverage", "State Coverage", priority=30))

        selector = CraftSelector()
        result = selector.select(
            "vue_project",
            registry,
            required_craft_ids=("anti-ai-slop",),
            suggested_craft_ids=("anti-ai-slop",),
        )

        ids = [c.id for c in result]
        assert ids.count("anti-ai-slop") == 1

    def test_priority_sorting(self):
        registry = CraftRegistry()
        registry.register(_make_craft("accessibility-baseline", "Accessibility", priority=50))
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(_make_craft("state-coverage", "State Coverage", priority=30))

        selector = CraftSelector()
        result = selector.select("vue_project", registry)

        priorities = [c.priority for c in result]
        assert priorities == sorted(priorities)

    def test_applies_to_filter_excludes_non_matching(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", applies_to=(), priority=10))
        registry.register(
            _make_craft(
                "state-coverage", "State Coverage", applies_to=("vue_project",), priority=30
            )
        )
        registry.register(
            _make_craft("single-only", "Single Only", applies_to=("single_file",), priority=20)
        )

        selector = CraftSelector()
        result = selector.select("vue_project", registry)

        ids = [c.id for c in result]
        assert "single-only" not in ids
        assert "state-coverage" in ids

    def test_empty_applies_to_matches_all(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", applies_to=(), priority=10))

        selector = CraftSelector()
        result = selector.select("single_file", registry)

        assert len(result) == 1
        assert result[0].id == "anti-ai-slop"

    def test_missing_craft_id_skipped(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))

        selector = CraftSelector()
        result = selector.select("vue_project", registry, required_craft_ids=("nonexistent",))

        ids = [c.id for c in result]
        assert "nonexistent" not in ids
        assert "anti-ai-slop" in ids

    def test_no_default_crafts_in_registry(self):
        registry = CraftRegistry()

        selector = CraftSelector()
        result = selector.select("vue_project", registry)

        assert len(result) == 0

    def test_required_before_suggested_before_default(self):
        registry = CraftRegistry()
        registry.register(_make_craft("anti-ai-slop", "Anti AI Slop", priority=10))
        registry.register(_make_craft("state-coverage", "State Coverage", priority=30))
        registry.register(_make_craft("accessibility-baseline", "Accessibility", priority=50))
        registry.register(_make_craft("typography", "Typography", priority=40))

        selector = CraftSelector()
        result = selector.select(
            "vue_project",
            registry,
            required_craft_ids=("accessibility-baseline",),
            suggested_craft_ids=("typography",),
        )

        ids = [c.id for c in result]
        assert "accessibility-baseline" in ids
        assert "typography" in ids
        assert "anti-ai-slop" in ids
        assert "state-coverage" in ids

    def test_default_craft_ids_constant(self):
        assert DEFAULT_CRAFT_IDS == ("anti-ai-slop", "state-coverage")
