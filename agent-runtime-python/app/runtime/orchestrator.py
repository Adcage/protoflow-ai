import asyncio
import json
import logging
import time

from app.agent_loop_vnext.agents.conductor.agent import ConductorAgent
from app.capabilities.common.asset_index import create_default_asset_manager
from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.modeling.policy import ModelPolicy
from app.modeling.resolver import ModelResolver
from app.artifacts.writer import ArtifactWriter
from app.quality.structure_checker import StructureChecker
from app.runtime.context import CodeGenType, ExecutionContext, RunMode, ChatHistoryEntry, AppContext, AttachmentInfo, _CODE_GEN_TYPE_TO_GENERATION_MODE
from app.runtime.event_bus import EventBus
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.services.chat_model_factory import ChatModelFactory
from app.grpc_client.platform_client import GrpcPlatformClient

logger = logging.getLogger("app.runtime.orchestrator")

# 全局 RAG 服务单例（跨请求共享连接池，由 shutdown 时清理）
_global_rag_service: object | None = None


def _get_rag_service() -> object | None:
    """获取全局 RAG 服务实例。"""
    return _global_rag_service


async def init_rag_service() -> None:
    """启动时初始化 RAG 服务（连接 PG、解析 Embedding 配置、索引文档）。"""
    global _global_rag_service
    try:
        from app.rag.service import RAGService
        from app.modeling.resolver import ModelResolver
        from app.grpc_client.platform_client import GrpcPlatformClient

        rag = RAGService()
        platform_client = GrpcPlatformClient()
        model_resolver = ModelResolver(platform_client)

        bundle = await platform_client.resolve_runtime_model_bundle(
            user_id=0, app_id=0, agent_run_id=0, code_gen_type=0,
        )
        model_resolver._bundle = bundle
        await rag.initialize(model_resolver)

        _global_rag_service = rag
        if rag.enabled:
            logger.info("RAG 服务启动初始化成功")
        else:
            logger.info("RAG 服务已初始化但未启用（Embedding 模型未配置）")
    except Exception as e:
        logger.warning("RAG 服务启动初始化失败（不影响核心功能）: %s", e)
        _global_rag_service = None


async def close_rag_service() -> None:
    """关闭全局 RAG 服务（应用 shutdown 时调用）。"""
    global _global_rag_service
    if _global_rag_service is not None:
        try:
            await _global_rag_service.close()  # type: ignore[union-attr]
            logger.info("RAG 服务已关闭")
        except Exception as e:
            logger.warning("RAG 服务关闭异常: %s", e)
        _global_rag_service = None


def _parse_attachments_json(attachments_json: str | None) -> tuple[AttachmentInfo, ...]:
    """从 JSON 字符串解析附件元数据列表。"""
    if not attachments_json:
        return ()
    try:
        import json
        items = json.loads(attachments_json)
        return tuple(
            AttachmentInfo(
                id=item.get("id", ""),
                file_name=item.get("fileName", ""),
                file_size=item.get("fileSize", 0),
                mime_type=item.get("mimeType", ""),
                storage_type=item.get("storageType", "local"),
                storage_path=item.get("storagePath", ""),
                url=item.get("url", ""),
            )
            for item in items
        )
    except Exception:
        return ()


def _map_code_gen_type(proto_value: int) -> CodeGenType:
    mapping = {
        1: CodeGenType.SINGLE_FILE,
        2: CodeGenType.MULTI_FILE,
        3: CodeGenType.VUE_PROJECT,
    }
    return mapping.get(proto_value, CodeGenType.SINGLE_FILE)


