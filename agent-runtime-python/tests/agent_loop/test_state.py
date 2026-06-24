import json

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import (
    ArtifactTypeState,
    PlanStateV2,
    ExecutionStateV2,
    RoutingStateV2,
    ValidationStateV2,
    WorkflowState,
)
from app.agent_loop.phase_report import PhaseCompletionReport, OpenItem
from app.core.exceptions import AgentRuntimeError
from app.runtime.state import ToolCallRecord


class TestAgentLoopState:
    def test_default_state(self):
        state = AgentLoopState()
        assert state.mode == "plan"
        assert state.status == "running"
        assert state.iteration == 0
        assert state.max_iterations == 50
        assert state.mode_switches == 0
        assert state.max_mode_switches == 6
        assert state.selected_capabilities is None
        assert state.implementation_outline is None
        assert state.clarification_questions == []

    def test_mode_transition(self):
        state = AgentLoopState()
        state.mode = "implement"
        state.mode_switches += 1
        assert state.mode == "implement"
        assert state.mode_switches == 1

    def test_completed_status(self):
        state = AgentLoopState(status="completed")
        assert state.status == "completed"

    def test_max_iterations_exceeded(self):
        state = AgentLoopState(iteration=51, max_iterations=50)
        assert state.iteration >= state.max_iterations

    def test_waiting_for_user_status(self):
        state = AgentLoopState(status="waiting_for_user")
        assert state.status == "waiting_for_user"


class TestAgentLoopStateSerialization:
    def test_from_graph_result_uses_returned_waiting_state(self):
        entry_state = AgentLoopState(status="running", iteration=1)
        graph_result = {
            **entry_state.__dict__,
            "status": "waiting_for_user",
            "iteration": 4,
            "clarification_questions": [{"id": "q1", "question": "页面类型？"}],
        }

        final_state = AgentLoopState.from_graph_result(graph_result)

        assert final_state is not entry_state
        assert final_state.status == "waiting_for_user"
        assert final_state.iteration == 4
        assert final_state.clarification_questions[0]["id"] == "q1"

    def test_from_graph_result_keeps_state_instance(self):
        state = AgentLoopState(status="completed", iteration=3)

        assert AgentLoopState.from_graph_result(state) is state

    def test_serialize_deserialize_roundtrip(self):
        state = AgentLoopState()
        state.mode = "implement"
        state.iteration = 5
        state.mode_switches = 2
        state.selected_skill_id = "ui-ux-pro-max"
        state.implementation_outline = {"text": "test plan"}
        state.clarification_questions = [{"id": "q1", "question": "颜色？"}]
        state.files_touched = ["src/App.vue", "src/main.ts"]
        state.implement_phase_files = ["src/App.vue"]
        state.implement_replan_requested = True
        state.implement_replan_reason = "计划缺少路由方案"
        state.executed_tool_calls = [
            ToolCallRecord(id="t1", name="read_file", arguments={"relative_path": "src/App.vue"}, result="file content"),
            ToolCallRecord(id="t2", name="ask_user", arguments={"question": "颜色？"}, result="已向用户提问"),
        ]
        state.conversation_messages = [{"role": "user", "content": "做一个仪表盘"}]
        state.resolved_model = {"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-secret"}
        state.plan_iterations = 3

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored.mode == "implement"
        assert restored.iteration == 5
        assert restored.mode_switches == 2
        assert restored.selected_skill_id == "ui-ux-pro-max"
        assert restored.implementation_outline == {"text": "test plan"}
        assert len(restored.clarification_questions) == 1
        assert restored.files_touched == ["src/App.vue", "src/main.ts"]
        assert restored.implement_phase_files == ["src/App.vue"]
        assert restored.implement_replan_requested is True
        assert restored.implement_replan_reason == "计划缺少路由方案"
        assert len(restored.executed_tool_calls) == 2
        assert restored.executed_tool_calls[0].name == "read_file"
        assert restored.executed_tool_calls[1].name == "ask_user"
        assert len(restored.conversation_messages) == 1
        assert restored.resolved_model["provider"] == "openai"
        assert "apiKey" not in restored.resolved_model
        assert restored.plan_iterations == 3

    def test_serialize_waiting_for_user(self):
        state = AgentLoopState()
        state.status = "waiting_for_user"
        state.clarification_questions = [{"id": "q1", "question": "颜色？"}]
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert restored.status == "waiting_for_user"

    def test_deserialize_empty_fields(self):
        state = AgentLoopState()
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert restored.mode == "plan"
        assert restored.iteration == 0
        assert restored.files_touched == []
        assert restored.executed_tool_calls == []

    def test_serialize_strips_api_key(self):
        state = AgentLoopState()
        state.resolved_model = {"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-super-secret"}
        json_str = state.serialize()
        data = json.loads(json_str)
        wf = data["workflow"]
        assert "apiKey" not in wf.get("resolved_model", {})

    def test_serialize_compacts_write_file_content(self):
        state = AgentLoopState()
        state.executed_tool_calls = [
            ToolCallRecord(
                id="w1",
                name="write_file",
                arguments={"relative_path": "src/App.vue", "content": "x" * 20_000},
                result="文件写入成功",
            )
        ]

        data = json.loads(state.serialize())

        calls = data["workflow"]["executed_tool_calls"]
        arguments = calls[0]["arguments"]
        assert "content" not in arguments
        assert arguments["content_length"] == 20_000


