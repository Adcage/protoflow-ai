from pathlib import Path

from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.design_systems.selector import DesignSystemSelector
from app.capabilities.design_systems.types import DesignSystemDefinition, DesignSystemFiles


def _make_ds(
    id: str,
    name: str,
    design_path: Path | None = None,
) -> DesignSystemDefinition:
    if design_path is None:
        design_path = Path(f"/design-systems/{id}/DESIGN.md")
    return DesignSystemDefinition(
        id=id,
        name=name,
        category="Test",
        description=f"{name} design system",
        import_mode="normalized",
        files=DesignSystemFiles(design=design_path),
        source_path=Path(f"/design-systems/{id}"),
    )


class TestDesignSystemSelector:
    def test_selects_default_when_available(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))
        registry.register(_make_ds("ant", "Ant"))

        selector = DesignSystemSelector()
        result = selector.select("生成一个页面", "vue_project", registry, default_design_system_id="default")

        assert result is not None
        assert result.id == "default"

    def test_selects_hinted_design_system_from_prompt(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))
        registry.register(_make_ds("ant", "Ant"))

        selector = DesignSystemSelector()
        result = selector.select("使用 ant 风格生成", "vue_project", registry)

        assert result is not None
        assert result.id == "ant"

    def test_selects_antd_hint_as_ant(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))
        registry.register(_make_ds("ant", "Ant"))

        selector = DesignSystemSelector()
        result = selector.select("使用 antd 组件风格", "vue_project", registry)

        assert result is not None
        assert result.id == "ant"

    def test_hinted_id_not_found_falls_to_default(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))

        selector = DesignSystemSelector()
        result = selector.select("使用 material 风格", "vue_project", registry)

        assert result is not None
        assert result.id == "default"

    def test_no_default_selects_smallest_id(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("beta", "Beta"))
        registry.register(_make_ds("alpha", "Alpha"))

        selector = DesignSystemSelector()
        result = selector.select("生成一个页面", "vue_project", registry)

        assert result is not None
        assert result.id == "alpha"

    def test_empty_registry_returns_none(self):
        registry = DesignSystemRegistry()

        selector = DesignSystemSelector()
        result = selector.select("生成一个页面", "vue_project", registry)

        assert result is None

    def test_default_design_system_id_used(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))
        registry.register(_make_ds("ant", "Ant"))

        selector = DesignSystemSelector()
        result = selector.select("生成一个页面", "vue_project", registry, default_design_system_id="ant")

        assert result is not None
        assert result.id == "ant"

    def test_default_id_not_found_falls_back(self):
        registry = DesignSystemRegistry()
        registry.register(_make_ds("default", "Default"))

        selector = DesignSystemSelector()
        result = selector.select("生成一个页面", "vue_project", registry, default_design_system_id="nonexistent")

        assert result is not None
        assert result.id == "default"
