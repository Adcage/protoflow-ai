"""Prompt Profile 测试：验证 profile 组合、工具摘要一致性和权限边界。"""

from dataclasses import dataclass
from typing import Any

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import AgentMode


@dataclass(frozen=True)
class PromptCase:
    profile_id: str
    mode: AgentMode
    state: AgentLoopState
    expected_tool_names: frozenset[str]


def _make_prompt_cases() -> list[PromptCase]:
    state_route_initial = AgentLoopState(mode="plan", route_decided=False)
    state_route_after_plan = AgentLoopState(
        mode="plan", route_decided=True, plan_just_finished=True,
        implementation_outline={"text": "plan content"}
    )
    state_route_after_implement = AgentLoopState(
        mode="implement", implement_just_finished=True
    )
    state_route_after_validate = AgentLoopState(
        mode="validate", validate_just_finished=True
    )
    state_plan = AgentLoopState(mode="plan", route_decided=True)
    state_implement = AgentLoopState(mode="implement", route_decided=True)
    state_validate = AgentLoopState(mode="validate", route_decided=True)

    return [
        PromptCase(profile_id="route_initial", mode=AgentMode.ROUTE, state=state_route_initial,
                    expected_tool_names=frozenset({"read_file", "read_dir", "decide_route"})),
        PromptCase(profile_id="route_after_plan", mode=AgentMode.ROUTE, state=state_route_after_plan,
                    expected_tool_names=frozenset({"read_file", "read_dir", "decide_route"})),
        PromptCase(profile_id="route_after_implement", mode=AgentMode.ROUTE, state=state_route_after_implement,
                    expected_tool_names=frozenset({"read_file", "read_dir", "decide_route"})),
        PromptCase(profile_id="route_after_validate", mode=AgentMode.ROUTE, state=state_route_after_validate,
                    expected_tool_names=frozenset({"read_file", "read_dir", "decide_route"})),
        PromptCase(profile_id="plan", mode=AgentMode.PLAN, state=state_plan,
                    expected_tool_names=frozenset({"read_file", "read_dir", "read_asset", "run_command",
                                                   "ask_user", "select_skill", "write_plan"})),
        PromptCase(profile_id="implement", mode=AgentMode.IMPLEMENT, state=state_implement,
                    expected_tool_names=frozenset({"read_file", "read_dir", "read_asset", "write_file",
                                                   "run_command", "complete_implementation", "request_replan"})),
        PromptCase(profile_id="validate", mode=AgentMode.VALIDATE, state=state_validate,
                    expected_tool_names=frozenset({"read_file", "read_dir", "run_checks", "submit_validation_report"})),
    ]


_PROMPT_CASES = _make_prompt_cases()


class TestRouteInitialPromptExcludesAskUserCapability:
    def test_route_initial_prompt_excludes_ask_user_capability(self):
        case = _PROMPT_CASES[0]
        toolset = _resolve_toolset(case.mode, case.expected_tool_names)
        system_prompt = _compose_for_case(case, toolset)

        assert "ask_user" not in system_prompt, (
            "Route initial Prompt 不应包含 ask_user 能力声明"
        )


class TestPlanPromptExcludesArtifactContract:
    def test_plan_prompt_excludes_artifact_contract(self):
        case = _PROMPT_CASES[4]
        toolset = _resolve_toolset(case.mode, case.expected_tool_names)
        system_prompt = _compose_for_case(case, toolset)

        artifact_keywords = ["artifact_output_contract", "write_file", "写入文件"]
        for kw in artifact_keywords:
            assert kw not in system_prompt, (
                f"Plan Prompt 不应包含 Artifact 写入契约关键词: {kw}"
            )


class TestValidatePromptClaimsReadonlyBehavior:
    def test_validate_prompt_claims_readonly_behavior(self):
        case = _PROMPT_CASES[6]
        toolset = _resolve_toolset(case.mode, case.expected_tool_names)
        system_prompt = _compose_for_case(case, toolset)

        write_keywords = ["write_file", "写入文件", "修改文件"]
        for kw in write_keywords:
            assert kw not in system_prompt, (
                f"Validate Prompt 不应包含写入能力关键词: {kw}"
            )


