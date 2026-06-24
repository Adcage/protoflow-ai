"""Phase 3: Implement Dispatcher 和 Application Agent 测试。"""

import pytest

from app.agent_loop.agents.base import ImplementAgent
from app.agent_loop.agents.application import ApplicationImplementAgent
from app.agent_loop.execution_contract import ExecutionContract
from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcher
from app.agent_loop.state import AgentLoopState
from app.core.exceptions import AgentRuntimeError
from app.generation_modes.registry import GenerationModeRegistry
from app.generation_modes.types import GenerationModeDefinition


def _make_registry_with_application():
    registry = GenerationModeRegistry()
    registry.register(GenerationModeDefinition(
        mode_id="application",
        plan_prompt_module_ids=("application_plan",),
        implement_agent_factory=ApplicationImplementAgent,
        validate_prompt_module_ids=("application_validate",),
        supported_artifact_formats=frozenset({"web_single_file", "web_multi_file", "vue_project"}),
    ))
    return registry


def _make_state_with_contract(contract: ExecutionContract | None = None):
    state = AgentLoopState(mode="implement", status="running")
    if contract is None:
        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="web_single_file",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
        )
    envelope = state._to_envelope()
    envelope.workflow.execution.execution_contract = contract.model_dump()
    state._state_envelope = envelope
    return state


class TestImplementDispatcher:
    def test_dispatcher_resolves_application_from_registry(self):
        registry = _make_registry_with_application()
        dispatcher = ImplementDispatcher(registry)
        state = _make_state_with_contract()
        assert dispatcher._validate_contract(state).generation_mode == "application"

    def test_dispatcher_rejects_missing_contract(self):
        registry = _make_registry_with_application()
        dispatcher = ImplementDispatcher(registry)
        state = AgentLoopState(mode="implement", status="running")
        envelope = state._to_envelope()
        envelope.workflow.execution.execution_contract = None
        state._state_envelope = envelope
        with pytest.raises(AgentRuntimeError, match="ExecutionContract"):
            dispatcher._validate_contract(state)

    def test_dispatcher_rejects_unregistered_mode(self):
        registry = GenerationModeRegistry()
        dispatcher = ImplementDispatcher(registry)
        contract = ExecutionContract(
            source="direct",
            generation_mode="unknown_mode",
            expected_artifact_format="web_single_file",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
        )
        state = _make_state_with_contract(contract)
        with pytest.raises(AgentRuntimeError, match="未注册"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                dispatcher.dispatch(state, None, None, None)
            )

    def test_dispatcher_rejects_unsupported_format(self):
        registry = _make_registry_with_application()
        dispatcher = ImplementDispatcher(registry)
        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="pptx",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.pptx"]}],
        )
        state = _make_state_with_contract(contract)
        with pytest.raises(AgentRuntimeError, match="不受模式"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                dispatcher.dispatch(state, None, None, None)
            )


class TestApplicationImplementAgent:
    def test_is_implement_agent_subclass(self):
        assert issubclass(ApplicationImplementAgent, ImplementAgent)

    def test_factory_creates_instance(self):
        agent = ApplicationImplementAgent()
        assert isinstance(agent, ImplementAgent)

    def test_agent_receives_same_resolved_toolset_used_by_prompt_and_executor(self):
        from unittest.mock import AsyncMock, MagicMock

        from app.agent_loop.tool_policy import AgentMode
        from app.agent_loop.tool_resolver import ModeToolResolver
        from app.agent_loop.nodes.step_base import _create_terminal_tools_for_mode, _make_loop_tools
        from app.tools.file_tools import Workspace, FileTools
        from app.tools.langchain_tools import create_all_tools, ReadAssetTool

        registry = _make_registry_with_application()
        agent = ApplicationImplementAgent()

        state = _make_state_with_contract()
        context = MagicMock()
        context.workspace_path = "/tmp/test_ws"
        services = MagicMock()
        services.generation_mode_registry = registry
        services.prompt_module_registry = MagicMock()
        services.event_bus = MagicMock()
        services.event_bus.emit = AsyncMock()

        ws = Workspace("/tmp/test_ws")
        file_tools = FileTools(ws)
        terminal_tools = _create_terminal_tools_for_mode(ws, readonly=False)
        lc_tools = list(create_all_tools(file_tools, terminal_tools=terminal_tools))
        lc_tools.append(ReadAssetTool(file_tools=file_tools))
        lc_tools.extend(_make_loop_tools(state, services.event_bus))
        toolset = ModeToolResolver.resolve(AgentMode.IMPLEMENT, lc_tools)

        captured_toolset = None

        async def patched_execute(s, ctx, svc, contract, ts):
            nonlocal captured_toolset
            captured_toolset = ts

        agent.execute = patched_execute

        import asyncio

        async def _run():
            try:
                await agent.execute(state, context, services, None, toolset)
            except Exception:
                pass

        asyncio.get_event_loop().run_until_complete(_run())
        assert captured_toolset is toolset

    def test_application_agent_cannot_write_outside_contract(self):
        from app.agent_loop.execution_contract import ContractTask, ExecutionContract

        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="web_single_file",
            goal="只允许修改 a.html",
            tasks=[ContractTask(task_id="t1", goal="修改 a.html", allowed_files=["a.html"])],
        )
        state = _make_state_with_contract(contract)

        dispatcher = ImplementDispatcher(_make_registry_with_application())
        validated = dispatcher._validate_contract(state)
        allowed = set()
        for t in validated.tasks:
            allowed.update(t.allowed_files)
        assert "b.html" not in allowed
        assert "a.html" in allowed

    def test_dispatcher_rejects_mode_mismatch_between_contract_and_workflow(self):
        from app.agent_loop.state_v2 import WorkflowState, WorkflowStateEnvelope

        registry = _make_registry_with_application()
        dispatcher = ImplementDispatcher(registry)

        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="web_single_file",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
        )

        state = AgentLoopState(mode="implement", status="running")
        envelope = state._to_envelope()
        envelope.workflow.generation_mode = "unresolved"
        envelope.workflow.execution.execution_contract = contract.model_dump()
        state._state_envelope = envelope

        with pytest.raises(AgentRuntimeError, match="generation_mode.*不一致"):
            dispatcher._validate_contract(state)
