"""
Phase 0: 生成模式扩展边界架构约束测试

本文件包含三类目标断言：
1. GenerationModeDefinition 注册原子性 — 缺少任一必需部分时拒绝注册
2. 核心图不得导入具体非 application Agent — 防止核心图耦合未来 Agent
3. 生产 code_gen_type 引用清单冻结 — 记录迁移基线，后续 Phase 逐步消除

所有未来目标测试使用 xfail(strict=True, reason="Phase X") 标记，
禁止使用 skip，禁止无原因跳过。
"""

import ast
from pathlib import Path

import pytest

_APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"
_GRAPH_PY = _APP_DIR / "agent_loop" / "graph.py"
_CONTEXT_PY = _APP_DIR / "runtime" / "context.py"


class TestGenerationModeDefinitionRequiresCompleteBundle:
    """注册定义必须完整：缺少任一注册部分时失败。

    目标：GenerationModeDefinition 包含 mode_id、plan_prompt_module_ids、
    implement_agent_factory、validate_prompt_module_ids、
    supported_artifact_formats 五类字段，注册时原子校验。

    当前状态：GenerationModeRegistry 尚未实现，导入会失败。
    """

    def test_missing_mode_id_rejected(self):
        from app.generation_modes.types import GenerationModeDefinition

        with pytest.raises(Exception, match="mode_id"):
            GenerationModeDefinition(mode_id="", plan_prompt_module_ids=("a",), implement_agent_factory=lambda: None, validate_prompt_module_ids=("b",), supported_artifact_formats=frozenset({"web_single_file"}))

    def test_missing_plan_modules_rejected(self):
        from app.generation_modes.types import GenerationModeDefinition

        with pytest.raises(Exception):
            GenerationModeDefinition(mode_id="test", plan_prompt_module_ids=(), implement_agent_factory=lambda: None, validate_prompt_module_ids=("b",), supported_artifact_formats=frozenset({"web_single_file"}))

    def test_missing_implement_factory_rejected(self):
        from app.generation_modes.types import GenerationModeDefinition
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GenerationModeDefinition(mode_id="test", plan_prompt_module_ids=("a",), implement_agent_factory=None, validate_prompt_module_ids=("b",), supported_artifact_formats=frozenset({"web_single_file"}))

    def test_missing_validate_modules_rejected(self):
        from app.generation_modes.types import GenerationModeDefinition

        with pytest.raises(Exception):
            GenerationModeDefinition(mode_id="test", plan_prompt_module_ids=("a",), implement_agent_factory=lambda: None, validate_prompt_module_ids=(), supported_artifact_formats=frozenset({"web_single_file"}))

    def test_missing_artifact_formats_rejected(self):
        from app.generation_modes.types import GenerationModeDefinition

        with pytest.raises(Exception):
            GenerationModeDefinition(mode_id="test", plan_prompt_module_ids=("a",), implement_agent_factory=lambda: None, validate_prompt_module_ids=("b",), supported_artifact_formats=frozenset())

    def test_duplicate_mode_rejected(self):
        from app.generation_modes.registry import GenerationModeRegistry
        from app.generation_modes.types import GenerationModeDefinition

        registry = GenerationModeRegistry()
        kwargs = dict(mode_id="application", plan_prompt_module_ids=("a",), implement_agent_factory=lambda: None, validate_prompt_module_ids=("b",), supported_artifact_formats=frozenset({"web_single_file"}))
        defn = GenerationModeDefinition(**kwargs)
        registry.register(defn)
        with pytest.raises(Exception, match="已注册"):
            registry.register(GenerationModeDefinition(**kwargs))

    def test_only_application_registered_in_production(self):
        from app.generation_modes.registry import GenerationModeRegistry
        from app.generation_modes.application import register_application

        registry = GenerationModeRegistry()
        register_application(registry)
        assert set(registry.registered_mode_ids()) == {"application"}


class TestCoreGraphHasNoConcreteFutureAgentImports:
    """核心图不得导入具体非 application Agent。

    目标：graph.py 只能导入通用 Dispatcher 和公共节点，
    不得导入具体 Agent 实现（如 PresentationAgent、PrototypeAgent 等）。

    当前状态：graph.py 尚未使用 Dispatcher 模式，直接引用 ImplementStepNode。
    这个测试在 Phase 3 实现 Dispatcher 后才会通过。
    """

    FUTURE_AGENT_PATTERNS = (
        "presentation",
        "prototype",
        "diagram",
        "slide",
        "wireframe",
    )

    def test_graph_source_has_no_future_agent_imports(self):
        """graph.py 的 import 语句不得包含未来模式 Agent 名称。"""
        assert _GRAPH_PY.exists(), f"graph.py 不存在于 {_GRAPH_PY}，核心图文件缺失"
        source = _GRAPH_PY.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    for pattern in self.FUTURE_AGENT_PATTERNS:
                        assert pattern.lower() not in full_name.lower(), f"graph.py 导入了未来模式 Agent: {full_name}"

    def test_graph_uses_dispatcher_not_concrete_agents(self):
        """orchestrator 应通过 ImplementDispatcherNode 而非直接引用 ImplementStepNode。"""
        source = (Path(__file__).resolve().parent.parent.parent / "app" / "runtime" / "orchestrator.py").read_text(encoding="utf-8")
        assert "ImplementDispatcherNode" in source, "orchestrator.py 应使用 ImplementDispatcherNode"
        assert "ImplementStepNode" not in source, "orchestrator.py 不应直接引用 ImplementStepNode"