class TestDynamicToolSummaryMatchesResolvedTools:
    @pytest.mark.parametrize("case", _PROMPT_CASES, ids=lambda c: c.profile_id)
    def test_dynamic_tool_summary_matches_resolved_tools(self, case: PromptCase):
        toolset = _resolve_toolset(case.mode, case.expected_tool_names)
        system_prompt = _compose_for_case(case, toolset)

        summary_tool_names = _extract_tool_names_from_summary(system_prompt)
        assert summary_tool_names == case.expected_tool_names, (
            f"Profile {case.profile_id}: 摘要工具 {summary_tool_names} "
            f"!= 期望工具 {case.expected_tool_names}"
        )


class TestImplementReplanPrompt:
    def test_incomplete_plan_requires_replan_request_not_completion(self):
        case = _PROMPT_CASES[5]
        toolset = _resolve_toolset(case.mode, case.expected_tool_names)
        system_prompt = _compose_for_case(case, toolset)

        assert "提交重新规划请求" in system_prompt
        assert "在提交阶段完成结果时说明\"需要重新规划\"" not in system_prompt


class TestRouteAfterImplementPrompt:
    def test_structured_replan_request_recommends_plan(self):
        from app.prompts.route_modules import RouteAfterImplementModule

        state = AgentLoopState(
            mode="implement",
            implement_just_finished=True,
            implement_replan_requested=True,
            implement_replan_reason="计划缺少文件范围",
            implement_phase_files=["src/App.vue"],
        )
        prompt = RouteAfterImplementModule().render(_stub_context(), state)

        assert "建议路由：plan" in prompt
        assert "计划缺少文件范围" in prompt
        assert "AI 刚才完成了什么工作" not in prompt

    def test_phase_file_count_does_not_fall_back_to_global_history(self):
        from app.prompts.route_modules import RouteAfterImplementModule
        from app.runtime.context import RunMode

        context = _stub_context()
        context.run_mode = RunMode.MODIFY
        state = AgentLoopState(
            mode="implement",
            implement_just_finished=True,
            implement_phase_files=[],
            files_touched=[f"old-{index}.vue" for index in range(10)],
        )
        prompt = RouteAfterImplementModule().render(context, state)

        assert "本次改动的文件数：0" in prompt
        assert "建议路由：validate" in prompt


def _compose_for_case(case: PromptCase, toolset) -> str:
    from app.prompts.profiles import PROMPT_PROFILES
    from app.prompts.composer import PromptComposer

    registry = _build_registry_with_all_modules()
    profile_module_ids = PROMPT_PROFILES[case.profile_id]
    modules = registry.require_many(profile_module_ids)
    composer = PromptComposer(modules)
    messages = composer.compose(_stub_context(), case.state, toolset)
    return messages[0]["content"] if messages else ""


def _build_registry_with_all_modules():
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

    registry = PromptModuleRegistry()
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
        registry.register(cls())
    return registry


def _resolve_toolset(mode: AgentMode, expected_names: frozenset[str]) -> Any:
    from app.agent_loop.tool_resolver import ModeToolResolver
    from langchain_core.tools import BaseTool

    class _StubTool(BaseTool):
        name: str = ""
        description: str = "stub"

        def _run(self, *args, **kwargs):
            return "stub"

        async def _arun(self, *args, **kwargs):
            return "stub"

    candidates = [_StubTool(name=n) for n in expected_names]
    return ModeToolResolver.resolve(mode, candidates)


def _extract_tool_names_from_summary(system_prompt: str) -> frozenset[str]:
    import re

    section_match = re.search(
        r"## 当前模式可用能力\s+(.*?)(?=\n## |\Z)", system_prompt, re.DOTALL
    )
    if not section_match:
        return frozenset()

    tool_names = re.findall(r"- `(\w+)\(", section_match.group(1))
    return frozenset(tool_names)


def _stub_context():
    from unittest.mock import MagicMock
    from app.runtime.context import ExecutionContext, CodeGenType, RunMode

    ctx = MagicMock(spec=ExecutionContext)
    ctx.prompt = "test prompt"
    ctx.code_gen_type = CodeGenType.VUE_PROJECT
    ctx.run_mode = RunMode.GENERATE
    ctx.workspace_path = "/tmp/test"
    return ctx
