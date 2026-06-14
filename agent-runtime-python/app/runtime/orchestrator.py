import logging
import time

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.graph.definitions import GENERATION_V1, MODIFICATION_V1
from app.graph.workflow import WorkflowEngine
from app.modeling.policy import ModelPolicy
from app.modeling.resolver import ModelResolver
from app.nodes.prepare_context import PrepareContextNode
from app.nodes.classify_task import ClassifyTaskNode
from app.nodes.resolve_model import ResolveModelNode
from app.nodes.compose_prompt import ComposePromptNode
from app.nodes.call_model import CallModelNode
from app.nodes.execute_tools import ExecuteToolsNode
from app.nodes.finalize import FinalizeNode
from app.prompts.default_modules import DEFAULT_PROMPT_MODULES
from app.registries.node_registry import NodeRegistry
from app.registries.prompt_module_registry import PromptModuleRegistry
from app.registries.tool_registry import ToolRegistry
from app.runtime.context import CodeGenType, ExecutionContext, RunMode, ChatHistoryEntry, AppContext
from app.runtime.event_bus import EventBus
from app.runtime.event_mapper import ProtoEventMapper
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.runtime.state import ExecutionState
from app.services.chat_model_factory import ChatModelFactory
from app.grpc_client.platform_client import GrpcPlatformClient

logger = logging.getLogger("app.runtime.orchestrator")


def _map_code_gen_type(proto_value: int) -> CodeGenType:
    mapping = {
        1: CodeGenType.SINGLE_FILE,
        2: CodeGenType.MULTI_FILE,
        3: CodeGenType.VUE_PROJECT,
    }
    return mapping.get(proto_value, CodeGenType.VUE_PROJECT)


class RuntimeOrchestrator:
    def __init__(self) -> None:
        self._platform_client = GrpcPlatformClient()
        self._chat_model_factory = ChatModelFactory()
        self._model_policy = ModelPolicy()
        self._model_resolver = ModelResolver(self._platform_client)
        self._node_registry = self._build_node_registry()
        self._prompt_module_registry = self._build_prompt_module_registry()
        self._tool_registry = ToolRegistry()
        self._workflow_engine = WorkflowEngine(self._node_registry)
        self._event_mapper = ProtoEventMapper()

    def _build_node_registry(self) -> NodeRegistry:
        registry = NodeRegistry()
        registry.register(PrepareContextNode())
        registry.register(ClassifyTaskNode())
        registry.register(ResolveModelNode())
        registry.register(ComposePromptNode())
        registry.register(CallModelNode())
        registry.register(ExecuteToolsNode())
        registry.register(FinalizeNode())
        return registry

    def _build_prompt_module_registry(self) -> PromptModuleRegistry:
        registry = PromptModuleRegistry()
        for module_cls in DEFAULT_PROMPT_MODULES:
            registry.register(module_cls())
        return registry

    def _build_services(self, event_bus: EventBus) -> RuntimeServices:
        return RuntimeServices(
            platform_client=self._platform_client,
            tool_client=None,
            chat_model_factory=self._chat_model_factory,
            model_policy=self._model_policy,
            model_resolver=self._model_resolver,
            prompt_composer=None,
            prompt_module_registry=self._prompt_module_registry,
            tool_registry=self._tool_registry,
            event_bus=event_bus,
            node_registry=self._node_registry,
        )

    async def _build_context(self, request, run_mode: RunMode) -> ExecutionContext:
        code_gen_type = _map_code_gen_type(request.code_gen_type)
        original_content = getattr(request, "original_content", "")
        model_config_id = getattr(request, "model_config_id", 0)
        config_version = getattr(request, "config_version", 0)

        app: AppContext | None = None
        if request.app_id > 0:
            try:
                app_detail = await self._platform_client.get_app_detail(request.app_id)
                app = AppContext(
                    id=app_detail.get("id", 0),
                    name=app_detail.get("name", ""),
                    description=app_detail.get("description", ""),
                    code_gen_type=_map_code_gen_type(app_detail.get("codeGenType", 3)),
                    user_id=app_detail.get("userId", 0),
                )
            except Exception as e:
                logger.warning("failed to load app detail: %s", e)

        chat_history: tuple[ChatHistoryEntry, ...] = ()
        if request.session_id > 0:
            try:
                history = await self._platform_client.get_chat_history(request.session_id)
                chat_history = tuple(
                    ChatHistoryEntry(id=h["id"], role=h["role"], content=h["content"])
                    for h in history
                )
            except Exception as e:
                logger.warning("failed to load chat history: %s", e)

        return ExecutionContext(
            agent_run_id=int(request.agent_run_id),
            app_id=request.app_id,
            session_id=request.session_id,
            user_id=request.user_id,
            prompt=request.prompt,
            code_gen_type=code_gen_type,
            workspace_path=request.workspace_path or "",
            run_mode=run_mode,
            app=app,
            chat_history=chat_history,
            original_content=original_content,
            runtime_options={
                "model_config_id": model_config_id,
                "config_version": config_version,
            },
        )

    async def stream_generate(self, request):
        async for event in self._run_workflow(request, RunMode.GENERATE, GENERATION_V1):
            yield event

    async def stream_modify(self, request):
        async for event in self._run_workflow(request, RunMode.MODIFY, MODIFICATION_V1):
            yield event

    async def _run_workflow(self, request, run_mode: RunMode, definition: list[str]):
        agent_run_id = int(request.agent_run_id)
        event_bus = EventBus(agent_run_id=agent_run_id)
        services = self._build_services(event_bus)
        start_time = time.monotonic()

        try:
            context = await self._build_context(request, run_mode)
            state = ExecutionState()
            state = await self._workflow_engine.execute(definition, context, state, services)
        except AgentRuntimeError as e:
            logger.error("orchestrator error | agentRunId=%s error=%s", agent_run_id, e)
            await event_bus.emit(
                RuntimeEvent(RuntimeEventType.RUNTIME_ERROR, {"message": str(e), "code": int(e.code)})
            )
            await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"运行失败: {e}"}))
            try:
                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id, success=False, error_message=str(e),
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("orchestrator unexpected error | agentRunId=%s error=%s", agent_run_id, e, exc_info=True)
            await event_bus.emit(
                RuntimeEvent(RuntimeEventType.RUNTIME_ERROR, {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR})
            )
            await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"运行异常: {e}"}))
            try:
                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id, success=False, error_message=str(e),
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                )
            except Exception:
                pass
        finally:
            await event_bus.close()

        async for seq_event in self._drain_events(event_bus):
            proto_event = self._event_mapper.map_event(seq_event)
            if proto_event is not None:
                yield proto_event

    async def _drain_events(self, event_bus: EventBus):
        while True:
            seq_event = await event_bus.next_event()
            if seq_event is None:
                break
            yield seq_event
