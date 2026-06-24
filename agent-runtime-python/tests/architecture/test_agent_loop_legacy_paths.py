"""Phase 0 失败测试：遗留入口和废弃文件扫描。

这些测试验证最终目标：
1. switch_mode.py 已删除
2. compose_prompt.py 已删除
3. 硬编码 fallback Prompt 文件已删除
4. ToolContractModule 已删除
5. 黑名单常量已删除

Phase 0 阶段这些测试预期失败，因为这些文件和符号当前仍然存在。
后续 Phase 3-4 删除后，这些测试应通过。
"""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_APP_DIR = _PROJECT_ROOT / "app"


class TestSwitchModeModuleIsRemoved:
    """验证 switch_mode.py 文件已删除。"""

    def test_switch_mode_module_is_removed(self):
        """switch_mode.py 文件不应存在。"""
        switch_mode_path = _APP_DIR / "agent_loop" / "tools" / "switch_mode.py"
        assert not switch_mode_path.exists(), (
            f"switch_mode.py 应被删除，但文件仍存在: {switch_mode_path}"
        )


class TestComposePromptNodeIsRemoved:
    """验证 ComposePromptNode 及其文件已删除。"""

    def test_compose_prompt_node_is_removed(self):
        """compose_prompt.py 文件不应存在。"""
        compose_prompt_path = _APP_DIR / "nodes" / "compose_prompt.py"
        assert not compose_prompt_path.exists(), (
            f"compose_prompt.py 应被删除，但文件仍存在: {compose_prompt_path}"
        )

    def test_compose_prompt_not_in_modeling_policy(self):
        """ModelPolicy 中不应有 compose_prompt 映射。"""
        from app.modeling.policy import DEFAULT_NODE_MODEL_ROLES

        assert "compose_prompt" not in DEFAULT_NODE_MODEL_ROLES, (
            "DEFAULT_NODE_MODEL_ROLES 中不应包含 compose_prompt 映射"
        )


class TestHardcodedFallbackPromptPackageIsRemoved:
    """验证旧硬编码 fallback Prompt 文件已删除。"""

    def test_plan_fallback_is_removed(self):
        """agent_loop/prompts/plan.py 不应存在。"""
        path = _APP_DIR / "agent_loop" / "prompts" / "plan.py"
        assert not path.exists(), (
            f"agent_loop/prompts/plan.py 应被删除，但文件仍存在: {path}"
        )

    def test_implement_fallback_is_removed(self):
        """agent_loop/prompts/implement.py 不应存在。"""
        path = _APP_DIR / "agent_loop" / "prompts" / "implement.py"
        assert not path.exists(), (
            f"agent_loop/prompts/implement.py 应被删除，但文件仍存在: {path}"
        )

    def test_plan_spec_fallback_is_removed(self):
        """agent_loop/prompts/plan_spec.py 不应存在。"""
        path = _APP_DIR / "agent_loop" / "prompts" / "plan_spec.py"
        assert not path.exists(), (
            f"agent_loop/prompts/plan_spec.py 应被删除，但文件仍存在: {path}"
        )

    def test_fallback_prompt_package_is_removed(self):
        """agent_loop/prompts/ 目录应为空或不存在。"""
        prompts_dir = _APP_DIR / "agent_loop" / "prompts"
        if prompts_dir.exists():
            remaining = list(prompts_dir.iterdir())
            py_files = [f for f in remaining if f.suffix == ".py" and f.name != "__init__.py"]
            assert len(py_files) == 0, (
                f"agent_loop/prompts/ 目录应无 .py 文件，但仍存在: {[f.name for f in py_files]}"
            )


class TestToolContractModuleIsRemoved:
    """验证 ToolContractModule 已删除。"""

    def test_tool_contract_module_is_removed(self):
        """ToolContractModule 类不应在 default_modules.py 中存在。"""
        from app.prompts import default_modules

        assert not hasattr(default_modules, "ToolContractModule"), (
            "ToolContractModule 应被删除，但仍在 default_modules.py 中存在"
        )


class TestBlacklistConstantsAreRemoved:
    """验证 Route/Validate 黑名单常量已删除。"""

    def test_route_excluded_module_ids_is_removed(self):
        """RouteStepNode 不应有 _ROUTE_EXCLUDED_MODULE_IDS。"""
        from app.agent_loop.nodes.route_step import RouteStepNode

        assert not hasattr(RouteStepNode, "_ROUTE_EXCLUDED_MODULE_IDS"), (
            "RouteStepNode._ROUTE_EXCLUDED_MODULE_IDS 应被删除"
        )

    def test_validate_excluded_module_ids_is_removed(self):
        """ValidateStepNode 不应有 _VALIDATE_EXCLUDED_MODULE_IDS。"""
        from app.agent_loop.nodes.validate_step import ValidateStepNode

        assert not hasattr(ValidateStepNode, "_VALIDATE_EXCLUDED_MODULE_IDS"), (
            "ValidateStepNode._VALIDATE_EXCLUDED_MODULE_IDS 应被删除"
        )


class TestSwitchModeNotInProduction:
    """验证 switch_mode 不再出现在生产代码中。"""

    def test_switch_mode_not_in_tool_policy(self):
        """tool_policy.py 中不应包含 switch_mode。"""
        source = (_APP_DIR / "agent_loop" / "tool_policy.py").read_text(encoding="utf-8")
        assert "switch_mode" not in source, (
            "tool_policy.py 中不应包含 switch_mode"
        )

    def test_switch_mode_not_in_event_mapper(self):
        """event_mapper.py 中不应包含 switch_mode。"""
        source = (_APP_DIR / "runtime" / "event_mapper.py").read_text(encoding="utf-8")
        assert "switch_mode" not in source, (
            "event_mapper.py 中不应包含 switch_mode"
        )

    def test_switch_mode_not_in_loop_modules(self):
        """loop_modules.py 中不应包含 switch_mode。"""
        source = (_APP_DIR / "prompts" / "loop_modules.py").read_text(encoding="utf-8")
        assert "switch_mode" not in source, (
            "loop_modules.py 中不应包含 switch_mode"
        )
