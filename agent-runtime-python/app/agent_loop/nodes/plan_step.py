import logging

from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import (
    _create_terminal_tools_for_mode,
    _execute_single_step,
    _get_assets_dir,
    _get_skill_dir,
    _make_loop_tools,
)
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.langchain_tools import create_file_tools

logger = logging.getLogger("app.agent_loop.nodes.plan_step")


def _compose_system_prompt(
    state: AgentLoopState,
    context: ExecutionContext,
    services: RuntimeServices,
    toolset,
    profile_id: str,
) -> str:
    """使用 PromptComposer + profile 构建系统提示词。接收已解析的 toolset 避免重复解析。"""
    registry = getattr(services, "prompt_module_registry", None)
    if registry is None:
        raise AgentRuntimeError(
            "PromptModuleRegistry 不可用",
            code=AgentErrorCode.STATE_ERROR,
        )

    profile_module_ids = PROMPT_PROFILES.get(profile_id)
    if profile_module_ids is None:
        raise AgentRuntimeError(
            f"Profile {profile_id} 不存在",
            code=AgentErrorCode.STATE_ERROR,
        )

    modules = registry.require_many(profile_module_ids)
    composer = PromptComposer(modules)
    messages = composer.compose(context, state, toolset)
    if messages and messages[0].get("role") == "system":
        return messages[0]["content"]

    raise AgentRuntimeError(
        "PromptComposer 未能生成系统提示词",
        code=AgentErrorCode.STATE_ERROR,
    )


class PlanStepNode:
    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        await self._services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.STATUS, {"message": f"Plan step {state.iteration + 1}"})
        )

        workspace = Workspace(self._context.workspace_path)
        skill_dir = _get_skill_dir(state)
        assets_dir = _get_assets_dir(state)
        file_tools = FileTools(workspace, skill_dir=skill_dir, assets_dir=assets_dir)

        script_dirs: list[str] = []
        if skill_dir:
            script_dirs.append(skill_dir)
        if assets_dir:
            script_dirs.append(assets_dir)
        terminal_tools = _create_terminal_tools_for_mode(
            workspace, readonly=True, allowed_script_dirs=script_dirs
        )

        file_lc_tools = create_file_tools(file_tools)
        lc_tools: list[BaseTool] = list(file_lc_tools)
        if terminal_tools is not None:
            from app.tools.langchain_tools import RunCommandTool

            cmd_tool = RunCommandTool(terminal_tools=terminal_tools, readonly=True)
            cmd_tool.description = "在项目工作区执行预授权终端命令。plan 模式下仅限只读命令（ls、cat、git status、python 脚本等）。"
            lc_tools.append(cmd_tool)

        from app.tools.langchain_tools import ReadAssetTool

        lc_tools.append(ReadAssetTool(file_tools=file_tools))

        lc_tools.extend(_make_loop_tools(state, self._services.event_bus))

        toolset = ModeToolResolver.resolve(AgentMode.PLAN, lc_tools)

        system_prompt = _compose_system_prompt(
            state, self._context, self._services, toolset,
            profile_id="plan",
        )

        state.plan_iterations += 1
        logger.info(
            "plan_step | iteration=%d plan_iterations=%d mode=%s",
            state.iteration + 1,
            state.plan_iterations,
            state.mode,
        )

        return await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )


class ImplementStepNode:
    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        await self._services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.STATUS, {"message": f"Implement step {state.iteration + 1}"}
            )
        )

        workspace = Workspace(self._context.workspace_path)
        skill_dir = _get_skill_dir(state)
        assets_dir = _get_assets_dir(state)
        file_tools = FileTools(workspace, skill_dir=skill_dir, assets_dir=assets_dir)

        terminal_tools = _create_terminal_tools_for_mode(workspace, readonly=False)

        from app.tools.langchain_tools import create_all_tools

        lc_tools: list[BaseTool] = create_all_tools(file_tools, terminal_tools=terminal_tools)
        from app.tools.langchain_tools import ReadAssetTool

        lc_tools.append(ReadAssetTool(file_tools=file_tools))
        lc_tools.extend(_make_loop_tools(state, self._services.event_bus))

        toolset = ModeToolResolver.resolve(AgentMode.IMPLEMENT, lc_tools)

        system_prompt = _compose_system_prompt(
            state, self._context, self._services, toolset,
            profile_id="implement",
        )

        logger.info("implement_step | iteration=%d mode=%s", state.iteration + 1, state.mode)

        result = await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )

        return result
