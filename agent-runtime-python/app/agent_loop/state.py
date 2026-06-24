import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from app.agent_loop.state_v2 import (
    ConversationStateV2,
    ExecutionStateV2,
    PlanStateV2,
    RoutingStateV2,
    ValidationStateV2,
    WorkflowState,
    WorkflowStateEnvelope,
)
from app.agent_loop.state_codec import decode_loop_state, encode_loop_state
from app.runtime.state import ToolCallRecord
from app.agent_loop.tool_history import compact_tool_records
from app.core.config import settings
from app.core.exceptions import AgentRuntimeError

logger = logging.getLogger("app.agent_loop.state")

_PERSIST_FIELDS = (
    "mode", "status", "iteration", "mode_switches",
    "selected_skill_id", "implementation_outline", "clarification_questions",
    "files_touched", "implement_phase_files",
    "implement_replan_requested", "implement_replan_reason",
    "executed_tool_calls", "conversation_messages",
    "resolved_model", "plan_iterations",
    # 前置路由
    "route_decided", "route_decision", "route_iterations",
    "recommended_code_gen_type",
    # 校验循环
    "validate_iterations", "validation_failures", "validation_check_results",
    "validation_status", "implement_just_finished", "validate_just_finished",
    "plan_just_finished",
    "validation_issues", "validation_report_id",
    "validation_coverage_gaps", "validation_recommended_transition",
    # 测试模式
    "is_test",
    # 提示词追踪
    "prompt_modules_applied",
    # AI 完成总结
    "final_summary",
    # Phase 4: 执行状态
    "execution_state",
)


