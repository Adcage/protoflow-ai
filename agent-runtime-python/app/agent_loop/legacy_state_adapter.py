import logging
from typing import Any

from app.agent_loop.state_v2 import (
    ArtifactTypeState,
    ConversationStateV2,
    ExecutionStateV2,
    PlanStateV2,
    ProgressStateV2,
    RoutingStateV2,
    ValidationStateV2,
    WorkflowState,
    WorkflowStateEnvelope,
)

logger = logging.getLogger("app.agent_loop.legacy_state_adapter")

_MODE_MAP: dict[str, str] = {
    "plan": "plan",
    "implement": "implement",
    "validate": "validate",
    "finish": "finished",
    "route": "route",
}

_STATUS_MAP: dict[str, str] = {
    "running": "plan",
    "completed": "finished",
    "failed": "blocked",
    "waiting_for_user": "plan",
}


def _map_mode(raw_mode: Any, raw_status: Any) -> str:
    mode_str = str(raw_mode) if raw_mode else "plan"
    status_str = str(raw_status) if raw_status else "running"

    if status_str == "completed":
        return "finished"
    if status_str == "failed":
        return "blocked"
    if status_str == "waiting_for_user":
        return _MODE_MAP.get(mode_str, "plan")

    return _MODE_MAP.get(mode_str, "plan")


def _convert_tool_calls(raw_calls: list[dict]) -> list[dict]:
    result = []
    for call in raw_calls:
        if isinstance(call, dict):
            entry = {
                "id": call.get("id", ""),
                "name": call.get("name", ""),
                "arguments": call.get("arguments", {}),
                "result": call.get("result"),
                "error": call.get("error"),
            }
            args = entry.get("arguments")
            if isinstance(args, dict) and entry["name"] == "write_file" and "content" in args:
                args = dict(args)
                content = args.pop("content")
                args["content_length"] = len(content) if isinstance(content, str) else 0
                args["content_omitted"] = True
                entry["arguments"] = args
            result.append(entry)
    return result


def adapt_legacy_state(raw: dict[str, Any]) -> WorkflowStateEnvelope:
    mode = _map_mode(raw.get("mode"), raw.get("status"))

    iteration = int(raw.get("iteration", 0))
    max_iterations = int(raw.get("max_iterations", 50))
    mode_switches = int(raw.get("mode_switches", 0))
    max_mode_switches = int(raw.get("max_mode_switches", 6))

    is_test = bool(raw.get("is_test", False))
    prompt_modules_applied = list(raw.get("prompt_modules_applied", []))
    final_summary = str(raw.get("final_summary", ""))

    plan = PlanStateV2(
        plan_iterations=int(raw.get("plan_iterations", 0)),
        max_plan_iterations=int(raw.get("max_plan_iterations", 60)),
        plan_soft_limit=int(raw.get("plan_soft_limit", 30)),
        plan_hard_limit=int(raw.get("plan_hard_limit", 60)),
        model_call_count=int(raw.get("model_call_count", raw.get("plan_iterations", 0))),
        plan_session_id=raw.get("plan_session_id"),
        plan_stage=raw.get("plan_stage", "discover_direction"),
        selected_skill_id=raw.get("selected_skill_id"),
        implementation_outline=raw.get("implementation_outline"),
        clarification_questions=list(raw.get("clarification_questions", [])),
        plan_just_finished=bool(raw.get("plan_just_finished", False)),
    )

    execution = ExecutionStateV2(
        files_touched=list(raw.get("files_touched", [])),
        implement_phase_files=list(raw.get("implement_phase_files", [])),
        implement_replan_requested=bool(raw.get("implement_replan_requested", False)),
        implement_replan_reason=str(raw.get("implement_replan_reason", "")),
        implement_just_finished=bool(raw.get("implement_just_finished", False)),
    )

    validation = ValidationStateV2(
        validate_iterations=int(raw.get("validate_iterations", 0)),
        validation_failures=list(raw.get("validation_failures", [])),
        validation_check_results=raw.get("validation_check_results"),
        validation_status=raw.get("validation_status", "pending"),
        validate_just_finished=bool(raw.get("validate_just_finished", False)),
    )

    routing = RoutingStateV2(
        route_decided=bool(raw.get("route_decided", False)),
        route_decision=raw.get("route_decision"),
        route_iterations=int(raw.get("route_iterations", 0)),
        recommended_code_gen_type=raw.get("recommended_code_gen_type"),
    )

    conversation = ConversationStateV2(
        conversation_messages=list(raw.get("conversation_messages", [])),
    )

    artifact_type: ArtifactTypeState | None = None
    if raw.get("recommended_code_gen_type"):
        code_gen_type = raw.get("recommended_code_gen_type", "")
        artifact_type = ArtifactTypeState(
            requested=code_gen_type,
            effective=code_gen_type,
            recommended=raw.get("recommended_code_gen_type"),
        )

    resolved_model = raw.get("resolved_model")
    if isinstance(resolved_model, dict):
        resolved_model = {k: v for k, v in resolved_model.items() if k != "apiKey"}

    executed_tool_calls_raw = raw.get("executed_tool_calls", [])
    executed_tool_calls = _convert_tool_calls(executed_tool_calls_raw) if isinstance(executed_tool_calls_raw, list) else []

    migration_warnings: list[str] = []

    if not plan.implementation_outline and mode in ("implement", "validate"):
        migration_warnings.append(
            "[open_item: legacy_missing_implementation_outline] 旧状态缺少 implementation_outline，实现可能不完整"
        )

    if not plan.selected_skill_id and mode in ("implement", "validate"):
        migration_warnings.append(
            "[open_item: legacy_missing_selected_skill_id] 旧状态缺少 selected_skill_id"
        )

    workflow = WorkflowState(
        current_mode=mode,
        iteration=iteration,
        max_iterations=max_iterations,
        mode_switches=mode_switches,
        max_mode_switches=max_mode_switches,
        is_test=is_test,
        prompt_modules_applied=prompt_modules_applied,
        final_summary=final_summary,
        plan=plan,
        execution=execution,
        validation=validation,
        routing=routing,
        conversation=conversation,
        artifact_type=artifact_type,
        generation_mode="application",
        progress=ProgressStateV2(),
        phase_reports=[],
        resolved_model=resolved_model,
        executed_tool_calls=executed_tool_calls,
        migration_warnings=migration_warnings,
    )

    if migration_warnings:
        logger.info(
            "legacy_state_adapter | migration_warnings=%d",
            len(migration_warnings),
        )

    envelope = WorkflowStateEnvelope(schema_version=3, workflow=workflow)

    return envelope
