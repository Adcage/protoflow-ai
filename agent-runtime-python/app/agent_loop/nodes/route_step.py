import logging

from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import _execute_single_step
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.agent_loop.tools.decide_route import (
    DecideRouteTool,
    apply_route_decision,
    _resolve_route_source,
)
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.langchain_tools import create_file_tools

logger = logging.getLogger("app.agent_loop.nodes.route_step")


class RouteStepNode:
    """统一路由决策节点。

    每次图显式进入 Route 时都产生当前来源的新决策，禁止跳过并复用 stale route_decision。
    """

    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        await self._services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.STATUS, {"message": "Route step"})
        )

        # 每次进入都清除待提交结果
        state.route_decided = False
        state.route_decision = None

        # 构建只读工具集
        workspace = Workspace(self._context.workspace_path)
        file_tools = FileTools(workspace)
        file_lc_tools = create_file_tools(file_tools)

        decide_route = DecideRouteTool()
        decide_route.set_state(state)

        all_tools: list[BaseTool] = list(file_lc_tools) + [decide_route]
        toolset = ModeToolResolver.resolve(AgentMode.ROUTE, all_tools)

        system_prompt = self._compose_prompt(state, toolset)

        state.route_iterations += 1
        logger.info(
            "route_step | route_iterations=%d mode=%s route_decided=%s",
            state.route_iterations,
            state.mode,
            state.route_decided,
        )

        result = await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )

        if not result.route_decided:
            self._apply_default_route(result)

        return result

    def _compose_prompt(self, state: AgentLoopState, toolset) -> str:
        registry = getattr(self._services, "prompt_module_registry", None)
        if registry is None:
            raise AgentRuntimeError(
                "PromptModuleRegistry 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        profile_id = self._resolve_profile_id(state)
        profile_module_ids = PROMPT_PROFILES.get(profile_id)
        if profile_module_ids is None:
            raise AgentRuntimeError(
                f"Profile {profile_id} 不存在",
                code=AgentErrorCode.STATE_ERROR,
            )

        modules = registry.require_many(profile_module_ids)
        composer = PromptComposer(modules)
        messages = composer.compose(self._context, state, toolset)
        if messages and messages[0].get("role") == "system":
            return messages[0]["content"]

        raise AgentRuntimeError(
            "PromptComposer 未能生成系统提示词",
            code=AgentErrorCode.STATE_ERROR,
        )

    def _resolve_profile_id(self, state: AgentLoopState) -> str:
        if getattr(state, "plan_just_finished", False):
            return "route_after_plan"
        if getattr(state, "implement_just_finished", False):
            return "route_after_implement"
        if getattr(state, "validate_just_finished", False):
            return "route_after_validate"
        return "route_initial"

    def _apply_default_route(self, state: AgentLoopState) -> None:
        """安全回退路由，必须走 apply_route_decision。"""
        source = _resolve_route_source(state)
        if source == "initial":
            target: str = "plan"
        elif source == "plan":
            target = "plan"
        elif source == "implement":
            target = (
                "plan"
                if getattr(state, "implement_replan_requested", False)
                else "validate"
            )
        elif source == "validate":
            if getattr(state, "validation_status", "pending") == "passed":
                target = "finish"
            else:
                target = "implement"
        else:
            target = "plan"

        apply_route_decision(
            state,
            source=source,
            mode=target,
            code_gen_type="",
            reason="默认路由",
        )
        logger.warning(
            "route_step | applied default route: source=%s target=%s",
            source,
            target,
        )
