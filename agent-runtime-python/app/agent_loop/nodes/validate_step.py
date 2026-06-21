import logging

from langchain_core.tools import BaseTool

from app.agent_loop.nodes.step_base import _execute_single_step
from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tool_resolver import ModeToolResolver
from app.agent_loop.tools.decide_validation import DecideValidationTool
from app.agent_loop.tools.run_checks import RunChecksTool
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.langchain_tools import create_file_tools

logger = logging.getLogger("app.agent_loop.nodes.validate_step")


class ValidateStepNode:
    """校验模式节点，和 plan/implement 同级别的大循环模式。
    AI 自主调用工具校验代码质量，然后调用 decide_validation 输出结论。"""

    def __init__(self, context: ExecutionContext, services: RuntimeServices):
        self._context = context
        self._services = services

    async def __call__(self, state: AgentLoopState) -> AgentLoopState:
        if state.validate_iterations >= state.max_validate_iterations:
            if state.validation_status == "pending":
                state.validation_status = "failed"
                state.validation_failures.append({
                    "issue": f"校验超过最大迭代次数 {state.max_validate_iterations}，未提交校验结论",
                    "suggestion": "请检查代码结构并在下一轮 Implement 中修复",
                })
            state.validate_just_finished = True
            logger.warning(
                "validate_step | exceeded max_validate_iterations, status=%s",
                state.validation_status,
            )
            return state

        await self._services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.STATUS,
                {"message": f"Validate step {state.validate_iterations + 1}"},
            )
        )

        workspace = Workspace(self._context.workspace_path)
        file_tools = FileTools(workspace)
        file_lc_tools = create_file_tools(file_tools)

        run_checks = RunChecksTool()
        run_checks.set_state(state)
        run_checks.set_workspace(self._context.workspace_path)
        run_checks.set_quality_checker(self._services.quality_checker)
        run_checks.set_code_gen_type(self._context.code_gen_type)

        decide_validation = DecideValidationTool()
        decide_validation.set_state(state)

        all_tools: list[BaseTool] = list(file_lc_tools) + [run_checks, decide_validation]
        toolset = ModeToolResolver.resolve(AgentMode.VALIDATE, all_tools)

        system_prompt = self._compose_prompt(state, toolset)

        state.validate_iterations += 1
        logger.info(
            "validate_step | validate_iterations=%d mode=%s",
            state.validate_iterations,
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

    def _compose_prompt(self, state: AgentLoopState, toolset) -> str:
        registry = getattr(self._services, "prompt_module_registry", None)
        if registry is None:
            raise AgentRuntimeError(
                "PromptModuleRegistry 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        profile_module_ids = PROMPT_PROFILES.get("validate")
        if profile_module_ids is None:
            raise AgentRuntimeError(
                "Profile validate 不存在",
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
