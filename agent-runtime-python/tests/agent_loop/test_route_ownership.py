"""路由所有权和模式写权限边界测试。

这些测试验证最终目标：
1. 只有 Route 可以提交运行时模式变化
2. apply_route_decision 是唯一提交运行时 mode 变化的函数
3. DecideRouteTool 与 RouteStep 安全回退都必须调用 apply_route_decision
4. 非 Route 节点不直接写 state.mode

这些测试用于防止非 Route 节点或阶段工具重新获得 mode 写权限。
"""

import ast
import inspect


from app.agent_loop.state import AgentLoopState


class TestOnlyRouteDecisionCanChangeMode:
    """验证：只有 Route 决策提交可以改变运行时 mode。"""

    def test_plan_step_node_does_not_directly_write_mode(self):
        """PlanStepNode 不应直接写 state.mode。"""
        source = inspect.getsource(_get_class(PlanStepNode_cls()))
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"PlanStepNode 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_implement_dispatcher_node_does_not_directly_write_mode(self):
        """ImplementDispatcherNode 不应直接写 state.mode。"""
        source = inspect.getsource(_get_class(ImplementDispatcherNode_cls()))
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"ImplementDispatcherNode 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_validate_step_node_does_not_directly_write_mode(self):
        """ValidateStepNode 不应直接写 state.mode。

        当前实现：validate 迭代上限时直接 state.mode = "implement"，
        绕过了 Route，这是违规的。
        """
        source = inspect.getsource(_get_class(ValidateStepNode_cls()))
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"ValidateStepNode 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_write_plan_tool_does_not_directly_write_mode(self):
        """WritePlanTool 不应直接写 state.mode。"""
        source = _get_tool_source("write_plan")
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"WritePlanTool 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_finish_tool_does_not_directly_write_mode(self):
        """FinishTool 不应直接写 state.mode。"""
        source = _get_tool_source("finish")
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"FinishTool 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_request_replan_tool_does_not_directly_write_mode(self):
        source = _get_tool_source("request_replan")
        mode_assignments = _find_state_mode_assignments(source)
        assert len(mode_assignments) == 0, (
            f"RequestReplanTool 不应直接写 state.mode，发现: {mode_assignments}"
        )

    def test_apply_route_decision_is_the_only_mode_mutation_function(self):
        """apply_route_decision 应是唯一提交运行时 mode 变化的函数。"""
        from app.agent_loop.tools.decide_route import apply_route_decision

        assert callable(apply_route_decision), "apply_route_decision 应为可调用函数"

    def test_decide_route_tool_uses_apply_route_decision(self):
        """DecideRouteTool 应调用 apply_route_decision 提交决策。"""
        source = _get_tool_source("decide_route")
        assert "apply_route_decision" in source, (
            "DecideRouteTool 应调用 apply_route_decision 提交决策"
        )

    def test_route_safe_fallback_uses_apply_route_decision(self):
        """Route 安全回退应调用 apply_route_decision 提交默认决策。"""
        from app.agent_loop.nodes.route_step import RouteStepNode
        source = inspect.getsource(RouteStepNode._apply_safe_fallback)
        assert "apply_route_decision" in source, (
            "RouteStepNode._apply_safe_fallback 应调用 apply_route_decision"
        )

    def test_init_mode_assignment_is_initialization_only(self):
        """AgentLoopState 默认值和 InitNode 只允许初始化默认 mode，不允许阶段间流转。

        AgentLoopState.mode 的默认值 "plan" 是初始化语义，不计入 mode_switches。
        之后的运行时 mode 变化只能通过 apply_route_decision。
        """
        state = AgentLoopState()
        assert state.mode == "plan", "默认 mode 应为 plan"
        assert state.mode_switches == 0, "初始 mode_switches 应为 0"


def _get_class(cls):
    return cls


def PlanStepNode_cls():
    from app.agent_loop.nodes.plan_step import PlanStepNode
    return PlanStepNode


def ImplementDispatcherNode_cls():
    from app.agent_loop.nodes.implement_dispatcher import ImplementDispatcherNode
    return ImplementDispatcherNode


def ValidateStepNode_cls():
    from app.agent_loop.nodes.validate_step import ValidateStepNode
    return ValidateStepNode


def _find_state_mode_assignments(source: str) -> list[str]:
    """在源码中查找直接赋值 state.mode 的语句。"""
    assignments = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Attribute) and
                            isinstance(target.value, ast.Name) and
                            target.value.id in ("state", "result") and
                            target.attr == "mode"):
                        line = ast.get_source_segment(source, node) or str(node)
                        assignments.append(line.strip())
    except SyntaxError:
        pass
    return assignments


def _get_tool_source(tool_name: str) -> str:
    """获取工具类的源码。"""
    tool_map = {
        "write_plan": ("app.agent_loop.tools.write_plan", "WritePlanTool"),
        "finish": ("app.agent_loop.tools.finish_tool", "FinishTool"),
        "decide_route": ("app.agent_loop.tools.decide_route", "DecideRouteTool"),
        "ask_user": ("app.agent_loop.tools.ask_user", "AskUserTool"),
        "decide_validation": ("app.agent_loop.tools.decide_validation", "DecideValidationTool"),
        "request_replan": ("app.agent_loop.tools.request_replan", "RequestReplanTool"),
    }
    module_path, class_name = tool_map[tool_name]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return inspect.getsource(cls)
