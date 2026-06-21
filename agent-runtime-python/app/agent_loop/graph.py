import logging

from langgraph.graph import StateGraph

from app.agent_loop.state import AgentLoopState

logger = logging.getLogger("app.agent_loop.graph")


def _get_state_attr(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _route_finished(state) -> bool:
    """统一的循环终止检查，在所有条件边中使用。"""
    if _get_state_attr(state, "status") == "waiting_for_user":
        return True
    if _get_state_attr(state, "status") in ("completed", "failed"):
        return True
    if _get_state_attr(state, "iteration") >= _get_state_attr(state, "max_iterations"):
        return True
    if _get_state_attr(state, "mode_switches") >= _get_state_attr(state, "max_mode_switches"):
        return True
    return False


def route_after_route_step(state: AgentLoopState) -> str:
    """route_step 完成后，根据 route_decision 或 status 路由。"""
    if _route_finished(state):
        return "finish"
    decision = _get_state_attr(state, "route_decision")
    if decision and isinstance(decision, dict):
        mode = decision.get("mode", "plan")
        if mode == "finish":
            return "finish"
        if mode == "plan":
            return "plan_step"
        if mode == "implement":
            return "implement_step"
        if mode == "validate":
            return "validate_step"
    return "plan_step"


def route_after_plan_step(state: AgentLoopState) -> str:
    """plan_step 完成后的路由逻辑。

    Plan 不再直接进入 Implement：
    - plan_just_finished=True → route_step
    - 达到终止条件 → finish
    - plan_iterations 超限 → route_step
    - 否则 → plan_step
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "plan_just_finished"):
        return "route_step"
    if _get_state_attr(state, "plan_iterations") >= _get_state_attr(state, "max_plan_iterations"):
        logger.warning(
            "route | plan_iterations=%d exceeded max_plan_iterations=%d, routing to route_step",
            _get_state_attr(state, "plan_iterations"),
            _get_state_attr(state, "max_plan_iterations"),
        )
        return "route_step"
    return "plan_step"


def route_after_implement_step(state: AgentLoopState) -> str:
    """implement_step 完成后的路由逻辑。

    finish 或结构化重新规划请求标记 implement_just_finished=True 时离开 Implement，
    否则继续 implement_step。
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "implement_just_finished"):
        return "route_step"
    return "implement_step"


def route_after_validate_step(state: AgentLoopState) -> str:
    """validate_step 完成后的路由逻辑。

    只有 decide_validation 标记 validate_just_finished=True 或达到上限时才离开，
    否则继续 validate_step。
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "validate_just_finished"):
        return "route_step"
    if _get_state_attr(state, "validate_iterations") >= _get_state_attr(state, "max_validate_iterations"):
        return "route_step"
    return "validate_step"


def build_agent_loop_graph(
    init_node,
    route_step_node,
    plan_step_node,
    implement_step_node,
    validate_step_node,
    finish_node,
) -> StateGraph:
    """构建 Agent Loop 图结构。

    图结构：
        init → route_step → [plan_step / implement_step / validate_step / finish]

        plan_step → plan_step / route_step（计划完成→路由，否则继续规划）
        implement_step → implement_step / route_step（完成或请求重新规划→路由，否则继续实现）
        validate_step → validate_step / route_step（决策提交或超限→路由，否则继续校验）
    """
    graph = StateGraph(AgentLoopState)

    graph.add_node("init", init_node)
    graph.add_node("route_step", route_step_node)
    graph.add_node("plan_step", plan_step_node)
    graph.add_node("implement_step", implement_step_node)
    graph.add_node("validate_step", validate_step_node)
    graph.add_node("finish", finish_node)

    graph.set_entry_point("init")
    graph.add_edge("init", "route_step")

    graph.add_conditional_edges(
        "route_step",
        route_after_route_step,
        {
            "plan_step": "plan_step",
            "implement_step": "implement_step",
            "validate_step": "validate_step",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "plan_step",
        route_after_plan_step,
        {"plan_step": "plan_step", "route_step": "route_step", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "implement_step",
        route_after_implement_step,
        {"implement_step": "implement_step", "route_step": "route_step", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "validate_step",
        route_after_validate_step,
        {"validate_step": "validate_step", "route_step": "route_step", "finish": "finish"},
    )

    return graph.compile()