@dataclass
class AgentLoopState:
    mode: Literal["plan", "implement", "validate", "finish"] = "plan"
    status: Literal["running", "completed", "failed", "waiting_for_user"] = "running"

    iteration: int = 0
    max_iterations: int = 50
    mode_switches: int = 0
    max_mode_switches: int = 6

    selected_capabilities: Any | None = None
    implementation_outline: dict | None = None
    clarification_questions: list[dict] = field(default_factory=list)

    files_touched: list[str] = field(default_factory=list)
    implement_phase_files: list[str] = field(default_factory=list)
    implement_replan_requested: bool = False
    implement_replan_reason: str = ""
    executed_tool_calls: list[ToolCallRecord] = field(default_factory=list)
    model_response_text: str = ""

    resolved_model: dict[str, Any] | None = None

    conversation_messages: list[dict] = field(default_factory=list)
    skill_context: dict | None = None

    _asset_index: Any = None
    selected_skill_id: str | None = None
    plan_iterations: int = 0
    max_plan_iterations: int = 15

    # 前置路由
    route_decided: bool = False
    route_decision: dict | None = None   # {"mode": "plan", "code_gen_type": "", "reason": ""}
    route_iterations: int = 0
    recommended_code_gen_type: str | None = None

    # 校验循环
    validate_iterations: int = 0
    max_validate_iterations: int = 3
    validation_failures: list[dict] = field(default_factory=list)
    validation_check_results: list[dict] | None = None
    validation_status: Literal["pending", "passed", "failed"] = "pending"
    validation_issues: list[dict] = field(default_factory=list)
    validation_report_id: str | None = None
    validation_coverage_gaps: list[str] = field(default_factory=list)
    validation_recommended_transition: str | None = None

    # 阶段标记（用于 route_step 提示词模块判断）
    plan_just_finished: bool = False
    implement_just_finished: bool = False
    validate_just_finished: bool = False

    # 测试模式
    is_test: bool = False

    # 提示词追踪
    prompt_modules_applied: list[str] = field(default_factory=list)

    # AI 完成总结（由 finish 工具写入，finish 节点在 DONE 事件中发出）
    final_summary: str = ""

    # Phase 2: v2 状态信封和产物类型
    _state_envelope: Any = None
    _state_changed: bool = False
    artifact_type_state: Any | None = None

    # Phase 4: 执行状态
    execution_state: Any | None = None

    def record_state_change(self) -> None:
        self._state_changed = True

    def record_phase_report(self) -> None:
        from app.agent_loop.phase_report import PhaseCompletionReport

        envelope = getattr(self, "_state_envelope", None)
        if envelope is None:
            env = self._to_envelope()
            self._state_envelope = env
            envelope = env

        source_mode = self.mode if self.mode != "finish" else "plan"
        if source_mode not in ("plan", "implement", "validate"):
            return

        report = PhaseCompletionReport.make_report(
            source_mode=source_mode,
            status="completed",
            summary=f"{source_mode} 阶段完成 (iteration={self.iteration})",
            evidence_refs=list(self.files_touched) or [],
            open_items=[],
            recommended_transition=None,
            state_revision=envelope.workflow.revision,
        )
        envelope.workflow.phase_reports.append(report)
        self._state_envelope = envelope

    def serialize(self) -> str:
        envelope = self._to_envelope()
        return encode_loop_state(envelope)

    def _to_envelope(self) -> WorkflowStateEnvelope:
        existing_envelope = getattr(self, "_state_envelope", None)
        existing_workflow = existing_envelope.workflow if existing_envelope is not None else None
        existing_revision = existing_workflow.revision if existing_workflow is not None else 0
        existing_reports = existing_workflow.phase_reports if existing_workflow is not None else []
        existing_artifact_type = existing_workflow.artifact_type if existing_workflow is not None else None

        if existing_envelope is not None:
            existing_envelope.next_revision()
            existing_revision = existing_envelope.workflow.revision

        tool_calls_data = []
        for record in compact_tool_records(
            self.executed_tool_calls,
            max_total_chars=settings.agent_tool_history_max_chars,
            max_result_chars=settings.agent_tool_result_max_chars,
        ):
            tool_calls_data.append({
                "id": record.id,
                "name": record.name,
                "arguments": record.arguments,
                "result": record.result,
                "error": record.error,
            })

        resolved_model = self.resolved_model
        if isinstance(resolved_model, dict):
            resolved_model = {k: v for k, v in resolved_model.items() if k != "apiKey"}

        artifact_type = self.artifact_type_state
        if artifact_type is None and existing_artifact_type is not None:
            artifact_type = existing_artifact_type

        plan_state = existing_workflow.plan if existing_workflow is not None else self._build_plan_state()
        if existing_workflow is not None:
            plan_state = PlanStateV2(
                plan_iterations=self.plan_iterations,
                max_plan_iterations=existing_workflow.plan.max_plan_iterations,
                plan_soft_limit=existing_workflow.plan.plan_soft_limit,
                plan_hard_limit=existing_workflow.plan.plan_hard_limit,
                model_call_count=existing_workflow.plan.model_call_count,
                plan_session_id=existing_workflow.plan.plan_session_id,
                plan_stage=existing_workflow.plan.plan_stage,
                previous_plan_stage=existing_workflow.plan.previous_plan_stage,
                capability_bundle=existing_workflow.plan.capability_bundle,
                requirement_brief=existing_workflow.plan.requirement_brief,
                design_specification=existing_workflow.plan.design_specification,
                implementation_plan=existing_workflow.plan.implementation_plan,
                selected_skill_id=self.selected_skill_id,
                implementation_outline=self.implementation_outline,
                clarification_questions=list(self.clarification_questions),
                plan_just_finished=self.plan_just_finished,
                is_waiting_for_user=self.status == "waiting_for_user",
                project_inspection=existing_workflow.plan.project_inspection,
                skill_context_changed=existing_workflow.plan.skill_context_changed,
                pending_question_set_id=existing_workflow.plan.pending_question_set_id,
                design_spec_revision=existing_workflow.plan.design_spec_revision,
                implementation_plan_revision=existing_workflow.plan.implementation_plan_revision,
            )

        workflow = WorkflowState(
            current_mode=self._map_mode_for_v2(),
            revision=existing_revision,
            iteration=self.iteration,
            max_iterations=self.max_iterations,
            mode_switches=self.mode_switches,
            max_mode_switches=self.max_mode_switches,
            is_test=self.is_test,
            prompt_modules_applied=self.prompt_modules_applied,
            final_summary=self.final_summary,
            plan=plan_state,
            execution=self._build_execution_state(),
            validation=self._build_validation_state(),
            routing=self._build_routing_state(),
            conversation=self._build_conversation_state(),
            artifact_type=artifact_type,
            phase_reports=list(existing_reports),
            resolved_model=resolved_model,
            executed_tool_calls=tool_calls_data,
        )
        return WorkflowStateEnvelope(workflow=workflow)

    def _map_mode_for_v2(self) -> str:
        if self.mode == "finish":
            return "finished"
        if self.status == "completed":
            return "finished"
        if self.status == "failed":
            return "blocked"
        if self.status == "waiting_for_user":
            return self.mode if self.mode != "finish" else "plan"
        return self.mode

    def _build_plan_state(self):
        from app.agent_loop.state_v2 import PlanStateV2
        return PlanStateV2(
            plan_iterations=self.plan_iterations,
            selected_skill_id=self.selected_skill_id,
            implementation_outline=self.implementation_outline,
            clarification_questions=self.clarification_questions,
            plan_just_finished=self.plan_just_finished,
            is_waiting_for_user=self.status == "waiting_for_user",
        )

    def _build_execution_state(self):
        from app.agent_loop.execution_state import ExecutionState

        exec_state = self.execution_state
        if exec_state is not None and isinstance(exec_state, ExecutionState):
            budget = exec_state.call_budget
            return ExecutionStateV2(
                files_touched=list(self.files_touched),
                implement_phase_files=list(self.implement_phase_files),
                implement_replan_requested=self.implement_replan_requested,
                implement_replan_reason=self.implement_replan_reason,
                implement_just_finished=self.implement_just_finished,
                execution_run_kind=exec_state.run_kind,
                source_plan_version=exec_state.source_plan_version,
                active_task_id=exec_state.active_task_id,
                execution_tasks=[t.model_dump() for t in exec_state.tasks],
                active_issue_ids=list(exec_state.active_issue_ids),
                call_budget_soft_limit=budget.soft_limit if budget else 0,
                call_budget_hard_limit=budget.hard_limit if budget else 0,
                call_budget_model_call_count=budget.model_call_count if budget else 0,
                completion_candidate=exec_state.completion_candidate,
            )
        return ExecutionStateV2(
            files_touched=list(self.files_touched),
            implement_phase_files=list(self.implement_phase_files),
            implement_replan_requested=self.implement_replan_requested,
            implement_replan_reason=self.implement_replan_reason,
            implement_just_finished=self.implement_just_finished,
        )

    def _build_validation_state(self):
        return ValidationStateV2(
            validate_iterations=self.validate_iterations,
            validation_failures=list(self.validation_failures),
            validation_check_results=self.validation_check_results,
            validation_status=self.validation_status,
            validate_just_finished=self.validate_just_finished,
            validation_issues=getattr(self, "validation_issues", []),
            validation_report_id=getattr(self, "validation_report_id", None),
            validation_coverage_gaps=getattr(self, "validation_coverage_gaps", []),
            validation_recommended_transition=getattr(self, "validation_recommended_transition", None),
        )

    def _build_routing_state(self):
        return RoutingStateV2(
            route_decided=self.route_decided,
            route_decision=self.route_decision,
            route_iterations=self.route_iterations,
            recommended_code_gen_type=self.recommended_code_gen_type,
        )

    def _build_conversation_state(self):
        return ConversationStateV2(
            conversation_messages=list(self.conversation_messages),
        )

    @classmethod
    def from_graph_result(
        cls,
        result: "AgentLoopState | dict[str, Any]",
    ) -> "AgentLoopState":
        if isinstance(result, cls):
            return result
        if not isinstance(result, dict):
            raise TypeError(f"Unsupported graph result type: {type(result).__name__}")

        state = cls()
        for key, value in result.items():
            if not hasattr(state, key):
                continue
            if key == "executed_tool_calls":
                value = [
                    record
                    if isinstance(record, ToolCallRecord)
                    else ToolCallRecord(
                        id=record["id"],
                        name=record["name"],
                        arguments=record.get("arguments", {}),
                        result=record.get("result"),
                        error=record.get("error"),
                    )
                    for record in value
                ]
            setattr(state, key, value)
        return state

    @classmethod
    def deserialize(cls, json_str: str) -> "AgentLoopState":
        try:
            envelope = decode_loop_state(json_str)
            state = cls._from_envelope(envelope)
            state._state_envelope = envelope
            return state
        except AgentRuntimeError:
            if json_str and "schema_version" not in json.loads(json_str):
                return cls._legacy_deserialize(json_str)
            raise

    @classmethod
    def _from_envelope(cls, envelope: WorkflowStateEnvelope) -> "AgentLoopState":
        wf = envelope.workflow
        state = cls()

        mode_map_v2_to_legacy = {
            "plan": "plan",
            "implement": "implement",
            "validate": "validate",
            "route": "plan",
            "finished": "finish",
            "blocked": "finish",
        }
        state.mode = mode_map_v2_to_legacy.get(wf.current_mode, "plan")

        if wf.current_mode == "finished":
            state.status = "completed"
        elif wf.current_mode == "blocked":
            state.status = "failed"
        elif wf.plan.is_waiting_for_user:
            state.status = "waiting_for_user"
        else:
            has_pending_question = False
            for q in wf.plan.clarification_questions:
                if not q.get("answered", False):
                    has_pending_question = True
                    break
            if has_pending_question:
                state.status = "waiting_for_user"
            else:
                state.status = "running"

        state.iteration = wf.iteration
        state.max_iterations = wf.max_iterations
        state.mode_switches = wf.mode_switches
        state.max_mode_switches = wf.max_mode_switches
        state.is_test = wf.is_test
        state.prompt_modules_applied = list(wf.prompt_modules_applied)
        state.final_summary = wf.final_summary

        plan = wf.plan
        state.plan_iterations = plan.plan_iterations
        state.selected_skill_id = plan.selected_skill_id
        state.implementation_outline = plan.implementation_outline
        state.clarification_questions = list(plan.clarification_questions)
        state.plan_just_finished = plan.plan_just_finished

        execution = wf.execution
        state.files_touched = list(execution.files_touched)
        state.implement_phase_files = list(execution.implement_phase_files)
        state.implement_replan_requested = execution.implement_replan_requested
        state.implement_replan_reason = execution.implement_replan_reason
        state.implement_just_finished = execution.implement_just_finished

        from app.agent_loop.execution_state import (
            CallBudget,
            ExecutionState,
            ExecutionTaskState,
        )

        exec_tasks = []
        for td in execution.execution_tasks:
            if isinstance(td, dict):
                exec_tasks.append(ExecutionTaskState(**td))
            elif isinstance(td, ExecutionTaskState):
                exec_tasks.append(td)
        call_budget = None
        if execution.call_budget_soft_limit > 0 or execution.call_budget_hard_limit > 0:
            call_budget = CallBudget(
                soft_limit=execution.call_budget_soft_limit,
                hard_limit=execution.call_budget_hard_limit,
                model_call_count=execution.call_budget_model_call_count,
            )
        state.execution_state = ExecutionState(
            run_kind=execution.execution_run_kind if execution.execution_run_kind in ("initial", "user_modification", "validation_repair") else "initial",
            source_plan_version=execution.source_plan_version,
            active_task_id=execution.active_task_id,
            tasks=exec_tasks,
            active_issue_ids=list(execution.active_issue_ids),
            call_budget=call_budget,
            completion_candidate=execution.completion_candidate,
        )

        validation = wf.validation
        state.validate_iterations = validation.validate_iterations
        state.validation_failures = list(validation.validation_failures)
        state.validation_check_results = validation.validation_check_results
        state.validation_status = validation.validation_status
        state.validate_just_finished = validation.validate_just_finished
        state.validation_issues = list(validation.validation_issues)
        state.validation_report_id = validation.validation_report_id
        state.validation_coverage_gaps = list(validation.validation_coverage_gaps)
        state.validation_recommended_transition = validation.validation_recommended_transition

        routing = wf.routing
        state.route_decided = routing.route_decided
        state.route_decision = routing.route_decision
        state.route_iterations = routing.route_iterations
        state.recommended_code_gen_type = routing.recommended_code_gen_type

        state.conversation_messages = list(wf.conversation.conversation_messages)

        state.resolved_model = wf.resolved_model

        executed = wf.executed_tool_calls
        state.executed_tool_calls = []
        for r in executed:
            if isinstance(r, dict):
                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=r.get("id", ""),
                        name=r.get("name", ""),
                        arguments=r.get("arguments", {}),
                        result=r.get("result"),
                        error=r.get("error"),
                    )
                )

        if wf.artifact_type is not None:
            state.artifact_type_state = wf.artifact_type

        return state

    @classmethod
    def _legacy_deserialize(cls, json_str: str) -> "AgentLoopState":
        data = json.loads(json_str)
        executed = data.pop("executed_tool_calls", [])
        data["executed_tool_calls"] = [
            ToolCallRecord(
                id=r["id"], name=r["name"],
                arguments=r["arguments"], result=r.get("result"), error=r.get("error"),
            )
            for r in executed
        ]
        state = cls()
        for key, val in data.items():
            if hasattr(state, key):
                setattr(state, key, val)
        return state