class RuntimeOrchestrator:
    def __init__(self) -> None:
        self._platform_client = GrpcPlatformClient()
        self._chat_model_factory = ChatModelFactory()
        self._model_policy = ModelPolicy()
        self._model_resolver = ModelResolver(self._platform_client)
        self._asset_manager = create_default_asset_manager()
        self._quality_checker = StructureChecker()
        self._artifact_writer = ArtifactWriter()
        self._event_mapper = None  # 延迟初始化，见 _get_mapper()

    def _get_mapper(self):
        """按引擎配置返回对应的 ProtoEventMapper 子类。"""
        if self._event_mapper is not None:
            return self._event_mapper
        if settings.agent_loop_engine == "vnext":
            from app.agent_loop_vnext.event_mapper import VNextEventMapper
            self._event_mapper = VNextEventMapper()
        else:
            from app.agent_loop.event_mapper import LegacyEventMapper
            self._event_mapper = LegacyEventMapper()
        return self._event_mapper

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
            rag_service=_get_rag_service(),
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
                    ChatHistoryEntry(
                        id=h["id"],
                        role=h["role"],
                        content=h["content"],
                        attachments=_parse_attachments_json(h.get("attachments_json")),
                    )
                    for h in history
                )
            except Exception as e:
                logger.warning("failed to load chat history: %s", e)

        # 解析当前请求的附件
        request_attachments: tuple[AttachmentInfo, ...] = ()
        if hasattr(request, "attachments") and request.attachments:
            request_attachments = tuple(
                AttachmentInfo(
                    id=a.id,
                    file_name=a.file_name,
                    file_size=a.file_size,
                    mime_type=a.mime_type,
                    storage_type=a.storage_type,
                    storage_path=a.storage_path,
                    url=a.url,
                )
                for a in request.attachments
            )

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
            runtime_options=self._parse_runtime_options(request),
            is_test=getattr(request, "is_test", False),
            is_resume=is_resume,
            generation_mode=generation_mode,
            attachments=request_attachments,
        )

    async def stream_generate(self, request):
        # TEST_PLAYGROUND 模式优先路由（generation_mode == 2）
        generation_mode = getattr(request, "generation_mode", None)
        logger.info("stream_generate | generation_mode=%s type=%s", generation_mode, type(generation_mode))
        if generation_mode == 2:  # protobuf enum: TEST_PLAYGROUND
            async for event in self._run_playground(request, RunMode.GENERATE):
                yield event
            return

        engine = settings.agent_loop_engine
        if engine == "vnext":
            async for event in self._run_conductor_vnext(request, RunMode.GENERATE):
                yield event
        elif engine == "legacy":
            async for event in self._run_agent_loop(request, RunMode.GENERATE):
                yield event
        else:
            raise AgentRuntimeError(
                f"不支持的 agent_loop_engine 配置: {engine}",
                code=AgentErrorCode.STATE_ERROR,
            )

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
            # 恢复场景额外 3 次模式切换额度（路由纠偏 + 阶段跳转累计）
            state.max_mode_switches = settings.agent_loop_max_mode_switches + 3
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
            for proto_event in self._get_mapper().map_event(seq_event):
                yield proto_event

        await workflow_task

    async def _drain_events(self, event_bus: EventBus):
        while True:
            seq_event = await event_bus.next_event()
            if seq_event is None:
                break
            yield seq_event

    async def _run_single_implement_vnext(self, request, run_mode: RunMode):
        """vNext 单实现链路：模型流式对话 → SSE 传输。"""
        from app.agent_loop_vnext.runner import SingleImplementLoopRunner

        agent_run_id = int(request.agent_run_id)
        event_bus = EventBus(agent_run_id=agent_run_id)
        services = self._build_services(event_bus)
        start_time = time.monotonic()

        context = await self._build_context(request, run_mode)

        # 根据上下文配置 mapper（如 is_test、脱敏策略等）
        mapper = self._get_mapper()
        if hasattr(mapper, 'set_is_test'):
            mapper.set_is_test(context.is_test)

        async def _execute():
            try:
                runner = SingleImplementLoopRunner(context, services)
                await runner.run()

                latency_ms = int((time.monotonic() - start_time) * 1000)
                # 根据 runner 状态决定完成还是暂停
                loop_state_json = ""
                success = runner.state.status == "completed"
                ai_status = "success"
                ai_extra = self._build_ai_extra_from_event_bus(event_bus)
                if runner.state.status == "waiting_for_user":
                    # 最小非空 JSON 触发 Java pauseAgentRun 逻辑
                    loop_state_json = '{"status":"waiting_for_user"}'
                    ai_status = "waiting_for_user"

                # [DEBUG] 调试日志：打印 complete_agent_run 的关键参数
                logger.info(
                    "[DEBUG] complete_agent_run | agentRunId=%s success=%s ai_status=%s "
                    "ai_message_len=%d ai_extra_len=%d loop_state_json=%s",
                    agent_run_id,
                    success,
                    ai_status,
                    len(runner._accumulated_text or ""),
                    len(ai_extra or ""),
                    loop_state_json[:80] if loop_state_json else "",
                )

                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id,
                    success=success,
                    workspace_path=context.workspace_path,
                    latency_ms=latency_ms,
                    error_message="",
                    loop_state_json=loop_state_json,
                    ai_message=runner._accumulated_text,
                    ai_status=ai_status,
                    ai_extra=ai_extra,
                )
            except AgentRuntimeError as e:
                logger.error("vNext runner error | agentRunId=%s error=%s", agent_run_id, e)
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": int(e.code)},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"失败: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(
                    "vNext unexpected error | agentRunId=%s error=%s",
                    agent_run_id, e, exc_info=True,
                )
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"异常: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            finally:
                await event_bus.close()

        workflow_task = asyncio.create_task(_execute())

        async for seq_event in self._drain_events(event_bus):
            for proto_event in self._get_mapper().map_event(seq_event):
                yield proto_event

        await workflow_task

    async def _run_conductor_vnext(self, request, run_mode: RunMode):
        """vNext 多智能体链路：Conductor 调度 planner / implementor / validator。"""
        agent_run_id = int(request.agent_run_id)
        event_bus = EventBus(agent_run_id=agent_run_id)
        services = self._build_services(event_bus)
        start_time = time.monotonic()

        context = await self._build_context(request, run_mode)

        mapper = self._get_mapper()
        if hasattr(mapper, "set_is_test"):
            mapper.set_is_test(context.is_test)

        async def _execute():
            try:
                conductor = ConductorAgent()
                result = await conductor.run(context, services)

                latency_ms = int((time.monotonic() - start_time) * 1000)
                loop_state_json = ""
                ai_status = result.status
                success = result.status == "completed"
                if result.status == "waiting_for_user":
                    loop_state_json = json.dumps({"status": "waiting_for_user"}, ensure_ascii=False)
                    ai_status = "waiting_for_user"
                elif result.status == "completed":
                    ai_status = "success"
                ai_extra = self._build_ai_extra_from_event_bus(event_bus)

                token_usage = result.total_token_usage

                # [DEBUG] 调试日志：打印 complete_agent_run 的关键参数
                logger.info(
                    "[DEBUG] complete_agent_run | agentRunId=%s success=%s ai_status=%s "
                    "ai_message_len=%d ai_extra_len=%d loop_state_json=%s",
                    agent_run_id,
                    success,
                    ai_status,
                    len(result.message or ""),
                    len(ai_extra or ""),
                    loop_state_json[:80] if loop_state_json else "",
                )

                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id,
                    success=success,
                    workspace_path=context.workspace_path,
                    latency_ms=latency_ms,
                    error_message=result.error or "",
                    loop_state_json=loop_state_json,
                    total_input_tokens=token_usage.get("input_tokens", 0),
                    total_output_tokens=token_usage.get("output_tokens", 0),
                    total_cache_read_tokens=token_usage.get("cache_read_tokens", 0),
                    total_cache_creation_tokens=token_usage.get("cache_creation_tokens", 0),
                    ai_message=result.message,
                    ai_status=ai_status,
                    ai_extra=ai_extra,
                )
            except AgentRuntimeError as e:
                logger.error("vNext conductor error | agentRunId=%s error=%s", agent_run_id, e)
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": int(e.code)},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"失败: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(
                    "vNext conductor unexpected error | agentRunId=%s error=%s",
                    agent_run_id, e, exc_info=True,
                )
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"异常: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            finally:
                await event_bus.close()

        workflow_task = asyncio.create_task(_execute())

        async for seq_event in self._drain_events(event_bus):
            for proto_event in self._get_mapper().map_event(seq_event):
                yield proto_event

        await workflow_task

    # ── Playground 模式 ──────────────────────────────────────────────

    def _parse_runtime_options(self, request) -> dict:
        """从 gRPC 请求解析 runtime_options_json 为 dict。"""
        raw = getattr(request, "runtime_options_json", "") or ""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _build_playground_services(self, event_bus: EventBus) -> RuntimeServices:
        """构建 Playground 模式专用服务（精简 Prompt 模块，跳过生产约束）。"""
        from app.prompts.registry import PromptModuleRegistry
        from app.prompts.default_modules import (
            RuntimeBoundaryModule,
            SafetyAndInjectionResistanceModule,
        )
        from app.prompts.loop_modules import (
            ToolListModule,
            SkillContextModule,
        )
        from app.prompts.test_modules import TestModeInfoModule
        from app.prompts.playground_modules import PlaygroundModeModule

        registry = PromptModuleRegistry()
        # Playground 模式启用的 Prompt 模块（精简版）
        registry.register(RuntimeBoundaryModule())                # 运行时边界（必须）
        registry.register(SafetyAndInjectionResistanceModule())   # 基本注入防护（必须）
        registry.register(ToolListModule())                       # 工具列表（动态注入）
        registry.register(SkillContextModule())                    # Skill 上下文
        registry.register(TestModeInfoModule())                    # 测试模式（允许讨论内部机制）
        registry.register(PlaygroundModeModule())                  # Playground 模式说明

        # 注册 application 生成模式（保持兼容）
        from app.generation_modes.application import register_application
        from app.generation_modes.registry import GenerationModeRegistry
        gen_mode_registry = GenerationModeRegistry()
        register_application(gen_mode_registry)

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
            rag_service=_get_rag_service(),
        )

    async def _run_playground(self, request, run_mode: RunMode):
        """Playground 模式：通过 LoopStrategy 构建链路组件 + SingleImplementLoopRunner 执行。"""
        import dataclasses
        from app.agent_loop_vnext.loops import get_loop_strategy
        from app.agent_loop_vnext.runner import SingleImplementLoopRunner

        agent_run_id = int(request.agent_run_id)
        event_bus = EventBus(agent_run_id=agent_run_id)

        # 通过策略模式获取链路构建器
        strategy = get_loop_strategy(
            request.generation_mode if hasattr(request, "generation_mode") else None,
            runtime_orchestrator=self,
            is_test=True,
        )
        services = strategy.build_services(event_bus)
        start_time = time.monotonic()

        context = await self._build_context(request, run_mode)
        # 覆盖 runtime_options（从 request 解析 enabled_tools）
        context = dataclasses.replace(
            context,
            runtime_options=self._parse_runtime_options(request),
            is_test=True,  # Playground 始终测试模式
        )

        mapper = self._get_mapper()
        if hasattr(mapper, "set_is_test"):
            mapper.set_is_test(True)  # 不脱敏

        async def _execute():
            try:
                runner = SingleImplementLoopRunner(context, services)
                await runner.run()

                latency_ms = int((time.monotonic() - start_time) * 1000)
                loop_state_json = ""
                success = runner.state.status == "completed"
                ai_status = "success"
                ai_extra = self._build_ai_extra_from_event_bus(event_bus)
                if runner.state.status == "waiting_for_user":
                    loop_state_json = '{"status":"waiting_for_user"}'
                    ai_status = "waiting_for_user"

                logger.info(
                    "[Playground] complete_agent_run | agentRunId=%s success=%s ai_status=%s",
                    agent_run_id, success, ai_status,
                )

                await self._platform_client.complete_agent_run(
                    agent_run_id=agent_run_id,
                    success=success,
                    workspace_path=context.workspace_path,
                    latency_ms=latency_ms,
                    error_message="",
                    loop_state_json=loop_state_json,
                    ai_message=runner._accumulated_text,
                    ai_status=ai_status,
                    ai_extra=ai_extra,
                )
            except AgentRuntimeError as e:
                logger.error("playground runner error | agentRunId=%s error=%s", agent_run_id, e)
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": int(e.code)},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"失败: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(
                    "playground unexpected error | agentRunId=%s error=%s",
                    agent_run_id, e, exc_info=True,
                )
                await event_bus.emit(RuntimeEvent(
                    RuntimeEventType.RUNTIME_ERROR,
                    {"message": str(e), "code": AgentErrorCode.INTERNAL_ERROR},
                ))
                await event_bus.emit(RuntimeEvent(RuntimeEventType.DONE, {"message": f"异常: {e}"}))
                try:
                    await self._platform_client.complete_agent_run(
                        agent_run_id=agent_run_id,
                        success=False,
                        error_message=str(e),
                        latency_ms=int((time.monotonic() - start_time) * 1000),
                        ai_status="failed",
                    )
                except Exception:
                    pass
            finally:
                await event_bus.close()

        workflow_task = asyncio.create_task(_execute())

        async for seq_event in self._drain_events(event_bus):
            for proto_event in self._get_mapper().map_event(seq_event):
                yield proto_event

        await workflow_task

    # ── 工具名归一化 ──────────────────────────────────────────────
    # 但 SSE 实时流和前端还原逻辑使用 snake_case（如 ask_user），
    # 存入 extra 时必须与前端保持一致，否则还原时匹配不上。
    _TOOL_NAME_NORMALIZE = {
        "AskUser": "ask_user",
    }

    def _build_ai_extra_from_event_bus(self, event_bus: EventBus) -> str:
        tool_calls: list[dict[str, object]] = []

        # 预收集 CLARIFICATION_REQUIRED 事件，用于替换 AskUser 的原始 TOOL_CALL
        # 原始 TOOL_CALL 的 arguments 缺少 questionSetId / protocolVersion，
        # 而 CLARIFICATION_REQUIRED 包含完整的提问结构，与 SSE 实时流一致。
        clarification_by_qsid: dict[str, dict] = {}
        for sequenced in event_bus.snapshot():
            event = sequenced.event
            if event.event_type.value == "clarification_required":
                qsid = (event.data or {}).get("questionSetId", "")
                if qsid:
                    clarification_by_qsid[qsid] = event.data or {}

        for sequenced in event_bus.snapshot():
            event = sequenced.event
            if event.event_type.value == "tool_call":
                raw_name = str(event.data.get("name", ""))
                normalized_name = self._TOOL_NAME_NORMALIZE.get(raw_name, raw_name)

                # AskUser：用 CLARIFICATION_REQUIRED 的完整数据替代原始参数
                if raw_name == "AskUser":
                    # 原始 arguments 是 LLM 传入的 {questions: [...]}，
                    # 缺少 questionSetId / protocolVersion。
                    # 从 state.pending_question 或 clarification 事件中补充。
                    raw_args = event.data.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            import json as _json
                            raw_args = _json.loads(raw_args)
                        except (json.JSONDecodeError, TypeError, ValueError):
                            raw_args = {}

                    # 找到匹配的 CLARIFICATION_REQUIRED 事件
                    merged_args = dict(raw_args) if isinstance(raw_args, dict) else {}
                    for _qsid, clar_data in clarification_by_qsid.items():
                        # 如果 arguments 中有 questions，匹配第一个有相同 questions 的
                        if "questions" in clar_data:
                            merged_args = {
                                "protocolVersion": clar_data.get("protocolVersion", 1),
                                "questionSetId": clar_data.get("questionSetId", _qsid),
                                "stage": clar_data.get("stage", ""),
                                "questions": clar_data.get("questions", []),
                            }
                            break

                    tool_calls.append(
                        {
                            "type": "request",
                            "id": str(event.data.get("id", "")),
                            "name": normalized_name,
                            "arguments": self._serialize_tool_payload(merged_args),
                            "agentName": str(event.data.get("agent_name", "")),
                        }
                    )
                else:
                    tool_calls.append(
                        {
                            "type": "request",
                            "id": str(event.data.get("id", "")),
                            "name": normalized_name,
                            "arguments": self._serialize_tool_payload(event.data.get("arguments")),
                            "agentName": str(event.data.get("agent_name", "")),
                        }
                    )
            elif event.event_type.value == "tool_result":
                raw_name = str(event.data.get("name", ""))
                tool_calls.append(
                    {
                        "type": "executed",
                        "id": str(event.data.get("id", "")),
                        "name": self._TOOL_NAME_NORMALIZE.get(raw_name, raw_name),
                        "arguments": self._serialize_tool_payload(event.data.get("arguments")),
                        "result": str(event.data.get("result", "")),
                        "agentName": str(event.data.get("agent_name", "")),
                    }
                )

        if not tool_calls:
            return ""

        return json.dumps({"toolCalls": tool_calls}, ensure_ascii=False)

    @staticmethod
    def _serialize_tool_payload(payload) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            return payload
        try:
            return json.dumps(payload, ensure_ascii=False)
        except TypeError:
            return str(payload)
