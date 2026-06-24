import asyncio
import logging
import time

from app.capabilities.common.asset_index import create_default_asset_manager
from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.modeling.policy import ModelPolicy
from app.modeling.resolver import ModelResolver
from app.artifacts.writer import ArtifactWriter
from app.quality.structure_checker import StructureChecker
from app.runtime.context import CodeGenType, ExecutionContext, RunMode, ChatHistoryEntry, AppContext, _CODE_GEN_TYPE_TO_GENERATION_MODE
from app.runtime.event_bus import EventBus
from app.runtime.event_mapper import ProtoEventMapper
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
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
        self._asset_manager = create_default_asset_manager()
        self._quality_checker = StructureChecker()
        self._artifact_writer = ArtifactWriter()
        self._event_mapper = ProtoEventMapper()

    def _build_services(self, event_bus: EventBus) -> RuntimeServices:
        from app.prompts.registry import PromptModuleRegistry
        from app.prompts.default_modules import (
            RuntimeBoundaryModule,
            SafetyAndInjectionResistanceModule,
            ProjectRulesModule,
            TaskContextModule,
            OutputContractModule,
            AntiRoleplayModule,
        )
        from app.prompts.asset_modules import ArtifactOutputContractModule
        from app.prompts.loop_modules import (
            PlanWorkflowModule,
            ImplementWorkflowModule,
            ValidateWorkflowModule,
            ValidateFeedbackModule,
            ToolListModule,
            PlanSpecModule,
            SkillContextModule,
        )
        from app.prompts.route_modules import (
            RouteInitialModule,
            RouteAfterPlanModule,
            RouteAfterImplementModule,
            RouteAfterValidateModule,
        )
        from app.prompts.test_modules import (
            TestModeInfoModule,
            ProductionSecurityModule,
        )

        registry = PromptModuleRegistry()
        # 按注册顺序排列，决定提示词中的段落顺序
        # mandatory
        registry.register(RuntimeBoundaryModule())
        registry.register(SafetyAndInjectionResistanceModule())
        # test
        registry.register(ProductionSecurityModule())  # is_test=False 时启用
        # strategic - 项目规则
        registry.register(ProjectRulesModule())
        # strategic - 工具列表（动态注入）
        registry.register(ToolListModule())
        # strategic - 路由模块（互斥）
        registry.register(RouteInitialModule())
        registry.register(RouteAfterPlanModule())
        registry.register(RouteAfterImplementModule())
        registry.register(RouteAfterValidateModule())
        # strategic - 大循环工作流（互斥）
        registry.register(PlanWorkflowModule())
        registry.register(ImplementWorkflowModule())
        registry.register(ValidateWorkflowModule())
        registry.register(PlanSpecModule())
        registry.register(ValidateFeedbackModule())
        # strategic - artifact 合约
        registry.register(ArtifactOutputContractModule())
        # mandatory - 输出规则
        registry.register(OutputContractModule())
        registry.register(AntiRoleplayModule())
        # strategic - Skill 上下文
        registry.register(SkillContextModule())
        # strategic - 任务上下文
        registry.register(TaskContextModule())
        # test
        registry.register(TestModeInfoModule())  # is_test=True 时启用

        # 生成模式 Prompt 模块
        from app.prompts.generation_modes.application import (
            ApplicationPlanModule,
            ApplicationValidateModule,
        )
        from app.prompts.generation_modes.common import GenerationModeClarificationModule

        registry.register(ApplicationPlanModule())
        registry.register(ApplicationValidateModule())
        registry.register(GenerationModeClarificationModule())

        # 注册 application 生成模式定义
        from app.generation_modes.application import register_application
        from app.generation_modes.registry import GenerationModeRegistry

        gen_mode_registry = GenerationModeRegistry()
        register_application(gen_mode_registry)
        gen_mode_registry.validate_prompt_modules_exist(registry)

        return RuntimeServices(
            platform_client=self._platform_client,
            tool_client=None,
            chat_model_factory=self._chat_model_factory,
            model_policy=self._model_policy,
            model_resolver=self._model_resolver,
            prompt_composer=None,
            prompt_module_registry=registry,
            tool_registry=None,
            event_bus=event_bus,
            node_registry=None,
            asset_manager=self._asset_manager,
            quality_checker=self._quality_checker,
            artifact_writer=self._artifact_writer,
            generation_mode_registry=gen_mode_registry,
        )

    async def _build_context(
        self,
        request,
        run_mode: RunMode,
        *,
        is_resume: bool = False,
    ) -> ExecutionContext:
        code_gen_type = _map_code_gen_type(request.code_gen_type)
        generation_mode = getattr(request, "generation_mode", None)
        if not generation_mode:
            generation_mode = _CODE_GEN_TYPE_TO_GENERATION_MODE.get(code_gen_type.value if hasattr(code_gen_type, "value") else str(code_gen_type), "application")
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
            is_test=getattr(request, "is_test", False),
            is_resume=is_resume,
            generation_mode=generation_mode,
        )

    async def stream_generate(self, request):
        async for event in self._run_agent_loop(request, RunMode.GENERATE):
            yield event

    async def stream_modify(self, request):
        async for event in self._run_agent_loop(request, RunMode.MODIFY):
            yield event

    async def _run_agent_loop(self, request, run_mode: RunMode):
        from app.agent_loop.state import AgentLoopState
        from app.agent_loop.graph import build_agent_loop_graph
        from app.agent_loop.nodes.init import InitNode
        from app.agent_loop.nodes.plan_step import PlanStepNode
        from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcherNode
        from app.agent_loop.nodes.route_step import RouteStepNode
        from app.agent_loop.nodes.validate_step import ValidateStepNode
        from app.agent_loop.nodes.finish import FinishNode

        agent_run_id = int(request.agent_run_id)
        event_bus = EventBus(agent_run_id=agent_run_id)
        services = self._build_services(event_bus)
        start_time = time.monotonic()
        loop_state_json = getattr(request, "loop_state_json", "") or ""
        context = await self._build_context(
            request,
            run_mode,
            is_resume=bool(loop_state_json),
        )

        if loop_state_json:
            logger.info("resuming agent loop from paused state | agentRunId=%s", agent_run_id)
            state = AgentLoopState.deserialize(loop_state_json)
            state.max_iterations = settings.agent_loop_max_iterations
            state.max_mode_switches = settings.agent_loop_max_mode_switches
            state.max_plan_iterations = 15
            state.status = "running"

        else:
            state = AgentLoopState(
                max_iterations=settings.agent_loop_max_iterations,
                max_mode_switches=settings.agent_loop_max_mode_switches,
            )

        init_node = InitNode(context, services)
        route_step = RouteStepNode(context, services)
        plan_step = PlanStepNode(context, services)
        implement_step = ImplementDispatcherNode(context, services)
        validate_step = ValidateStepNode(context, services)
        finish_node = FinishNode(context, services)

        graph = build_agent_loop_graph(
            init_node, route_step, plan_step, implement_step, validate_step, finish_node
        )

        async def _execute():
            nonlocal context
            try:
                result = await graph.ainvoke(state)
                final_state = AgentLoopState.from_graph_result(result)
                status = final_state.status
                iteration = final_state.iteration
                mode_switches = final_state.mode_switches
                files_touched = final_state.files_touched

                logger.info(
                    "agent_loop completed | status=%s iterations=%d switches=%d files=%d",
                    status,
                    iteration,
                    mode_switches,
                    len(files_touched),
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)
                success = status == "completed"

                loop_state_json = ""
                if status == "waiting_for_user":
                    loop_state_json = final_state.serialize()

                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id,
                    success=success,
                    workspace_path=context.workspace_path,
                    latency_ms=latency_ms,
                    error_message="" if success else f"AgentLoop status: {status}",
                    loop_state_json=loop_state_json,
                )
            except AgentRuntimeError as e:
                logger.error("agent_loop error | agentRunId=%s error=%s", agent_run_id, e)
                await event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.RUNTIME_ERROR, {"message": str(e), "code": int(e.code)}
                    )
                )
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"失败: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(
                    "agent_loop unexpected error | agentRunId=%s error=%s",
                    agent_run_id,
                    e,
                    exc_info=True,
                )
                await event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.RUNTIME_ERROR,
                        {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR},
                    )
                )
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"异常: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                    )
                except Exception:
                    pass
            finally:
                await event_bus.close()

        workflow_task = asyncio.create_task(_execute())

        async for seq_event in self._drain_events(event_bus):
            proto_event = self._event_mapper.map_event(seq_event)
            if proto_event is not None:
                yield proto_event

        await workflow_task

    async def _drain_events(self, event_bus: EventBus):
        while True:
            seq_event = await event_bus.next_event()
            if seq_event is None:
                break
            yield seq_event
