from pathlib import Path

from app.capabilities.templates.selector import TemplateSelector
from app.capabilities.templates.types import TemplateDefinition


def _make_template(
    id: str = "dashboard-analytics",
    name: str = "Analytics Dashboard",
    code_gen_type: str = "vue_project",
) -> TemplateDefinition:
    return TemplateDefinition(
        id=id,
        name=name,
        description="Test template",
        code_gen_type=code_gen_type,
        entry="files/src/App.vue",
        max_prompt_files=3,
        files=(Path("files/src/App.vue"),),
        source_path=Path("/test"),
    )


class TestTemplateSelector:
    def test_select_first_matching_code_gen_type(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(code_gen_type="vue_project"))
        selector = TemplateSelector()

        result = selector.select("vue_project", registry)
        assert result is not None
        assert result.id == "dashboard-analytics"

    def test_code_gen_type_filter(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(code_gen_type="vue_project"))
        selector = TemplateSelector()

        result = selector.select("single_file", registry)
        assert result is None

    def test_no_match_returns_none(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        selector = TemplateSelector()

        result = selector.select("vue_project", registry)
        assert result is None

    def test_empty_registry(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        selector = TemplateSelector()

        result = selector.select("vue_project", registry)
        assert result is None

    def test_empty_code_gen_type_matches_all(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(code_gen_type=""))
        selector = TemplateSelector()

        result = selector.select("vue_project", registry)
        assert result is not None

    def test_default_template_id_used(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(id="dashboard", code_gen_type="single_file"))
        registry.register(_make_template(id="landing", name="Landing", code_gen_type="vue_project"))
        selector = TemplateSelector()

        result = selector.select("single_file", registry, default_template_id="dashboard")
        assert result is not None
        assert result.id == "dashboard"

    def test_default_template_id_skip_mismatched_code_gen_type(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(id="dashboard", code_gen_type="vue_project"))
        registry.register(_make_template(id="landing", name="Landing", code_gen_type="single_file"))
        selector = TemplateSelector()

        result = selector.select("single_file", registry, default_template_id="dashboard")
        assert result is not None
        assert result.id == "landing"

    def test_default_template_id_missing_falls_back(self) -> None:
        from app.capabilities.templates.registry import TemplateRegistry

        registry = TemplateRegistry()
        registry.register(_make_template(id="dashboard", code_gen_type="single_file"))
        selector = TemplateSelector()

        result = selector.select("single_file", registry, default_template_id="missing")
        assert result is not None
        assert result.id == "dashboard"
