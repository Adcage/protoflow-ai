import json
import os
from pathlib import Path


from app.artifacts.types import ArtifactCheckResult, ArtifactManifest
from app.artifacts.writer import ArtifactWriter


def _make_manifest(**overrides) -> ArtifactManifest:
    defaults = dict(
        version=2,
        kind="vue_project",
        title="Test App",
        entry="src/App.vue",
        generation_mode="application",
        artifact_format="vue_project",
        code_gen_type="",
        supporting_files=["src/App.vue", "package.json", "src/main.ts"],
        source_skill_id="dashboard",
        source_seed_id="vue-basic",
        source_template_id="",
        design_system_id="default",
        craft_ids=["anti-slop"],
    )
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


class TestArtifactWriter:
    def test_writes_camel_case_json(self, tmp_path: Path):
        writer = ArtifactWriter()
        manifest = _make_manifest()
        path = writer.write(str(tmp_path), manifest)

        assert os.path.exists(path)
        assert path.endswith(os.path.join(".acai", "artifact-manifest.json"))

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == 2
        assert data["kind"] == "vue_project"
        assert data["entry"] == "src/App.vue"
        assert "codeGenType" not in data
        assert data["generationMode"] == "application"
        assert data["artifactFormat"] == "vue_project"
        assert data["supportingFiles"] == ["src/App.vue", "package.json", "src/main.ts"]
        assert data["sourceSkillId"] == "dashboard"
        assert data["sourceSeedId"] == "vue-basic"
        assert data["sourceTemplateId"] == ""
        assert data["designSystemId"] == "default"
        assert data["craftIds"] == ["anti-slop"]
        assert "code_gen_type" not in data
        assert "supporting_files" not in data

    def test_writes_checks(self, tmp_path: Path):
        writer = ArtifactWriter()
        manifest = _make_manifest(
            checks=[
                ArtifactCheckResult(
                    id="entry_exists", status="pass", message="Entry exists", severity="error"
                ),
                ArtifactCheckResult(
                    id="placeholder_text",
                    status="warn",
                    message="Placeholder found",
                    severity="warning",
                ),
            ],
        )
        path = writer.write(str(tmp_path), manifest)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["checks"]) == 2
        assert data["checks"][0]["id"] == "entry_exists"
        assert data["checks"][0]["status"] == "pass"
        assert data["checks"][1]["id"] == "placeholder_text"
        assert data["checks"][1]["status"] == "warn"

    def test_creates_acai_directory(self, tmp_path: Path):
        writer = ArtifactWriter()
        manifest = _make_manifest()
        writer.write(str(tmp_path), manifest)

        assert os.path.isdir(os.path.join(str(tmp_path), ".acai"))

    def test_read_roundtrip(self, tmp_path: Path):
        writer = ArtifactWriter()
        manifest = _make_manifest(
            checks=[
                ArtifactCheckResult(
                    id="entry_exists", status="pass", message="OK", severity="error"
                )
            ],
        )
        writer.write(str(tmp_path), manifest)

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.version == manifest.version
        assert loaded.kind == manifest.kind
        assert loaded.entry == manifest.entry
        assert loaded.generation_mode == manifest.generation_mode
        assert loaded.artifact_format == manifest.artifact_format
        assert loaded.source_skill_id == manifest.source_skill_id
        assert loaded.craft_ids == manifest.craft_ids
        assert len(loaded.checks) == 1
        assert loaded.checks[0].id == "entry_exists"

    def test_read_returns_none_when_missing(self, tmp_path: Path):
        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is None

    def test_status_and_metadata(self, tmp_path: Path):
        writer = ArtifactWriter()
        manifest = _make_manifest(
            status="complete_with_warnings",
            metadata={"agentRunId": 123, "appId": 456},
        )
        path = writer.write(str(tmp_path), manifest)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["status"] == "complete_with_warnings"
        assert data["metadata"]["agentRunId"] == 123

    def test_serializes_capability_selection_fields(self, tmp_path: Path):
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Dashboard",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            source_skill_id="dashboard",
            source_skill_ids=["frontend-design", "dashboard"],
            source_template_id="dashboard",
            source_template_ids=["dashboard"],
            selection_source="selector",
            project_mode="vue_project",
        )

        path = ArtifactWriter().write(str(tmp_path), manifest)
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        assert data["sourceSkillIds"] == ["frontend-design", "dashboard"]
        assert data["sourceTemplateIds"] == ["dashboard"]
        assert data["selectionSource"] == "selector"
        assert data["projectMode"] == "vue_project"

    def test_reads_capability_selection_fields(self, tmp_path: Path):
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Dashboard",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            source_skill_ids=["frontend-design", "dashboard"],
            source_template_ids=["dashboard"],
            selection_source="selector",
            project_mode="vue_project",
        )

        ArtifactWriter().write(str(tmp_path), manifest)
        loaded = ArtifactWriter.read(str(tmp_path))

        assert loaded.source_skill_ids == ["frontend-design", "dashboard"]
        assert loaded.source_template_ids == ["dashboard"]
        assert loaded.selection_source == "selector"
        assert loaded.project_mode == "vue_project"
