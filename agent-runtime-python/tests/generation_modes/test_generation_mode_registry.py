"""Phase 1 Task 1-1: GenerationModeDefinition 和 GenerationModeRegistry 测试。"""

import pytest

from app.core.exceptions import AgentRuntimeError
from app.generation_modes.types import GenerationModeDefinition
from app.generation_modes.registry import GenerationModeRegistry
from app.generation_modes.application import register_application


def _valid_kwargs(**overrides):
    kwargs = dict(
        mode_id="test_mode",
        plan_prompt_module_ids=("plan_mod_a",),
        implement_agent_factory=lambda: None,
        validate_prompt_module_ids=("validate_mod_a",),
        supported_artifact_formats=frozenset({"web_single_file"}),
    )
    kwargs.update(overrides)
    return kwargs


class TestGenerationModeDefinition:
    def test_complete_definition_succeeds(self):
        defn = GenerationModeDefinition(**_valid_kwargs())
        assert defn.mode_id == "test_mode"
        assert defn.plan_prompt_module_ids == ("plan_mod_a",)
        assert defn.validate_prompt_module_ids == ("validate_mod_a",)
        assert defn.supported_artifact_formats == frozenset({"web_single_file"})
        assert callable(defn.implement_agent_factory)

    def test_empty_mode_id_rejected(self):
        with pytest.raises(AgentRuntimeError, match="mode_id"):
            GenerationModeDefinition(**_valid_kwargs(mode_id=""))

    def test_blank_mode_id_rejected(self):
        with pytest.raises(AgentRuntimeError, match="mode_id"):
            GenerationModeDefinition(**_valid_kwargs(mode_id="   "))

    def test_empty_plan_modules_rejected(self):
        with pytest.raises(AgentRuntimeError, match="plan_prompt_module_ids"):
            GenerationModeDefinition(**_valid_kwargs(plan_prompt_module_ids=()))

    def test_none_factory_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GenerationModeDefinition(**_valid_kwargs(implement_agent_factory=None))

    def test_non_callable_factory_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GenerationModeDefinition(**_valid_kwargs(implement_agent_factory="not_callable"))

    def test_empty_validate_modules_rejected(self):
        with pytest.raises(AgentRuntimeError, match="validate_prompt_module_ids"):
            GenerationModeDefinition(**_valid_kwargs(validate_prompt_module_ids=()))

    def test_empty_formats_rejected(self):
        with pytest.raises(AgentRuntimeError, match="supported_artifact_formats"):
            GenerationModeDefinition(**_valid_kwargs(supported_artifact_formats=frozenset()))

    def test_mode_id_stripped(self):
        defn = GenerationModeDefinition(**_valid_kwargs(mode_id="  test_mode  "))
        assert defn.mode_id == "test_mode"


class TestGenerationModeRegistry:
    def test_register_and_get(self):
        registry = GenerationModeRegistry()
        defn = GenerationModeDefinition(**_valid_kwargs())
        registry.register(defn)
        assert registry.get("test_mode") is defn
        assert registry.is_registered("test_mode")

    def test_duplicate_mode_rejected(self):
        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(**_valid_kwargs()))
        with pytest.raises(AgentRuntimeError, match="已注册"):
            registry.register(GenerationModeDefinition(**_valid_kwargs()))

    def test_require_existing(self):
        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(**_valid_kwargs()))
        result = registry.require("test_mode")
        assert result.mode_id == "test_mode"

    def test_require_missing_raises(self):
        registry = GenerationModeRegistry()
        with pytest.raises(AgentRuntimeError, match="未注册"):
            registry.require("nonexistent")

    def test_registered_mode_ids(self):
        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(**_valid_kwargs(mode_id="alpha")))
        registry.register(GenerationModeDefinition(**_valid_kwargs(mode_id="beta", plan_prompt_module_ids=("p2",), validate_prompt_module_ids=("v2",))))
        assert registry.registered_mode_ids() == ["alpha", "beta"]

    def test_validate_prompt_modules_exist_success(self):
        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(**_valid_kwargs(
            plan_prompt_module_ids=("existing_mod",),
            validate_prompt_module_ids=("another_mod",),
        )))
        mock_prompt_registry = type("MockRegistry", (), {"get_by_id": lambda self, mid: True})()
        registry.validate_prompt_modules_exist(mock_prompt_registry)

    def test_validate_prompt_modules_exist_failure(self):
        registry = GenerationModeRegistry()
        registry.register(GenerationModeDefinition(**_valid_kwargs(
            plan_prompt_module_ids=("missing_mod",),
            validate_prompt_module_ids=("another_mod",),
        )))
        mock_prompt_registry = type("MockRegistry", (), {"get_by_id": lambda self, mid: None if mid == "missing_mod" else True})()
        with pytest.raises(AgentRuntimeError, match="不存在的 Plan Prompt 模块"):
            registry.validate_prompt_modules_exist(mock_prompt_registry)


class TestApplicationRegistration:
    def test_application_definition_is_complete(self):
        registry = GenerationModeRegistry()
        register_application(registry)
        defn = registry.require("application")
        assert defn.mode_id == "application"
        assert len(defn.plan_prompt_module_ids) > 0
        assert callable(defn.implement_agent_factory)
        assert len(defn.validate_prompt_module_ids) > 0
        assert len(defn.supported_artifact_formats) > 0

    def test_application_supported_formats(self):
        registry = GenerationModeRegistry()
        register_application(registry)
        defn = registry.require("application")
        assert "web_single_file" in defn.supported_artifact_formats
        assert "web_multi_file" in defn.supported_artifact_formats
        assert "vue_project" in defn.supported_artifact_formats

    def test_only_application_registered_in_production(self):
        registry = GenerationModeRegistry()
        register_application(registry)
        assert set(registry.registered_mode_ids()) == {"application"}
