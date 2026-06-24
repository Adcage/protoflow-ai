from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.artifacts.types import ArtifactManifest
from app.artifacts.writer import ArtifactWriter
from app.nodes.structure_check import StructureCheckNode
from app.quality.result import CheckResult
from app.quality.structure_checker import StructureChecker
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.event_bus import EventBus
from app.runtime.services import RuntimeServices
from app.runtime.state import ExecutionState


def _make_context(**overrides) -> ExecutionContext:
    defaults = dict(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="生成一个数据看板",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path="",
        run_mode=RunMode.GENERATE,
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


def _setup_vue_project(root: Path) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "App.vue").write_text("<template><div>Hello World</div></template>", encoding="utf-8")
    (root / "package.json").write_text('{"name": "test", "version": "1.0.0"}', encoding="utf-8")
    (src / "main.ts").write_text('import { createApp } from "vue"', encoding="utf-8")


def _write_manifest(root: str, manifest: ArtifactManifest) -> str:
    writer = ArtifactWriter()
    return writer.write(root, manifest)


class TestStructureCheckNode:
    @pytest.mark.asyncio
    async def test_writes_quality_results(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Test",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            code_gen_type="vue_project",
            supporting_files=["src/App.vue", "package.json", "src/main.ts"],
        )
        _write_manifest(str(tmp_path), manifest)

        node = StructureCheckNode()
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = RuntimeServices(
            event_bus=event_bus,
            quality_checker=StructureChecker(),
            artifact_writer=ArtifactWriter(),
        )

        result = await node.run(context, state, services)

        assert len(result.quality_results) >= 5
        assert result.quality_results[0]["id"] == "entry_exists"

    @pytest.mark.asyncio
    async def test_updates_manifest_checks(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Test",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            code_gen_type="vue_project",
            supporting_files=["src/App.vue", "package.json", "src/main.ts"],
        )
        _write_manifest(str(tmp_path), manifest)

        node = StructureCheckNode()
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = RuntimeServices(
            event_bus=event_bus,
            quality_checker=StructureChecker(),
            artifact_writer=ArtifactWriter(),
        )

        await node.run(context, state, services)

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert len(loaded.checks) >= 5
        assert loaded.checks[0].id == "entry_exists"
        assert loaded.status == "complete_with_warnings"

    @pytest.mark.asyncio
    async def test_manifest_failed_on_missing_entry(self, tmp_path: Path):
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Test",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            code_gen_type="vue_project",
            supporting_files=["src/App.vue"],
        )
        _write_manifest(str(tmp_path), manifest)

        node = StructureCheckNode()
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = RuntimeServices(
            event_bus=event_bus,
            quality_checker=StructureChecker(),
            artifact_writer=ArtifactWriter(),
        )

        await node.run(context, state, services)

        loaded = ArtifactWriter.read(str(tmp_path))
        assert loaded is not None
        assert loaded.status == "failed"

    @pytest.mark.asyncio
    async def test_skips_when_no_manifest(self, tmp_path: Path):
        node = StructureCheckNode()
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = RuntimeServices(event_bus=event_bus)

        result = await node.run(context, state, services)
        assert len(result.quality_results) == 0

    @pytest.mark.asyncio
    async def test_uses_injected_checker(self, tmp_path: Path):
        _setup_vue_project(tmp_path)
        manifest = ArtifactManifest(
            version=2,
            kind="vue_project",
            title="Test",
            entry="src/App.vue",
            generation_mode="application",
            artifact_format="vue_project",
            code_gen_type="vue_project",
            supporting_files=["src/App.vue"],
        )
        _write_manifest(str(tmp_path), manifest)

        mock_checker = MagicMock(spec=StructureChecker)
        mock_checker.run.return_value = [
            CheckResult(id="entry_exists", status="pass", severity="error", message="OK"),
        ]
        mock_checker.determine_manifest_status = StructureChecker.determine_manifest_status

        node = StructureCheckNode()
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = RuntimeServices(
            event_bus=event_bus,
            quality_checker=mock_checker,
            artifact_writer=ArtifactWriter(),
        )

        result = await node.run(context, state, services)
        mock_checker.run.assert_called_once()
        assert len(result.quality_results) == 1
