import logging
from typing import Any

from app.agent_loop.agents.base import ImplementAgent
from app.agent_loop.nodes.step_base import _execute_single_step
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.prompts.composer import PromptComposer
from app.prompts.profiles import resolve_profile_module_ids
from app.runtime.events import RuntimeEvent, RuntimeEventType

logger = logging.getLogger("app.agent_loop.agents.application")


class ApplicationImplementAgent(ImplementAgent):
    """application 生成模式的 Implement Agent。

    加载公共 Implement Prompt + application Implement 模块，
    只执行合同 tasks，不得自行补全或修改合同。
    """

    async def execute(
        self,
        state: Any,
        context: Any,
        services: Any,
        contract: Any,
        toolset: Any,
    ) -> Any:
        await services.event_bus.emit(
            RuntimeEvent(RuntimeEventType.STATUS, {"message": f"Implement step {state.iteration + 1}"})
        )

        generation_mode = getattr(state, "generation_mode", None)
        if generation_mode is None:
            envelope = getattr(state, "_state_envelope", None)
            if envelope is not None:
                generation_mode = getattr(envelope.workflow, "generation_mode", None)

        mode_registry = getattr(services, "generation_mode_registry", None)

        system_prompt = self._compose_prompt(
            state, context, services, toolset, generation_mode, mode_registry
        )

        workspace = getattr(context, "workspace_path", "")
        from app.tools.file_tools import Workspace, FileTools

        ws = Workspace(workspace)
        file_tools = FileTools(ws)

        logger.info("application_implement | iteration=%d mode=%s", state.iteration + 1, state.mode)

        return await _execute_single_step(
            state,
            context,
            services,
            system_prompt,
            toolset,
            file_tools,
        )

    def _compose_prompt(
        self,
        state: Any,
        context: Any,
        services: Any,
        toolset: Any,
        generation_mode: str | None,
        mode_registry: Any,
    ) -> str:
        registry = getattr(services, "prompt_module_registry", None)
        if registry is None:
            raise AgentRuntimeError(
                "PromptModuleRegistry 不可用",
                code=AgentErrorCode.STATE_ERROR,
            )

        profile_module_ids = resolve_profile_module_ids(
            "implement",
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