class TestProductionCodeGenTypeInventoryIsFrozen:
    """记录当前生产代码中 code_gen_type 引用清单，作为迁移基线。

    本测试不是要求引用数量为零（那是 Phase 6 的目标），
    而是记录当前基线并在后续 Phase 逐步减少时提供可追踪的锚点。

    新增 code_gen_type 引用（在 Phase 1-5 期间）应被检测到，
    以防止迁移期间引入新的旧字段依赖。
    """

    _FROZEN_FILES_USING_CODE_GEN_TYPE: frozenset[str] = frozenset(
        {
            "app/agent_loop/graph.py",
            "app/agent_loop/legacy_state_adapter.py",
            "app/agent_loop/nodes/init.py",
            "app/agent_loop/nodes/route_step.py",
            "app/agent_loop/nodes/validate_step.py",
            "app/agent_loop/state.py",
            "app/agent_loop/state_v2.py",
            "app/agent_loop/state_codec.py",
            "app/agent_loop/tools/decide_route.py",
            "app/agent_loop/tools/run_checks.py",
            "app/artifacts/manifest.py",
            "app/artifacts/types.py",
            "app/artifacts/writer.py",
            "app/capabilities/common/asset_summary.py",
            "app/capabilities/craft/selector.py",
            "app/capabilities/design_systems/selector.py",
            "app/capabilities/seeds/loader.py",
            "app/capabilities/seeds/selector.py",
            "app/capabilities/seeds/types.py",
            "app/capabilities/templates/loader.py",
            "app/capabilities/templates/selector.py",
            "app/capabilities/templates/types.py",
            "app/core/metrics.py",
            "app/grpc/code_generation_pb2.py",
            "app/grpc/code_generation_pb2_grpc.py",
            "app/grpc/platform_service_pb2.py",
            "app/grpc/platform_service_pb2_grpc.py",
            "app/grpc/tool_service_pb2.py",
            "app/grpc_client/platform_client.py",
            "app/grpc_client/tool_client.py",
            "app/grpc_server/code_generation_servicer.py",
            "app/grpc_server/interceptors.py",
            "app/modeling/resolver.py",
            "app/nodes/collect_artifacts.py",
            "app/nodes/load_assets.py",
            "app/nodes/select_capabilities.py",
            "app/prompts/asset_modules.py",
            "app/quality/structure_checker.py",
            "app/prompts/default_modules.py",
            "app/prompts/loop_modules.py",
            "app/prompts/route_modules.py",
            "app/prompts/tool_summary.py",
            "app/runtime/context.py",
            "app/runtime/orchestrator.py",
            "app/schemas/code_generation.py",
        }
    )

    _GRPC_GENERATED_DIR = "app/grpc/"

    def _scan_code_gen_type_files(self) -> set[str]:
        """扫描 app/ 目录下所有包含 code_gen_type/codeGenType/CodeGenType 的 .py 文件。"""
        found: set[str] = set()
        patterns = ("code_gen_type", "codeGenType", "CodeGenType")
        for py_file in _APP_DIR.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for pattern in patterns:
                if pattern in content:
                    rel = str(py_file.relative_to(_APP_DIR.parent)).replace("\\", "/")
                    found.add(rel)
                    break
        return found

    def test_code_gen_type_inventory_not_grown(self):
        """生产代码中 code_gen_type 引用文件数不得超过冻结基线。

        允许减少（后续 Phase 迁移移除），但不允许新增。
        gRPC 生成代码目录允许存在但不算入核心业务逻辑计数。
        """
        current = self._scan_code_gen_type_files()
        non_grpc_current = {f for f in current if not f.startswith(self._GRPC_GENERATED_DIR)}
        non_grpc_frozen = {f for f in self._FROZEN_FILES_USING_CODE_GEN_TYPE if not f.startswith(self._GRPC_GENERATED_DIR)}
        new_files = non_grpc_current - non_grpc_frozen
        assert not new_files, (
            f"发现新增 code_gen_type 引用文件（迁移期间不应引入新的旧字段依赖）: {sorted(new_files)}\n"
            f"当前非 gRPC 文件数: {len(non_grpc_current)}, 冻结基线: {len(non_grpc_frozen)}"
        )

    @pytest.mark.xfail(strict=True, reason="Phase 6: codeGenType 物理删除后才为零")
    def test_production_code_gen_type_count_is_zero(self):
        """最终目标：生产代码中不存在 code_gen_type/codeGenType/CodeGenType 引用。"""
        current = self._scan_code_gen_type_files()
        non_grpc_current = {f for f in current if not f.startswith(self._GRPC_GENERATED_DIR)}
        assert len(non_grpc_current) == 0, f"仍存在 code_gen_type 引用: {sorted(non_grpc_current)}"
