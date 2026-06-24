"""Phase 0 失败测试：Prompt 与工具摘要一致性。

这些测试验证最终目标：
1. Prompt 中的动态工具摘要区域展示的工具集合等于 resolver 解析出的工具集合
2. 业务 Prompt 模块不手写具体工具调用签名
3. 工具 description 不引用其他工具名称

Phase 0 阶段这些测试验证当前存在的串台问题，
后续 Phase 1-2 实现后，这些测试应逐步通过。
"""

import re


from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import (
    PLAN_TOOLS,
    IMPLEMENT_TOOLS,
    ROUTE_TOOLS,
    VALIDATE_TOOLS,
)


_REGISTERED_TOOL_NAMES: frozenset[str] = frozenset(
    PLAN_TOOLS | IMPLEMENT_TOOLS | ROUTE_TOOLS | VALIDATE_TOOLS
)


class TestPromptToolConsistencyCurrentState:
    """验证当前 Prompt 与工具集合的一致性问题。

    这些测试在 Phase 0 预期失败，暴露当前串台问题。
    """

    def test_route_prompt_currently_contains_ask_user_reference(self):
        """RouteInitialModule 不应包含 ask_user 引用。"""
        from app.prompts.route_modules import RouteInitialModule

        module = RouteInitialModule()
        state = AgentLoopState(mode="plan", route_decided=False)
        ctx = _stub_context()
        rendered = module.render(ctx, state)

        assert "ask_user" not in rendered, (
            "RouteInitialModule 不应包含 ask_user 引用"
        )

    def test_tool_contract_module_is_removed(self):
        """ToolContractModule 已被删除，不应再存在。"""
        from app.prompts import default_modules

        assert not hasattr(default_modules, "ToolContractModule"), (
            "ToolContractModule 应被删除"
        )

    def test_artifact_module_currently_contains_write_file(self):
        """ArtifactOutputContractModule 不应包含 write_file 引用。"""
        from app.prompts.asset_modules import ArtifactOutputContractModule

        module = ArtifactOutputContractModule()
        state = AgentLoopState(mode="plan")
        ctx = _stub_context()
        rendered = module.render(ctx, state)

        assert "write_file" not in rendered, (
            "ArtifactOutputContractModule 不应包含 write_file 引用"
        )

    def test_runtime_boundary_currently_claims_write_access(self):
        """RuntimeBoundaryModule 不应声称写入权限（在只读模式下误导）。"""
        from app.prompts.default_modules import RuntimeBoundaryModule

        module = RuntimeBoundaryModule()
        state = AgentLoopState(mode="validate")
        ctx = _stub_context()
        rendered = module.render(ctx, state)

        assert "写入" not in rendered and "write" not in rendered.lower(), (
            "Phase 2: RuntimeBoundaryModule 不应声称写入权限"
        )


class TestPromptToolConsistencyTarget:
    """验证目标：业务模块不包含已注册工具的具体名称。

    Phase 0 时这些测试预期失败，因为目标 API 尚未实现。
    """

    def test_business_modules_do_not_contain_registered_tool_names(self):
        """业务 Prompt 模块不应包含当前注册工具的具体名称。"""
        from app.prompts.profiles import PROMPT_PROFILES
        from app.prompts.composer import PromptComposer

        for profile_id in PROMPT_PROFILES:
            profile_module_ids = PROMPT_PROFILES[profile_id]
            registry = _build_registry_with_all_modules()
            modules = registry.require_many(profile_module_ids)
            composer = PromptComposer(modules)
            state = AgentLoopState(mode="plan")
            messages = composer.compose(_stub_context(), state)
            system_prompt = messages[0]["content"] if messages else ""

            for tool_name in _REGISTERED_TOOL_NAMES:
                pattern = rf"\b{re.escape(tool_name)}\b"
                if tool_name in ("read_file", "read_dir", "write_file"):
                    continue
                assert not re.search(pattern, system_prompt), (
                    f"Profile {profile_id}: 业务 Prompt 不应包含工具名 {tool_name}"
                )


class TestToolDescriptionsDoNotReferenceOtherTools:
    """验证目标：工具 description 不引用其他工具名称。

    Phase 0 时 SelectSkillTool 的 description 引用了 read_asset 和 run_command。
    """

    def test_tool_descriptions_do_not_reference_other_tools(self):
        """所有 BaseTool 的 description 不应引用其他工具名称。"""
        from app.agent_loop.tools.select_skill import SelectSkillTool

        tool = SelectSkillTool()
        other_tool_names = _REGISTERED_TOOL_NAMES - {tool.name}
        for other_name in other_tool_names:
            assert other_name not in tool.description, (
                f"工具 {tool.name} 的 description 引用了其他工具名 {other_name}"
            )


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


def _stub_context():
    from unittest.mock import MagicMock
    from app.runtime.context import ExecutionContext, CodeGenType, RunMode

    ctx = MagicMock(spec=ExecutionContext)
    ctx.prompt = "test prompt"
    ctx.code_gen_type = CodeGenType.VUE_PROJECT
    ctx.run_mode = RunMode.GENERATE
    ctx.workspace_path = "/tmp/test"
    return ctx
