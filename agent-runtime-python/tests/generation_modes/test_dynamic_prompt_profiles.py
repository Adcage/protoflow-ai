"""Phase 1 Task 1-2: 共享 Plan/Validate Prompt 动态注入测试。"""

import re

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode, IMPLEMENT_TOOLS
from app.agent_loop.tool_resolver import ModeToolResolver
from app.generation_modes.registry import GenerationModeRegistry
from app.generation_modes.types import GenerationModeDefinition
from app.prompts.composer import PromptComposer
from app.prompts.profiles import PROMPT_PROFILES, resolve_profile_module_ids


def _make_registry_with_application():
    registry = GenerationModeRegistry()
    registry.register(GenerationModeDefinition(
        mode_id="application",
        plan_prompt_module_ids=("application_plan",),
        implement_agent_factory=lambda: None,
        validate_prompt_module_ids=("application_validate",),
        supported_artifact_formats=frozenset({"web_single_file", "web_multi_file", "vue_project"}),
    ))
    return registry


class TestResolveProfileModuleIds:
    def test_base_plan_profile_without_mode(self):
        result = resolve_profile_module_ids("plan")
        assert result == PROMPT_PROFILES["plan"]

    def test_base_validate_profile_without_mode(self):
        result = resolve_profile_module_ids("validate")
        assert result == PROMPT_PROFILES["validate"]

    def test_application_plan_profile_injects_application_module_once(self):
        registry = _make_registry_with_application()
        result = resolve_profile_module_ids("plan", generation_mode="application", mode_registry=registry)
        assert "application_plan" in result
        assert result.count("application_plan") == 1
        base_ids = set(PROMPT_PROFILES["plan"])
        for mid in base_ids:
            assert mid in result

    def test_application_validate_profile_injects_application_module_once(self):
        registry = _make_registry_with_application()
        result = resolve_profile_module_ids("validate", generation_mode="application", mode_registry=registry)
        assert "application_validate" in result
        assert result.count("application_validate") == 1

    def test_unresolved_plan_profile_has_clarification_module(self):
        result = resolve_profile_module_ids("plan", generation_mode="unresolved")
        assert "generation_mode_clarification" in result
        assert "application_plan" not in result

    def test_unresolved_plan_no_mode_specific_module(self):
        result = resolve_profile_module_ids("plan", generation_mode="unresolved")
        assert "application_plan" not in result
        assert "application_validate" not in result

    def test_validate_rejects_unresolved_generation_mode(self):
        from app.core.exceptions import AgentRuntimeError

        with pytest.raises(AgentRuntimeError, match="unresolved"):
            resolve_profile_module_ids("validate", generation_mode="unresolved")

    def test_unknown_profile_raises(self):
        from app.core.exceptions import AgentRuntimeError

        with pytest.raises(AgentRuntimeError, match="不存在"):
            resolve_profile_module_ids("nonexistent_profile")

    def test_unregistered_mode_falls_back_to_base(self):
        registry = _make_registry_with_application()
        result = resolve_profile_module_ids("plan", generation_mode="unknown_mode", mode_registry=registry)
        assert result == PROMPT_PROFILES["plan"]

    def test_module_order_preserved(self):
        registry = _make_registry_with_application()
        result = resolve_profile_module_ids("plan", generation_mode="application", mode_registry=registry)
        result_list = list(result)
        tool_list_idx = result_list.index("tool_list")
        app_plan_idx = result_list.index("application_plan")
        assert app_plan_idx < tool_list_idx, "模式模块应插入在 tool_list 之前"

    def test_route_profiles_not_affected_by_mode(self):
        registry = _make_registry_with_application()
        for profile_id in ["route_initial", "route_after_plan", "route_after_implement", "route_after_validate"]:
            result = resolve_profile_module_ids(profile_id, generation_mode="application", mode_registry=registry)
            assert result == PROMPT_PROFILES[profile_id], f"{profile_id} 不应受 generationMode 影响"


class TestDynamicPromptToolNamesEqualResolvedToolset:
    """Phase 1 Task 1-2: 动态工具摘要中的工具名必须与 ResolvedToolSet.names 完全一致。"""

    def test_dynamic_prompt_tool_names_equal_resolved_toolset(self):
        from app.prompts.registry import PromptModuleRegistry
        from app.prompts.default_modules import (
            RuntimeBoundaryModule,
            SafetyAndInjectionResistanceModule,
            ProjectRulesModule,
            OutputContractModule,
            AntiRoleplayModule,
            TaskContextModule,
        )
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
        from app.prompts.asset_modules import ArtifactOutputContractModule
        from app.prompts.test_modules import TestModeInfoModule, ProductionSecurityModule
        from unittest.mock import MagicMock
        from langchain_core.tools import BaseTool
        from pydantic import BaseModel

        class _DummyArgs(BaseModel):
            pass

        class _DummyTool(BaseTool):
            name: str = ""
            description: str = "dummy"
            args_schema: type[BaseModel] = _DummyArgs

            def _run(self, *args, **kwargs):
                return "ok"

        registry = _make_registry_with_application()
        prompt_registry = PromptModuleRegistry()
        for cls in [
            RuntimeBoundaryModule,
            SafetyAndInjectionResistanceModule,
            ProductionSecurityModule,
            TestModeInfoModule,
            ProjectRulesModule,
            ToolListModule,
            PlanWorkflowModule,
            ImplementWorkflowModule,
            ValidateWorkflowModule,
            PlanSpecModule,
            ValidateFeedbackModule,
            ArtifactOutputContractModule,
            OutputContractModule,
            SkillContextModule,
            TaskContextModule,
            RouteInitialModule,
            RouteAfterPlanModule,
            RouteAfterImplementModule,
            RouteAfterValidateModule,
            AntiRoleplayModule,
        ]:
            prompt_registry.register(cls())

        dummy_tools = [_DummyTool(name=n) for n in IMPLEMENT_TOOLS]
        toolset = ModeToolResolver.resolve(AgentMode.IMPLEMENT, dummy_tools)

        profile_ids = resolve_profile_module_ids(
            "implement",
            generation_mode="application",
            mode_registry=registry,
        )
        modules = prompt_registry.require_many(profile_ids)
        composer = PromptComposer(modules)

        ctx = MagicMock()
        ctx.prompt = "test"
        state = AgentLoopState(mode="implement", status="running")
        messages = composer.compose(ctx, state, toolset)

        system_prompt = messages[0]["content"] if messages else ""

        tool_summary_section = ""
        marker = "## 当前模式可用能力"
        if marker in system_prompt:
            tool_summary_section = system_prompt[system_prompt.index(marker):]

        tool_name_pattern = re.compile(r"`(\w+)\(")
        summary_tool_names = frozenset(tool_name_pattern.findall(tool_summary_section))

        assert summary_tool_names == toolset.names, (
            f"动态工具摘要工具名 {summary_tool_names} != ResolvedToolSet.names {toolset.names}"
        )
