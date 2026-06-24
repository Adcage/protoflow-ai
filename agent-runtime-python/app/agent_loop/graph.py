import logging

from langgraph.graph import StateGraph

from app.agent_loop.state import AgentLoopState

logger = logging.getLogger("app.agent_loop.graph")


def _get_state_attr(state, key, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _ensure_execution_contract_after_plan(state: AgentLoopState) -> None:
    envelope = getattr(state, "_state_envelope", None)
    if envelope is None:
        return
    execution = envelope.workflow.execution
    if getattr(execution, "execution_contract", None) is not None:
        return
    plan_state = envelope.workflow.plan
    impl_plan = getattr(plan_state, "implementation_plan", None)
    if impl_plan is None:
        return
    generation_mode = getattr(envelope.workflow, "generation_mode", None) or "application"
    artifact_format = _infer_artifact_format_from_code_gen_type(state)
    try:
        from app.agent_loop.execution_contract import from_implementation_plan
        contract = from_implementation_plan(impl_plan, generation_mode, artifact_format)
        execution.execution_contract = contract.model_dump()
    except Exception as e:
        logger.warning("_ensure_execution_contract_after_plan | failed: %s", e)


def _infer_artifact_format_from_code_gen_type(state: AgentLoopState) -> str:
    code_gen_type_str = ""
    artifact_type_state = getattr(state, "artifact_type_state", None)
    if artifact_type_state is not None:
        code_gen_type_str = getattr(artifact_type_state, "effective", "")
    if not code_gen_type_str:
        code_gen_type_str = getattr(state, "recommended_code_gen_type", "")
    if not code_gen_type_str:
        code_gen_type_str = "vue_project"
    mapping = {
        "single_file": "web_single_file",
        "multi-file": "web_multi_file",
        "vue_project": "vue_project",
    }
    return mapping.get(code_gen_type_str, "vue_project")


def _route_finished(state) -> bool:
    if _get_state_attr(state, "status") == "waiting_for_user":
        return True
    if _get_state_attr(state, "status") in ("completed", "failed"):
        return True
    if _get_state_attr(state, "iteration") >= _get_state_attr(state, "max_iterations"):
        if hasattr(state, 'status') and state.status == "running":
            state.status = "failed"
            if not state.final_summary:
                state.final_summary = (
                    f"全局迭代上限 {state.max_iterations} 已到 "
                    f"(mode={state.mode}, iteration={state.iteration})"
                )
        return True
    if _get_state_attr(state, "mode_switches") >= _get_state_attr(state, "max_mode_switches"):
        if hasattr(state, 'status') and state.status == "running":
            state.status = "failed"
            if not state.final_summary:
                state.final_summary = (
                    f"模式切换上限 {state.max_mode_switches} 已到 "
                    f"(mode={state.mode}, mode_switches={state.mode_switches})"
                )
        return True
    return False


def route_after_route_step(state: AgentLoopState) -> str:
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
    """plan_step 完成后路由。

    状态变更已在 PlanStepNode.apply_exit_transition 中完成。
    此函数仅读取状态决定下一节点。
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "plan_just_finished"):
        return "implement_step"
    return "plan_step"


def route_after_implement_step(state: AgentLoopState) -> str:
    """implement_step 完成后路由。

    状态变更已在 ImplementDispatcherNode.apply_exit_transition 中完成。
    此函数仅读取状态决定下一节点。
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "implement_just_finished"):
        if getattr(state, "implement_replan_requested", False):
            return "route_step"
        return "validate_step"
    return "implement_step"


def route_after_validate_step(state: AgentLoopState) -> str:
    """validate_step 完成后路由。

    状态变更已在 ValidateStepNode.apply_exit_transition 中完成。
    此函数仅读取状态决定下一节点。
    """
    if _route_finished(state):
        return "finish"
    if _get_state_attr(state, "validate_just_finished"):
        validation_status = _get_state_attr(state, "validation_status", "pending")
        if validation_status == "passed":
            return "finish"
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

    固定流转图：
        init → route_step → [plan_step / implement_step / finish]

        plan_step → plan_step / implement_step / finish
        implement_step → implement_step / validate_step / route_step / finish
        validate_step → validate_step / route_step / finish
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
        {"plan_step": "plan_step", "implement_step": "implement_step", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "implement_step",
        route_after_implement_step,
        {
            "implement_step": "implement_step",
            "validate_step": "validate_step",
            "route_step": "route_step",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "validate_step",
        route_after_validate_step,
        {"validate_step": "validate_step", "route_step": "route_step", "finish": "finish"},
    )

    return graph.compile()
