from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.capabilities.common.asset_index import AssetIndex, AssetManager
from app.capabilities.common.asset_paths import AssetPathConfig
from app.capabilities.craft.registry import CraftRegistry
from app.capabilities.craft.types import CraftDefinition
from app.capabilities.design_systems.registry import DesignSystemRegistry
from app.capabilities.design_systems.types import DesignSystemDefinition, DesignSystemFiles
from app.capabilities.seeds.registry import SeedRegistry
from app.capabilities.seeds.types import SeedDefinition
from app.capabilities.skills.registry import SkillRegistry
from app.capabilities.skills.types import SkillDefinition
from app.capabilities.templates.registry import TemplateRegistry
from app.nodes.load_assets import LoadAssetsNode
from app.nodes.select_capabilities import SelectCapabilitiesNode
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.event_bus import EventBus
from app.runtime.services import RuntimeServices
from app.runtime.state import ExecutionState


def _make_empty_asset_index() -> AssetIndex:
    return AssetIndex(
        skill_registry=SkillRegistry(),
        seed_registry=SeedRegistry(),
        template_registry=TemplateRegistry(),
        design_system_registry=DesignSystemRegistry(),
        craft_registry=CraftRegistry(),
    )


def _make_asset_index_with_data() -> AssetIndex:
    skill_reg = SkillRegistry()
    skill_reg.register(
        SkillDefinition(
            id="dashboard",
            name="Dashboard",
            description="Dashboard skill",
            body="Build a dashboard.",
            source_path=Path("."),
        )
    )

    ds_reg = DesignSystemRegistry()
    ds_reg.register(
        DesignSystemDefinition(
            id="default",
            name="Default",
            category="product",
            description="Default design system",
            import_mode="normalized",
            files=DesignSystemFiles(design=Path("/tmp/DESIGN.md")),
            suggested_craft=("anti-ai-slop",),
            source_path=Path("."),
        )
    )

    seed_reg = SeedRegistry()
    seed_reg.register(
        SeedDefinition(
            id="vue-basic",
            name="Vue Basic",
            description="Basic Vue seed",
            code_gen_type="vue_project",
            entry="src/App.vue",
            files_dir=Path("/tmp/seed-files"),
            copy_mode="missing-only",
            source_path=Path("."),
        )
    )

    craft_reg = CraftRegistry()
    craft_reg.register(
        CraftDefinition(
            id="anti-ai-slop",
            name="Anti AI Slop",
            description="Anti slop rules",
            applies_to=(),
            priority=50,
            body="No lorem ipsum.",
            source_path=Path("."),
        )
    )
    craft_reg.register(
        CraftDefinition(
            id="state-coverage",
            name="State Coverage",
            description="State coverage rules",
            applies_to=(),
            priority=60,
            body="Include loading states.",
            source_path=Path("."),
        )
    )

    return AssetIndex(
        skill_registry=skill_reg,
        seed_registry=seed_reg,
        template_registry=TemplateRegistry(),
        design_system_registry=ds_reg,
        craft_registry=craft_reg,
    )


def _make_context(
    prompt: str = "生成一个后台数据看板",
    code_gen_type: CodeGenType = CodeGenType.VUE_PROJECT,
    run_mode: RunMode = RunMode.GENERATE,
    workspace_path: str = "/tmp/workspace",
) -> ExecutionContext:
    return ExecutionContext(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt=prompt,
        code_gen_type=code_gen_type,
        workspace_path=workspace_path,
        run_mode=run_mode,
    )


def _make_services(asset_manager: AssetManager | None = None) -> RuntimeServices:
    event_bus = EventBus(agent_run_id=1)
    return RuntimeServices(
        asset_manager=asset_manager,
        event_bus=event_bus,
    )


class TestLoadAssetsNode:
    @pytest.mark.asyncio
    async def test_load_assets_populates_counts(self, tmp_path: Path):
        bundled = tmp_path / "bundled"
        skills_dir = bundled / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "dashboard"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: dashboard\ndescription: test\n---\n\n# Dashboard\n",
            encoding="utf-8",
        )
        (bundled / "seeds").mkdir()
        (bundled / "templates").mkdir()
        (bundled / "design-systems").mkdir()
        (bundled / "craft").mkdir()

        config = AssetPathConfig(bundled_root=bundled)
        mgr = AssetManager(path_config=config)
        services = _make_services(asset_manager=mgr)
        state = ExecutionState()
        context = _make_context()

        node = LoadAssetsNode()
        result = await node.run(context, state, services)

        assert result.asset_counts["skills"] == 1
        assert result.asset_counts["seeds"] == 0
        assert result.asset_counts["templates"] == 0
        assert result.asset_counts["design_systems"] == 0
        assert result.asset_counts["crafts"] == 0

    @pytest.mark.asyncio
    async def test_load_assets_raises_without_manager(self):
        services = _make_services(asset_manager=None)
        state = ExecutionState()
        context = _make_context()

        node = LoadAssetsNode()
        with pytest.raises(Exception, match="AssetManager"):
            await node.run(context, state, services)


