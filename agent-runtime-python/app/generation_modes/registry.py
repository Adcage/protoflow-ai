import logging
from typing import Any

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.generation_modes.types import GenerationModeDefinition

logger = logging.getLogger("app.generation_modes.registry")


class GenerationModeRegistry:
    """生成模式原子注册表。

    注册时校验定义完整性；缺少任一必需部分时拒绝注册并返回 STATE_ERROR，
    不得以空 Prompt、默认 Agent 或 application 回退掩盖错误。
    """

    def __init__(self) -> None:
        self._definitions: dict[str, GenerationModeDefinition] = {}

    def register(self, definition: GenerationModeDefinition) -> None:
        """注册一个生成模式定义。拒绝重复 mode_id。"""
        if definition.mode_id in self._definitions:
            raise AgentRuntimeError(
                f"生成模式 {definition.mode_id} 已注册，不允许重复注册",
                code=AgentErrorCode.STATE_ERROR,
            )
        self._definitions[definition.mode_id] = definition
        logger.info("register | mode=%s formats=%s", definition.mode_id, definition.supported_artifact_formats)

    def get(self, mode_id: str) -> GenerationModeDefinition | None:
        return self._definitions.get(mode_id)

    def require(self, mode_id: str) -> GenerationModeDefinition:
        definition = self._definitions.get(mode_id)
        if definition is None:
            raise AgentRuntimeError(
                f"生成模式 {mode_id} 未注册",
                code=AgentErrorCode.STATE_ERROR,
            )
        return definition

    def registered_mode_ids(self) -> list[str]:
        return sorted(self._definitions.keys())

    def is_registered(self, mode_id: str) -> bool:
        return mode_id in self._definitions

    def validate_prompt_modules_exist(self, prompt_registry: Any) -> None:
        """启动时校验所有已注册模式的 Prompt 模块 ID 在 PromptModuleRegistry 中存在。"""
        for mode_id, definition in self._definitions.items():
            for mid in definition.plan_prompt_module_ids:
                if prompt_registry.get_by_id(mid) is None:
                    raise AgentRuntimeError(
                        f"生成模式 {mode_id} 引用了不存在的 Plan Prompt 模块: {mid}",
                        code=AgentErrorCode.STATE_ERROR,
                    )
            for mid in definition.validate_prompt_module_ids:
                if prompt_registry.get_by_id(mid) is None:
                    raise AgentRuntimeError(
                        f"生成模式 {mode_id} 引用了不存在的 Validate Prompt 模块: {mid}",
                        code=AgentErrorCode.STATE_ERROR,
                    )
