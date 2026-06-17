import json
from pathlib import Path

import pytest

from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.templates.loader import TemplateLoader


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    assets = tmp_path / "assets"
    assets.mkdir()
    return assets


def _create_template_json(
    template_dir: Path,
    template_id: str = "dashboard-analytics",
    name: str = "Analytics Dashboard",
    description: str = "Dashboard layout with sidebar.",
    code_gen_type: str = "vue_project",
    entry: str = "files/src/App.vue",
    max_prompt_files: int = 3,
    files: list[str] | None = None,
) -> Path:
    tdir = template_dir / "templates" / template_id
    tdir.mkdir(parents=True, exist_ok=True)
    data = {
        "schemaVersion": "ac-template/v1",
        "id": template_id,
        "name": name,
        "description": description,
        "codeGenType": code_gen_type,
        "entry": entry,
        "maxPromptFiles": max_prompt_files,
        "files": files or ["files/src/App.vue"],
    }
    tfile = tdir / "template.json"
    tfile.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    files_dir = tdir / "files" / "src"
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "App.vue").write_text("<template>Dashboard</template>", encoding="utf-8")

    return tdir


class TestTemplateLoader:
    def test_load_template(self, template_dir: Path) -> None:
        _create_template_json(template_dir)
        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        template = registry.get("dashboard-analytics")
        assert template.name == "Analytics Dashboard"
        assert template.code_gen_type == "vue_project"
        assert template.max_prompt_files == 3
        assert len(template.files) == 1

    def test_load_multiple_templates(self, template_dir: Path) -> None:
        _create_template_json(template_dir, "dashboard-a", name="Dashboard A")
        _create_template_json(template_dir, "dashboard-b", name="Dashboard B")
        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 2

    def test_skip_invalid_template(self, template_dir: Path) -> None:
        tdir = template_dir / "templates" / "bad-template"
        tdir.mkdir(parents=True)
        tfile = tdir / "template.json"
        tfile.write_text("not json", encoding="utf-8")

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_skip_missing_name(self, template_dir: Path) -> None:
        tdir = template_dir / "templates" / "no-name"
        tdir.mkdir(parents=True)
        tfile = tdir / "template.json"
        tfile.write_text(json.dumps({"id": "no-name"}), encoding="utf-8")

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_no_templates_dir(self, tmp_path: Path) -> None:
        config = AssetPathConfig(bundled_root=tmp_path)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_skip_no_template_json(self, template_dir: Path) -> None:
        tdir = template_dir / "templates" / "no-json"
        tdir.mkdir(parents=True)

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert len(registry.all()) == 0

    def test_default_values(self, template_dir: Path) -> None:
        tdir = template_dir / "templates" / "minimal"
        tdir.mkdir(parents=True)
        tfile = tdir / "template.json"
        tfile.write_text(
            json.dumps({"name": "Minimal", "description": "Desc"}),
            encoding="utf-8",
        )

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        t = registry.get("minimal")
        assert t.code_gen_type == ""
        assert t.max_prompt_files == 3

    def test_higher_priority_root_overrides(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        _create_template_json(root_a, "shared-id", name="From A")
        _create_template_json(root_b, "shared-id", name="From B")

        config = AssetPathConfig(bundled_root=root_b, project_root=root_a)
        loader = TemplateLoader()
        registry = loader.load(config)

        t = registry.get("shared-id")
        assert t.name == "From A"

    def test_load_references_and_checklists(self, template_dir: Path) -> None:
        tdir = template_dir / "templates" / "web-prototype"
        tdir.mkdir(parents=True)
        references_dir = tdir / "references"
        references_dir.mkdir(parents=True)
        files_dir = tdir / "files"
        files_dir.mkdir(parents=True)

        (references_dir / "layout.md").write_text("# Layout\n\n- Hero", encoding="utf-8")
        (references_dir / "checklist.md").write_text("# Checklist\n\n- P0 rule", encoding="utf-8")
        (files_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        data = {
            "schemaVersion": "ac-template/v1",
            "id": "web-prototype",
            "name": "Web Prototype",
            "description": "Web prototype reference",
            "kind": "html-reference",
            "codeGenType": "single_file",
            "entry": "index.html",
            "maxPromptFiles": 1,
            "references": ["references/layout.md"],
            "checklists": ["references/checklist.md"],
            "files": ["files/index.html"],
        }
        (tdir / "template.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        template = registry.get("web-prototype")
        assert template.kind == "html-reference"
        assert template.references == (Path("references/layout.md"),)
        assert template.checklists == (Path("references/checklist.md"),)
        assert template.files == (Path("files/index.html"),)

    def test_load_missing_references_defaults_to_empty(self, template_dir: Path) -> None:
        _create_template_json(template_dir)

        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        template = registry.get("dashboard-analytics")
        assert template.references == ()
        assert template.checklists == ()
        assert template.kind == ""


class TestTemplateRegistry:
    def test_all_returns_registered(self, template_dir: Path) -> None:
        _create_template_json(template_dir, "t1", name="T1")
        _create_template_json(template_dir, "t2", name="T2")
        config = AssetPathConfig(bundled_root=template_dir)
        loader = TemplateLoader()
        registry = loader.load(config)

        all_templates = registry.all()
        assert len(all_templates) == 2

    def test_all_returns_empty_when_none(self, tmp_path: Path) -> None:
        config = AssetPathConfig(bundled_root=tmp_path)
        loader = TemplateLoader()
        registry = loader.load(config)

        assert registry.all() == ()
