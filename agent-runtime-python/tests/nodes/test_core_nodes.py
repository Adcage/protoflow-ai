import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock

from app.modeling.policy import ModelPolicy
from app.modeling.resolver import ResolvedModelConfig, ModelRole
from app.nodes.prepare_context import PrepareContextNode
from app.nodes.classify_task import ClassifyTaskNode
from app.nodes.resolve_model import ResolveModelNode
from app.nodes.compose_prompt import ComposePromptNode
from app.nodes.execute_tools import ExecuteToolsNode
from app.nodes.finalize import FinalizeNode
from app.runtime.context import CodeGenType, ExecutionContext, RunMode
from app.runtime.event_bus import EventBus
from app.runtime.events import RuntimeEventType
from app.runtime.services import RuntimeServices
from app.runtime.state import ExecutionState
from app.capabilities.common.capability_selection import CapabilitySelection
from app.core.exceptions import AgentRuntimeError


def _make_context(**overrides) -> ExecutionContext:
    defaults = dict(
        agent_run_id=1,
        app_id=1,
        session_id=1,
        user_id=1,
        prompt="生成一个 Vue 页面",
        code_gen_type=CodeGenType.VUE_PROJECT,
        workspace_path=tempfile.mkdtemp(),
        run_mode=RunMode.GENERATE,
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


def _make_services(**overrides) -> RuntimeServices:
    defaults = dict(
        platform_client=AsyncMock(),
        tool_client=None,
        chat_model_factory=None,
        model_policy=ModelPolicy(),
        model_resolver=None,
        prompt_composer=None,
        prompt_module_registry=None,
        tool_registry=None,
        event_bus=EventBus(agent_run_id=1),
        node_registry=None,
    )
    defaults.update(overrides)
    return RuntimeServices(**defaults)


class TestPrepareContextNode:
    @pytest.mark.asyncio
    async def test_sets_task_type(self):
        node = PrepareContextNode()
        ctx = _make_context()
        state = ExecutionState()
        services = _make_services()
        result = await node.run(ctx, state, services)
        assert result.task_type == "generate"

    @pytest.mark.asyncio
    async def test_empty_prompt_raises(self):
        node = PrepareContextNode()
        ctx = _make_context(prompt="")
        state = ExecutionState()
        services = _make_services()
        with pytest.raises(AgentRuntimeError, match="提示词不能为空"):
            await node.run(ctx, state, services)


class TestClassifyTaskNode:
    @pytest.mark.asyncio
    async def test_generate_mode(self):
        node = ClassifyTaskNode()
        ctx = _make_context(run_mode=RunMode.GENERATE)
        state = ExecutionState()
        result = await node.run(ctx, state, _make_services())
        assert result.task_type == "generate"

    @pytest.mark.asyncio
    async def test_modify_mode(self):
        node = ClassifyTaskNode()
        ctx = _make_context(run_mode=RunMode.MODIFY)
        state = ExecutionState()
        result = await node.run(ctx, state, _make_services())
        assert result.task_type == "modify"


class TestResolveModelNode:
    @pytest.mark.asyncio
    async def test_resolves_primary_model(self):
        node = ResolveModelNode()
        ctx = _make_context()
        state = ExecutionState()
        mock_resolver = MagicMock()
        mock_resolver.load_bundle = AsyncMock()
        mock_resolver.resolve.return_value = ResolvedModelConfig(
            role=ModelRole.PRIMARY,
            provider="openai",
            model_name="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key="key",
        )
        services = _make_services(model_resolver=mock_resolver)
        result = await node.run(ctx, state, services)
        assert result.resolved_model is not None
        assert result.resolved_model["modelName"] == "gpt-4o"
        assert result.selected_model_role == ModelRole.PRIMARY


class TestComposePromptNode:
    @pytest.mark.asyncio
    async def test_composes_messages(self):
        node = ComposePromptNode()
        ctx = _make_context()
        state = ExecutionState()
        services = _make_services()
        result = await node.run(ctx, state, services)
        assert len(result.prompt_messages) >= 1
        assert result.prompt_messages[-1]["role"] == "user"


class TestExecuteToolsNode:
    @pytest.mark.asyncio
    async def test_executes_write_file_from_tool_calls(self):
        node = ExecuteToolsNode()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_context(workspace_path=tmpdir)
            state = ExecutionState(
                model_tool_calls=[
                    {
                        "id": "call_1",
                        "name": "write_file",
                        "arguments": {
                            "relative_path": "src/App.vue",
                            "content": "<template>Hello</template>",
                        },
                    },
                ]
            )
            services = _make_services()
            result = await node.run(ctx, state, services)
            assert len(result.executed_tool_calls) == 1
            assert "src/App.vue" in result.files_touched
            assert os.path.exists(os.path.join(tmpdir, "src", "App.vue"))

    @pytest.mark.asyncio
    async def test_executes_json_output(self):
        node = ExecuteToolsNode()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_context(workspace_path=tmpdir)
            state = ExecutionState(
                model_response_text='{"message": "done", "files": [{"path": "a.txt", "content": "hi"}]}'
            )
            services = _make_services()
            result = await node.run(ctx, state, services)
            assert "a.txt" in result.files_touched

    @pytest.mark.asyncio
    async def test_no_tool_calls_no_json_skips(self):
        node = ExecuteToolsNode()
        ctx = _make_context()
        state = ExecutionState(model_response_text="plain text response")
        services = _make_services()
        result = await node.run(ctx, state, services)
        assert len(result.executed_tool_calls) == 0


class TestFinalizeNode:
    @pytest.mark.asyncio
    async def test_completes_agent_run(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(files_touched=["a.vue"])
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        mock_platform.complete_agent_run.assert_called_once()
        assert result.final_summary != ""

    @pytest.mark.asyncio
    async def test_emits_done_event(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState()
        event_bus = EventBus(agent_run_id=1)
        services = _make_services(event_bus=event_bus, platform_client=AsyncMock())
        await node.run(ctx, state, services)
        await event_bus.close()
        events = []
        while True:
            e = await event_bus.next_event()
            if e is None:
                break
            events.append(e)
        done_events = [e for e in events if e.event.event_type == RuntimeEventType.DONE]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_summary_excludes_internal_details(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            files_touched=["a.vue", "b.vue"],
            selected_skill_id="dashboard",
            selected_design_system_id="default",
            artifact_manifest_path="/tmp/.acai/artifact-manifest.json",
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "2 个文件" in result.final_summary
        assert "Skill" not in result.final_summary
        assert "Design System" not in result.final_summary
        assert "Manifest" not in result.final_summary
        assert "Skill: dashboard" in result.internal_summary
        assert "Design System: default" in result.internal_summary
        assert "Manifest" in result.internal_summary

    @pytest.mark.asyncio
    async def test_summary_includes_quality_results(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            files_touched=["a.vue"],
            quality_results=[
                {"id": "entry_exists", "status": "pass", "severity": "error", "message": "OK"},
                {
                    "id": "placeholder_text",
                    "status": "warn",
                    "severity": "warning",
                    "message": "Found",
                },
                {
                    "id": "non_empty_files",
                    "status": "fail",
                    "severity": "error",
                    "message": "Empty",
                },
            ],
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "质量检查" in result.final_summary
        assert "1 pass" in result.final_summary
        call_args = mock_platform.complete_agent_run.call_args
        assert call_args.kwargs["success"] is False

    @pytest.mark.asyncio
    async def test_warnings_only_still_success(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            files_touched=["a.vue"],
            quality_results=[
                {"id": "entry_exists", "status": "pass", "severity": "error", "message": "OK"},
                {
                    "id": "placeholder_text",
                    "status": "warn",
                    "severity": "warning",
                    "message": "Found",
                },
            ],
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "质量警告" in result.final_summary
        call_args = mock_platform.complete_agent_run.call_args
        assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_internal_summary_includes_capability_selection(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            files_touched=["a.vue"],
            capability_selection=CapabilitySelection(
                skill_ids=("dashboard", "frontend-design"),
                seed_id="vue-dashboard",
                template_ids=("dashboard",),
                design_system_id="ant",
                craft_ids=("anti-ai-slop", "state-coverage"),
                selection_source="selector",
                project_mode="vue_project",
            ),
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "能力选择: selector" in result.internal_summary
        assert "Skill: dashboard,frontend-design" in result.internal_summary
        assert "Seed: vue-dashboard" in result.internal_summary
        assert "Template: dashboard" in result.internal_summary
        assert "DesignSystem: ant" in result.internal_summary
        assert "Craft: anti-ai-slop,state-coverage" in result.internal_summary

    @pytest.mark.asyncio
    async def test_finalize_returns_clarification_summary(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            workflow_route="clarification",
            clarification_questions=[
                {
                    "id": "q1",
                    "question": "需要偏向官网还是后台？",
                    "reason": "决定项目模式",
                    "required": True,
                    "options": ["官网", "后台"],
                },
            ],
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "<planning type=\"clarification\">" in result.final_summary
        assert "需要偏向官网还是后台" in result.final_summary
        call_args = mock_platform.complete_agent_run.call_args
        assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_finalize_returns_plan_confirmation_summary(self):
        node = FinalizeNode()
        ctx = _make_context()
        state = ExecutionState(
            workflow_route="plan_confirmation",
            implementation_outline={
                "title": "后台看板实施计划",
                "summary": "先搭建布局，再生成数据模块。",
                "steps": ["搭建侧边栏", "生成指标卡", "生成图表"],
                "risks": [],
                "assumptions": [],
            },
        )
        mock_platform = AsyncMock()
        services = _make_services(platform_client=mock_platform)
        result = await node.run(ctx, state, services)
        assert "<planning type=\"plan_confirmation\">" in result.final_summary
        assert "后台看板实施计划" in result.final_summary
        call_args = mock_platform.complete_agent_run.call_args
        assert call_args.kwargs["success"] is True
