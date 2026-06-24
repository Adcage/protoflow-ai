from typing import Any, Callable

from pydantic import BaseModel, field_validator


class GenerationModeDefinition(BaseModel):
    """生成模式定义，注册时原子校验完整性。

    新增生成能力时只需注册一个完整定义，不得修改核心图结构。
    """

    mode_id: str
    plan_prompt_module_ids: tuple[str, ...]
    implement_agent_factory: Callable
    validate_prompt_module_ids: tuple[str, ...]
    supported_artifact_formats: frozenset[str]

    model_config: dict[str, Any] = {"arbitrary_types_allowed": True}

    @field_validator("mode_id")
    @classmethod
    def mode_id_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "GenerationModeDefinition.mode_id 不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v.strip()

    @field_validator("plan_prompt_module_ids")
    @classmethod
    def plan_modules_must_be_non_empty(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "GenerationModeDefinition.plan_prompt_module_ids 不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("implement_agent_factory")
    @classmethod
    def factory_must_be_callable(cls, v: Callable) -> Callable:
        return v

    @field_validator("validate_prompt_module_ids")
    @classmethod
    def validate_modules_must_be_non_empty(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "GenerationModeDefinition.validate_prompt_module_ids 不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v

    @field_validator("supported_artifact_formats")
    @classmethod
    def formats_must_be_non_empty(cls, v: frozenset[str]) -> frozenset[str]:
        if not v:
            from app.core.error_codes import AgentErrorCode
            from app.core.exceptions import AgentRuntimeError

            raise AgentRuntimeError(
                "GenerationModeDefinition.supported_artifact_formats 不能为空",
                code=AgentErrorCode.STATE_ERROR,
            )
        return v
