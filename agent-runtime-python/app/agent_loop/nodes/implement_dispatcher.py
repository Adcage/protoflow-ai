import logging
from typing import Any

from app.agent_loop.agents.base import ImplementAgent
from app.agent_loop.execution_contract import ExecutionContract
from app.agent_loop.nodes.step_base import _create_terminal_tools_for_mode, _get_skill_dir, _get_assets_dir, _make_loop_tools
from app.agent_loop.state import AgentLoopState
from app.agent_loop.transition import apply_workflow_transition
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.runtime.context import ExecutionContext
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.langchain_tools import create_all_tools, ReadAssetTool

logger = logging.getLogger("app.agent_loop.nodes.implement_dispatcher")


class ImplementDispatcher:
    """Implement 阶段调度器。

    按合同中的 generationMode 查找 Agent，并把公共服务、合同和同次 ResolvedToolSet 交给 Agent。
    不创建工具，不持有运行状态，不使用 if mode == ... 链。
    """

    def __init__(self, generation_mode_registry: Any) -> None:
        self._registry = generation_mode_registry

    async def dispatch(
        self,
        state: AgentLoopState,
        context: ExecutionContext,
        services: RuntimeServices,
        toolset: Any,
    ) -> AgentLoopState:
        contract = self._validate_contract(state)
        generation_mode = contract.generation_mode

        if not self._registry.is_registered(generation_mode):
            raise AgentRuntimeError(
                f"生成模式 {generation_mode} 未注册，无法执行 Implement",
                code=AgentErrorCode.STATE_ERROR,
            )

        definition = self._registry.require(generation_mode)

        if contract.expected_artifact_format not in definition.supported_artifact_formats:
            raise AgentRuntimeError(
                f"产物格式 {contract.expected_artifact_format} 不受模式 {generation_mode} 支持",
                code=AgentErrorCode.STATE_ERROR,
            )

        agent: ImplementAgent = definition.implement_agent_factory()

        return await agent.execute(state, context, services, contract, toolset)

    def _validate_contract(self, state: AgentLoopState) -> ExecutionContract:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is None:
            raise AgentRuntimeError(
                "状态 envelope 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        execution = envelope.workflow.execution
        contract_dict = getattr(execution, "execution_contract", None)
        if contract_dict is None:
            raise AgentRuntimeError(
                "缺少 ExecutionContract，不能进入 Implement",
                code=AgentErrorCode.STATE_ERROR,
            )

        contract = ExecutionContract.model_validate(contract_dict)

        workflow_generation_mode = getattr(envelope.workflow, "generation_mode", None)
        if workflow_generation_mode is not None and contract.generation_mode != workflow_generation_mode:
            raise AgentRuntimeError(
                f"合同 generation_mode={contract.generation_mode} 与工作流 generation_mode={workflow_generation_mode} 不一致",
                code=AgentErrorCode.STATE_ERROR,
            )

        return contract


class ImplementDispatcherNode:
    """替换 ImplementStepNode 的调度节点。

    统一构造候选工具、Resolver 统一解析，
    然后委托给 ImplementDispatcher 按 generationMode 分派。
    """

    def __init__(self, context: ExecutionContext, services: RuntimeServices) -> None:
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        state.plan_just_finished = False
        state.implement_just_finished = False

        workspace = Workspace(self._context.workspace_path)
        skill_dir = _get_skill_dir(state)
        assets_dir = _get_assets_dir(state)
        file_tools = FileTools(workspace, skill_dir=skill_dir, assets_dir=assets_dir)

        terminal_tools = _create_terminal_tools_for_mode(workspace, readonly=False)

        lc_tools = create_all_tools(file_tools, terminal_tools=terminal_tools)
        lc_tools.append(ReadAssetTool(file_tools=file_tools))
        lc_tools.extend(_make_loop_tools(state, self._services.event_bus))

        toolset = ModeToolResolver.resolve(AgentMode.IMPLEMENT, lc_tools)

        dispatcher = ImplementDispatcher(
            generation_mode_registry=self._services.generation_mode_registry
        )

        result = await dispatcher.dispatch(state, self._context, self._services, toolset)
        ImplementDispatcherNode.apply_exit_transition(result)
        return result

    @staticmethod
    def apply_exit_transition(state: AgentLoopState) -> None:
        if not getattr(state, "implement_just_finished", False):
            return
        if getattr(state, "implement_replan_requested", False):
            apply_workflow_transition(
                state,
                source="implement",
                target="route",
                reason_code="implement_replan_requested",
            )
        else:
            apply_workflow_transition(
                state,
                source="implement",
                target="validate",
                reason_code="implement_completed",
            )
        if hasattr(state, "record_phase_report"):
            state.record_phase_report()
