from pathlib import Path


from app.artifacts.types import ArtifactManifest
from app.quality.checks import (
    check_artifact_tags_removed,
    check_entry_exists,
    check_non_empty_files,
    check_placeholder_text,
    check_supporting_files_exist,
    check_vue_app_structure,
)
from app.quality.result import CheckResult
from app.quality.structure_checker import StructureChecker


def _make_manifest(**overrides) -> ArtifactManifest:
    defaults = dict(
        version=2,
        kind="vue_project",
        title="Test",
        entry="src/App.vue",
        generation_mode="application",
        artifact_format="vue_project",
        code_gen_type="vue_project",
        supporting_files=["src/App.vue", "package.json", "src/main.ts"],
    )
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


def _setup_vue_project(root: Path) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "App.vue").write_text(
        "<template>\n"
        '  <div v-if="loading">加载中</div>\n'
        '  <div v-else-if="error">错误</div>\n'
        "  <div v-else>Hello World</div>\n"
        "</template>",
        encoding="utf-8",
    )
    (root / "package.json").write_text('{"name": "test", "version": "1.0.0"}', encoding="utf-8")
    (src / "main.ts").write_text('import { createApp } from "vue"', encoding="utf-8")


class TestCheckEntryExists:
    def test_pass_when_exists(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_entry_exists(str(tmp_path), manifest)
        assert result.status == "pass"
        assert result.id == "entry_exists"

    def test_fail_when_missing(self, tmp_path: Path):
        manifest = _make_manifest()
        result = check_entry_exists(str(tmp_path), manifest)
        assert result.status == "fail"
        assert result.severity == "error"


class TestCheckSupportingFilesExist:
    def test_pass_when_all_exist(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_supporting_files_exist(str(tmp_path), manifest)
        assert result.status == "pass"

    def test_warn_when_missing(self, tmp_path: Path):
        manifest = _make_manifest()
        result = check_supporting_files_exist(str(tmp_path), manifest)
        assert result.status == "warn"
        assert result.severity == "warning"


class TestCheckNonEmptyFiles:
    def test_pass_when_content_sufficient(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_non_empty_files(str(tmp_path), manifest)
        assert result.status == "pass"

    def test_fail_when_empty(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text("hi", encoding="utf-8")
        manifest = _make_manifest()
        result = check_non_empty_files(str(tmp_path), manifest)
        assert result.status == "fail"
        assert result.severity == "error"


class TestCheckVueAppStructure:
    def test_pass_when_valid_vue(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_vue_app_structure(str(tmp_path), manifest)
        assert result.status == "pass"

    def test_fail_when_missing_app_vue(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.ts").write_text("import Vue", encoding="utf-8")
        manifest = _make_manifest()
        result = check_vue_app_structure(str(tmp_path), manifest)
        assert result.status == "fail"
        assert "App.vue missing" in result.message

    def test_fail_when_no_template_tag(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text("<script>export default {}</script>", encoding="utf-8")
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (src / "main.ts").write_text("import Vue", encoding="utf-8")
        manifest = _make_manifest()
        result = check_vue_app_structure(str(tmp_path), manifest)
        assert result.status == "fail"
        assert "template" in result.message.lower()

    def test_skip_for_non_vue(self, tmp_path: Path):
        manifest = _make_manifest(artifact_format="web_single_file", code_gen_type="single_file")
        result = check_vue_app_structure(str(tmp_path), manifest)
        assert result.status == "pass"


class TestCheckPlaceholderText:
    def test_pass_when_no_placeholders(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_placeholder_text(str(tmp_path), manifest)
        assert result.status == "pass"

    def test_warn_for_metric_a(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text(
            "<template><div>Metric A: 100</div></template>", encoding="utf-8"
        )
        manifest = _make_manifest(supporting_files=["src/App.vue"])
        result = check_placeholder_text(str(tmp_path), manifest)
        assert result.status == "warn"
        assert result.severity == "warning"

    def test_warn_for_lorem_ipsum(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text(
            "<template><div>Lorem ipsum dolor</div></template>", encoding="utf-8"
        )
        manifest = _make_manifest(supporting_files=["src/App.vue"])
        result = check_placeholder_text(str(tmp_path), manifest)
        assert result.status == "warn"

    def test_warn_for_todo(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text(
            "<template><div>TODO: implement this</div></template>", encoding="utf-8"
        )
        manifest = _make_manifest(supporting_files=["src/App.vue"])
        result = check_placeholder_text(str(tmp_path), manifest)
        assert result.status == "warn"


class TestCheckArtifactTagsRemoved:
    def test_pass_when_no_artifact_tags(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        result = check_artifact_tags_removed(str(tmp_path), manifest)
        assert result.status == "pass"

    def test_warn_when_artifact_tags_present(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (src / "App.vue").write_text(
            "<template><artifact>some code</artifact></template>", encoding="utf-8"
        )
        manifest = _make_manifest(supporting_files=["src/App.vue"])
        result = check_artifact_tags_removed(str(tmp_path), manifest)
        assert result.status == "warn"
        assert "src/App.vue" in result.message


class TestStructureChecker:
    def test_all_pass_for_valid_vue_project(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = _make_manifest()
        checker = StructureChecker()
        results = checker.run(str(tmp_path), manifest)
        assert len(results) >= 5
        assert all(r.status == "pass" for r in results)

    def test_determine_manifest_status_failed(self):
        results = [
            CheckResult(id="entry_exists", status="fail", severity="error", message="Missing"),
        ]
        assert StructureChecker.determine_manifest_status(results) == "failed"

    def test_determine_manifest_status_warnings(self):
        results = [
            CheckResult(id="placeholder_text", status="warn", severity="warning", message="Found"),
        ]
        assert StructureChecker.determine_manifest_status(results) == "complete_with_warnings"

    def test_determine_manifest_status_complete(self):
        results = [
            CheckResult(id="entry_exists", status="pass", severity="error", message="OK"),
        ]
        assert StructureChecker.determine_manifest_status(results) == "complete"