class TestWorkflowStateV2FieldOwnership:
    def test_plan_state_has_plan_fields(self):
        plan = PlanStateV2(plan_iterations=3, selected_skill_id="ui-ux-pro-max")
        assert plan.plan_iterations == 3
        assert plan.selected_skill_id == "ui-ux-pro-max"

    def test_execution_state_has_execution_fields(self):
        execution = ExecutionStateV2(
            files_touched=["src/App.vue"],
            implement_phase_files=["src/App.vue"],
        )
        assert execution.files_touched == ["src/App.vue"]

    def test_validation_state_has_validation_fields(self):
        validation = ValidationStateV2(
            validate_iterations=1,
            validation_status="pending",
        )
        assert validation.validate_iterations == 1

    def test_routing_state_has_routing_fields(self):
        routing = RoutingStateV2(
            route_decided=True,
            route_decision={"mode": "implement"},
        )
        assert routing.route_decided is True

    def test_state_defaults_are_deterministic(self):
        wf1 = WorkflowState()
        wf2 = WorkflowState()
        assert wf1.current_mode == wf2.current_mode
        assert wf1.iteration == wf2.iteration
        assert wf1.plan.plan_iterations == wf2.plan.plan_iterations

    def test_submit_phase_report_revision_must_match_state(self):
        wf = WorkflowState()
        report = PhaseCompletionReport.make_report(
            source_mode="plan",
            status="completed",
            summary="计划完成",
            state_revision=999,
        )
        with pytest.raises(AgentRuntimeError):
            wf.submit_phase_report(report)

    def test_submit_phase_report_with_matching_revision(self):
        wf = WorkflowState(current_mode="plan")
        wf.next_revision()
        report = PhaseCompletionReport.make_report(
            source_mode="plan",
            status="completed",
            summary="计划完成",
            state_revision=1,
        )
        wf.submit_phase_report(report)
        assert len(wf.phase_reports) == 1

    def test_mode_cannot_write_foreign_partition(self):
        wf = WorkflowState(current_mode="implement")
        wf.next_revision()
        plan_report = PhaseCompletionReport.make_report(
            source_mode="plan",
            status="completed",
            summary="计划完成",
            state_revision=wf.revision,
        )
        with pytest.raises(AgentRuntimeError):
            wf.submit_phase_report(plan_report)

    def test_summary_cannot_hide_open_items(self):
        with pytest.raises(AgentRuntimeError):
            PhaseCompletionReport.make_report(
                source_mode="implement",
                status="completed",
                summary="声称完成",
                open_items=[
                    OpenItem(item_id="oi1", description="关键 bug 未修", blocking=True),
                ],
            )


class TestArtifactTypeState:
    def test_effective_defaults_to_requested(self):
        ats = ArtifactTypeState(requested="vue_project", effective="")
        assert ats.effective == "vue_project"

    def test_requested_and_effective_match_by_default(self):
        ats = ArtifactTypeState(requested="vue_project", effective="vue_project")
        assert ats.requested == ats.effective

    def test_recommended_does_not_override_effective(self):
        ats = ArtifactTypeState(
            requested="multi-file",
            effective="multi-file",
            recommended="single_file",
        )
        assert ats.effective == "multi-file"

    def test_requested_type_is_immutable(self):
        ats = ArtifactTypeState(requested="vue_project", effective="vue_project")
        with pytest.raises(Exception):
            ats.requested = "single_file"


class TestWorkflowStateEnvelopeSerializeV2:
    def test_serialize_deserialize_via_envelope(self):
        state = AgentLoopState()
        state.mode = "implement"
        state.iteration = 5
        state.mode_switches = 2
        state.selected_skill_id = "ui-ux-pro-max"
        state.implementation_outline = {"text": "test plan"}
        state.files_touched = ["src/App.vue"]
        state.implement_phase_files = ["src/App.vue"]
        state.executed_tool_calls = [
            ToolCallRecord(id="t1", name="read_file", arguments={"relative_path": "src/App.vue"}, result="content"),
        ]
        state.conversation_messages = [{"role": "user", "content": "做一个仪表盘"}]
        state.resolved_model = {"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-secret"}
        state.plan_iterations = 3

        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)

        assert restored.mode == "implement"
        assert restored.iteration == 5
        assert restored.selected_skill_id == "ui-ux-pro-max"
        assert restored.files_touched == ["src/App.vue"]
        assert restored.resolved_model.get("provider") == "openai"
        assert "apiKey" not in (restored.resolved_model or {})
        assert restored.plan_iterations == 3
