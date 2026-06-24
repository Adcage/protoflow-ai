from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.artifacts.format_registry import (
    ArtifactFormatRegistry,
    ArtifactFormatHandler,
    create_application_format_registry,
)
from app.artifacts.types import ArtifactManifest
from app.artifacts.writer import ArtifactWriter


def _make_v2_manifest(
    generation_mode: str = "application",
    artifact_format: str = "web_single_file",
    entry: str = "index.html",
    **overrides,
) -> ArtifactManifest:
    defaults = dict(
        version=2,
        kind=artifact_format,
        title="Test",
        entry=entry,
        generation_mode=generation_mode,
        artifact_format=artifact_format,
        code_gen_type="",
        supporting_files=["index.html"],
        status="complete",
    )
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


class TestManifestV2Roundtrip:
    def test_manifest_v2_roundtrip(self, tmp_path: Path):
        manifest = _make_v2_manifest(
            generation_mode="application",
            artifact_format="vue_project",
            entry="src/App.vue",
            supporting_files=["src/App.vue", "package.json"],
        )
        writer = ArtifactWriter()
        writer.write(str(tmp_path), manifest)

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.version == 2
        assert loaded.generation_mode == "application"
        assert loaded.artifact_format == "vue_project"
        assert loaded.entry == "src/App.vue"


class TestManifestV1ReadMapsKnownTypes:
    def test_manifest_v1_read_maps_known_types(self, tmp_path: Path):
        v1_data = {
            "version": 1,
            "kind": "vue_project",
            "title": "Old App",
            "entry": "src/App.vue",
            "codeGenType": "vue_project",
            "supportingFiles": ["src/App.vue"],
            "status": "complete",
        }
        manifest_dir = tmp_path / ".acai"
        manifest_dir.mkdir()
        (manifest_dir / "artifact-manifest.json").write_text(
            json.dumps(v1_data), encoding="utf-8"
        )

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.generation_mode == "application"
        assert loaded.artifact_format == "vue_project"

    def test_manifest_v1_read_maps_single_file(self, tmp_path: Path):
        v1_data = {
            "version": 1,
            "kind": "single_file",
            "entry": "index.html",
            "codeGenType": "single_file",
            "supportingFiles": ["index.html"],
            "status": "complete",
        }
        manifest_dir = tmp_path / ".acai"
        manifest_dir.mkdir()
        (manifest_dir / "artifact-manifest.json").write_text(
            json.dumps(v1_data), encoding="utf-8"
        )

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.generation_mode == "application"
        assert loaded.artifact_format == "web_single_file"

    def test_manifest_v1_read_maps_multi_file(self, tmp_path: Path):
        v1_data = {
            "version": 1,
            "kind": "multi-file",
            "entry": "index.html",
            "codeGenType": "multi-file",
            "supportingFiles": ["index.html", "style.css"],
            "status": "complete",
        }
        manifest_dir = tmp_path / ".acai"
        manifest_dir.mkdir()
        (manifest_dir / "artifact-manifest.json").write_text(
            json.dumps(v1_data), encoding="utf-8"
        )

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.generation_mode == "application"
        assert loaded.artifact_format == "web_multi_file"


class TestWriterNeverEmitsCodeGenType:
    def test_writer_never_emits_code_gen_type(self, tmp_path: Path):
        manifest = _make_v2_manifest(code_gen_type="vue_project")
        writer = ArtifactWriter()
        path = writer.write(str(tmp_path), manifest)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "codeGenType" not in data
        assert "code_gen_type" not in data
        assert data["generationMode"] == "application"
        assert data["artifactFormat"] == "web_single_file"


class TestExpectedActualFormatMismatchIsValidationError:
    def test_format_outside_mode_rejected_by_dispatcher(self):
        from app.agent_loop.execution_contract import ExecutionContract
        from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcher
        from app.agent_loop.state import AgentLoopState
        from app.core.exceptions import AgentRuntimeError
        from app.generation_modes.registry import GenerationModeRegistry
        from app.generation_modes.types import GenerationModeDefinition
        from app.agent_loop.agents.application import ApplicationImplementAgent

        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(
            mode_id="application",
            plan_prompt_module_ids=("application_plan",),
            implement_agent_factory=ApplicationImplementAgent,
            validate_prompt_module_ids=("application_validate",),
            supported_artifact_formats=frozenset({"web_single_file", "web_multi_file", "vue_project"}),
        ))
        dispatcher = ImplementDispatcher(registry)
        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="pptx",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.pptx"]}],
        )
        state = AgentLoopState(mode="implement", status="running")
        envelope = state._to_envelope()
        envelope.workflow.execution.execution_contract = contract.model_dump()
        state._state_envelope = envelope

        import asyncio
        with pytest.raises(AgentRuntimeError, match="不受模式"):
            asyncio.get_event_loop().run_until_complete(
                dispatcher.dispatch(state, None, None, None)
            )


class TestApplicationFormatChecks:
    def test_web_single_file_has_correct_checks(self):
        registry = create_application_format_registry()
        handler = registry.require("web_single_file")
        assert "entry_exists" in handler.checks
        assert "non_empty_files" in handler.checks
        assert "no_placeholder_text" in handler.checks

    def test_vue_project_has_structure_check(self):
        registry = create_application_format_registry()
        handler = registry.require("vue_project")
        assert "vue_app_structure" in handler.checks

    def test_web_multi_file_has_supporting_check(self):
        registry = create_application_format_registry()
        handler = registry.require("web_multi_file")
        assert "supporting_files_exist" in handler.checks

    def test_unknown_format_raises(self):
        registry = create_application_format_registry()
        with pytest.raises(Exception, match="unknown"):
            registry.require("unknown_format")

    def test_duplicate_format_rejected(self):
        registry = ArtifactFormatRegistry()
        registry.register(
            ArtifactFormatHandler(
                format_id="web_single_file",
                entry_inference=lambda files, root="": "index.html",
                checks=["entry_exists"],
            )
        )
        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                ArtifactFormatHandler(
                    format_id="web_single_file",
                    entry_inference=lambda files, root="": "index.html",
                    checks=["entry_exists"],
                )
            )
