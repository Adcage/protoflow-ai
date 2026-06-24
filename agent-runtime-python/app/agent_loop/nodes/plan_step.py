import logging
import uuid

from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import (
    _create_terminal_tools_for_mode,
    _execute_single_step,
    _get_assets_dir,
    _get_skill_dir,
    _make_loop_tools,
)
from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import PlanStateV2
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.capabilities.skills.selector import SkillRegistryProvider
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES, resolve_profile_module_ids
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

    generation_mode = getattr(state, "generation_mode", None)
    if generation_mode is None:
        envelope = getattr(state, "_state_envelope", None)
        if envelope is not None:
            generation_mode = getattr(envelope.workflow, "generation_mode", None)

    mode_registry = getattr(services, "generation_mode_registry", None)
    profile_module_ids = resolve_profile_module_ids(
        profile_id,
        generation_mode=generation_mode,
        mode_registry=mode_registry,
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


def _ensure_plan_envelope(state: AgentLoopState) -> PlanStateV2:
    envelope = getattr(state, "_state_envelope", None)
    if envelope is None:
        envelope = state._to_envelope()
        state._state_envelope = envelope
    plan_state: PlanStateV2 = envelope.workflow.plan
    if not plan_state.plan_session_id:
        plan_state.plan_session_id = f"plan_{uuid.uuid4().hex[:12]}"
    return plan_state


class PlanStepNode:
    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        plan_state = _ensure_plan_envelope(state)
        plan_state.increment_model_call()

        if plan_state.reached_hard_limit():
            state.status = "failed"
            await self._services.event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.STATUS,
                    {"message": "Plan 调用硬上限已到；进入 blocked 状态"},
                )
            )
            plan_state.plan_stage = "blocked"
            return state

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

        loop_tools = _make_loop_tools(state, self._services.event_bus)
        # 为 ChooseSkillTool 注入 SkillRegistryProvider（Plan 阶段专用）
        provider = build_skill_registry_provider(state)
        if provider is not None:
            for tool in loop_tools:
                if tool.name == "choose_skill":
                    setattr(tool, "_skill_registry_provider", provider)
                    break
        lc_tools.extend(loop_tools)

        toolset = ModeToolResolver.resolve(AgentMode.PLAN, lc_tools)

        system_prompt = _compose_system_prompt(
            state, self._context, self._services, toolset,
            profile_id="plan",
        )

        logger.info(
            "plan_step | iteration=%d model_call_count=%d mode=%s stage=%s session=%s",
            state.iteration + 1,
            plan_state.model_call_count,
            state.mode,
            plan_state.plan_stage,
            plan_state.plan_session_id,
        )

        result = await _execute_single_step(
            state,
            self._context,
            self._services,
            system_prompt,
            toolset,
            file_tools,
        )

        PlanStepNode.apply_exit_transition(result)
        return result

    @staticmethod
    def apply_exit_transition(state: AgentLoopState) -> None:
        if not getattr(state, "plan_just_finished", False):
            return
        from app.agent_loop.graph import _ensure_execution_contract_after_plan
        from app.agent_loop.transition import apply_workflow_transition

        _ensure_execution_contract_after_plan(state)
        apply_workflow_transition(
            state,
            source="plan",
            target="implement",
            reason_code="plan_completed",
        )
        if hasattr(state, "record_phase_report"):
            state.record_phase_report()


def build_skill_registry_provider(state: AgentLoopState) -> SkillRegistryProvider | None:
    index = getattr(state, "_asset_index", None)
    if index is None:
        return None
    return SkillRegistryProvider(index.skill_registry)