class TestLoadAssetsNodeAssetSummaries:
    @pytest.mark.asyncio
    async def test_load_assets_generates_asset_summaries(self):
        index = _make_asset_index_with_data()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context()

        node = LoadAssetsNode()
        result = await node.run(context, state, services)

        assert len(result.asset_summaries) > 0
        summary_ids = [s["id"] for s in result.asset_summaries]
        assert "dashboard" in summary_ids
        assert "vue-basic" in summary_ids
        assert "default" in summary_ids
        assert "anti-ai-slop" in summary_ids
        assert "state-coverage" in summary_ids

        dashboard = next(s for s in result.asset_summaries if s["id"] == "dashboard")
        assert dashboard["kind"] == "skill"
        assert dashboard["name"] == "Dashboard"

        vue_basic = next(s for s in result.asset_summaries if s["id"] == "vue-basic")
        assert vue_basic["kind"] == "seed"
        assert vue_basic["code_gen_types"] == ("vue_project",)

        default_ds = next(s for s in result.asset_summaries if s["id"] == "default")
        assert default_ds["kind"] == "design_system"
        assert default_ds["scenarios"] == ("product",)

        anti_slop = next(s for s in result.asset_summaries if s["id"] == "anti-ai-slop")
        assert anti_slop["kind"] == "craft"

    @pytest.mark.asyncio
    async def test_load_assets_empty_summaries_when_no_assets(self):
        index = _make_empty_asset_index()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context()

        node = LoadAssetsNode()
        result = await node.run(context, state, services)

        assert result.asset_summaries == []


class TestSelectCapabilitiesNode:
    @pytest.mark.asyncio
    async def test_selects_skill_and_capabilities(self, tmp_path: Path):
        index = _make_asset_index_with_data()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context(workspace_path=str(workspace))

        node = SelectCapabilitiesNode()
        result = await node.run(context, state, services)

        assert result.selected_skill_id == "dashboard"
        assert result.selected_design_system_id == "default"
        assert result.selected_seed_id == "vue-basic"
        assert result.selected_capabilities is not None
        assert result.selected_capabilities.skill is not None
        assert result.selected_capabilities.skill.id == "dashboard"

    @pytest.mark.asyncio
    async def test_seeds_only_for_vue_project(self, tmp_path: Path):
        index = _make_asset_index_with_data()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context(
            prompt="生成单文件页面",
            code_gen_type=CodeGenType.SINGLE_FILE,
            workspace_path=str(workspace),
        )

        node = SelectCapabilitiesNode()
        result = await node.run(context, state, services)

        assert result.selected_seed_id == ""

    @pytest.mark.asyncio
    async def test_modify_mode_no_seed(self, tmp_path: Path):
        index = _make_asset_index_with_data()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context(
            prompt="修改后台数据看板",
            run_mode=RunMode.MODIFY,
        )

        node = SelectCapabilitiesNode()
        result = await node.run(context, state, services)

        assert result.selected_seed_id == ""
        assert result.selected_capabilities.seed is None

    @pytest.mark.asyncio
    async def test_craft_ids_from_design_system_suggested(self, tmp_path: Path):
        index = _make_asset_index_with_data()

        mock_manager = MagicMock(spec=AssetManager)
        mock_manager.get_index.return_value = index

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        services = _make_services(asset_manager=mock_manager)
        state = ExecutionState()
        context = _make_context(workspace_path=str(workspace))

        node = SelectCapabilitiesNode()
        result = await node.run(context, state, services)

        assert "anti-ai-slop" in result.selected_craft_ids
        assert "state-coverage" in result.selected_craft_ids

    @pytest.mark.asyncio
    async def test_raises_without_asset_manager(self):
        services = _make_services(asset_manager=None)
        state = ExecutionState()
        context = _make_context()

        node = SelectCapabilitiesNode()
        with pytest.raises(Exception, match="AssetManager"):
            await node.run(context, state, services)
