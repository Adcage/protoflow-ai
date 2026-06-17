import os
from pathlib import Path

import pytest

from app.artifacts.writer import ArtifactWriter
from app.capabilities.common.loader_result import SelectedCapabilities
from app.capabilities.seeds.types import SeedDefinition
from app.capabilities.skills.types import SkillDefinition
from app.nodes.collect_artifacts import CollectArtifactsNode
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


def _make_services(event_bus: EventBus | None = None) -> RuntimeServices:
    return RuntimeServices(
        event_bus=event_bus or EventBus(agent_run_id=1),
        artifact_writer=ArtifactWriter(),
    )


class TestCollectArtifactsNode:
    @pytest.mark.asyncio
    async def test_skill_selected_workspace_files_collected(self, tmp_path: Path):
        node = CollectArtifactsNode()
        context = _make_context(workspace_path=str(tmp_path))
        skill = SkillDefinition(
            id="dashboard",
            name="dashboard",
            description="Dashboard",
            body="Build dashboard",
            source_path=Path("."),
        )
        state = ExecutionState(
            files_touched=["index.html", "app.js"],
            selected_skill_id="dashboard",
            selected_capabilities=SelectedCapabilities(skills=[skill]),
        )
        services = _make_services()

        result = await node.run(context, state, services)

        assert result.artifact_manifest_path != ""
        assert len(result.artifacts) > 0
        assert "entry" in result.artifacts[0]

    @pytest.mark.asyncio
    async def test_seed_entry_used(self, tmp_path: Path):
        node = CollectArtifactsNode()
        context = _make_context(workspace_path=str(tmp_path))
        seed = SeedDefinition(
            id="vue-basic",
            name="Vue Basic",
            description="Basic",
            code_gen_type="vue_project",
            entry="src/App.vue",
            files_dir=Path("/tmp/seed"),
            copy_mode="missing-only",
            source_path=Path("."),
        )
        state = ExecutionState(
            files_touched=["src/App.vue", "src/main.ts"],
            selected_seed_id="vue-basic",
            selected_capabilities=SelectedCapabilities(seed=seed),
        )
        services = _make_services()

        result = await node.run(context, state, services)

        assert result.artifacts[0]["entry"] == "src/App.vue"

    @pytest.mark.asyncio
    async def test_vue_project_default_entry_app_vue(self, tmp_path: Path):
        node = CollectArtifactsNode()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("<template></template>", encoding="utf-8")
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState(
            files_touched=["src/App.vue"],
            selected_capabilities=SelectedCapabilities(),
        )
        services = _make_services()

        result = await node.run(context, state, services)

        assert result.artifacts[0]["entry"] == "src/App.vue"

    @pytest.mark.asyncio
    async def test_single_file_uses_index_html(self, tmp_path: Path):
        node = CollectArtifactsNode()
        context = _make_context(
            workspace_path=str(tmp_path),
            code_gen_type=CodeGenType.SINGLE_FILE,
        )
        state = ExecutionState(
            files_touched=["index.html"],
            selected_capabilities=SelectedCapabilities(),
        )
        services = _make_services()

        result = await node.run(context, state, services)

        assert result.artifacts[0]["entry"] == "index.html"

    @pytest.mark.asyncio
    async def test_writes_manifest_file(self, tmp_path: Path):
        node = CollectArtifactsNode()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("<template></template>", encoding="utf-8")
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState(
            files_touched=["src/App.vue", "package.json"],
            selected_skill_id="dashboard",
            selected_design_system_id="default",
            selected_craft_ids=["anti-ai-slop"],
            selected_capabilities=SelectedCapabilities(),
        )
        services = _make_services()

        result = await node.run(context, state, services)

        assert os.path.exists(result.artifact_manifest_path)
        assert ".acai" in result.artifact_manifest_path

    @pytest.mark.asyncio
    async def test_no_writer_still_sets_path(self, tmp_path: Path):
        node = CollectArtifactsNode()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.vue").write_text("<template></template>", encoding="utf-8")
        context = _make_context(workspace_path=str(tmp_path))
        state = ExecutionState(
            files_touched=["src/App.vue"],
            selected_capabilities=SelectedCapabilities(),
        )
        services = RuntimeServices(event_bus=EventBus(agent_run_id=1), artifact_writer=None)

        result = await node.run(context, state, services)

        assert result.artifact_manifest_path != ""
