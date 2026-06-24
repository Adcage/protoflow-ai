from app.agent_loop.legacy_state_adapter import adapt_legacy_state
from app.agent_loop.state_v2 import WorkflowStateEnvelope


class TestLegacyStateAdapter:
    def test_adapts_basic_running_state(self):
        raw = {
            "mode": "plan",
            "status": "running",
            "iteration": 2,
            "mode_switches": 0,
        }
        envelope = adapt_legacy_state(raw)
        assert isinstance(envelope, WorkflowStateEnvelope)
        assert envelope.schema_version == 3
        assert envelope.workflow.current_mode == "plan"
        assert envelope.workflow.iteration == 2

    def test_adapts_implement_mode(self):
        raw = {
            "mode": "implement",
            "status": "running",
            "iteration": 5,
            "files_touched": ["src/App.vue"],
            "implement_phase_files": ["src/App.vue"],
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "implement"
        assert envelope.workflow.execution.files_touched == ["src/App.vue"]

    def test_adapts_completed_status_to_finished(self):
        raw = {
            "mode": "finish",
            "status": "completed",
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "finished"

    def test_adapts_failed_status_to_blocked(self):
        raw = {
            "mode": "implement",
            "status": "failed",
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "blocked"

    def test_adapts_waiting_for_user_status(self):
        raw = {
            "mode": "plan",
            "status": "waiting_for_user",
            "clarification_questions": [{"id": "q1", "question": "颜色？"}],
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "plan"
        assert len(envelope.workflow.plan.clarification_questions) == 1

    def test_legacy_state_adapts_without_claiming_completion(self):
        raw = {
            "mode": "implement",
            "status": "running",
            "iteration": 3,
            "plan_iterations": 0,
            "implementation_outline": None,
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "implement"
        assert len(envelope.workflow.phase_reports) == 0
        assert envelope.workflow.plan.implementation_outline is None
        assert envelope.workflow.current_mode != "finished"
        assert len(envelope.workflow.migration_warnings) > 0
        assert any("implementation_outline" in w for w in envelope.workflow.migration_warnings)

    def test_adapts_with_missing_plan_does_not_claim_finished(self):
        raw = {
            "mode": "validate",
            "status": "running",
            "plan_iterations": 0,
            "implementation_outline": None,
            "selected_skill_id": None,
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "validate"
        assert len(envelope.workflow.phase_reports) == 0

    def test_adapts_route_state(self):
        raw = {
            "mode": "plan",
            "status": "running",
            "route_decided": True,
            "route_decision": {"mode": "implement", "reason": "低风险修改"},
            "route_iterations": 1,
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.routing.route_decided is True
        assert envelope.workflow.routing.route_decision == {"mode": "implement", "reason": "低风险修改"}

    def test_adapts_validation_state(self):
        raw = {
            "mode": "validate",
            "status": "running",
            "validate_iterations": 1,
            "validation_status": "pending",
            "validation_failures": [{"check": "build", "status": "fail"}],
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.current_mode == "validate"
        assert envelope.workflow.validation.validate_iterations == 1
        assert len(envelope.workflow.validation.validation_failures) == 1

    def test_adapts_resolved_model_strips_api_key(self):
        raw = {
            "mode": "plan",
            "status": "running",
            "resolved_model": {
                "provider": "openai",
                "modelName": "gpt-4",
                "apiKey": "sk-secret",
            },
        }
        envelope = adapt_legacy_state(raw)
        assert "apiKey" not in (envelope.workflow.resolved_model or {})

    def test_adapts_executed_tool_calls(self):
        raw = {
            "mode": "implement",
            "status": "running",
            "executed_tool_calls": [
                {
                    "id": "t1",
                    "name": "write_file",
                    "arguments": {"relative_path": "src/App.vue", "content": "x" * 1000},
                    "result": "写入成功",
                },
                {
                    "id": "t2",
                    "name": "read_file",
                    "arguments": {"relative_path": "src/App.vue"},
                    "result": "文件内容",
                },
            ],
        }
        envelope = adapt_legacy_state(raw)
        calls = envelope.workflow.executed_tool_calls
        assert len(calls) == 2
        write_args = calls[0]["arguments"]
        assert "content" not in write_args
        assert write_args.get("content_length") == 1000

    def test_adapts_recommended_code_gen_type_to_artifact_type(self):
        raw = {
            "mode": "plan",
            "status": "running",
            "recommended_code_gen_type": "vue_project",
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.artifact_type is not None
        assert envelope.workflow.artifact_type.effective == "vue_project"

    def test_adapts_empty_state(self):
        raw = {}
        envelope = adapt_legacy_state(raw)
        assert envelope.schema_version == 3
        assert envelope.workflow.iteration == 0

    def test_adapts_preserves_plan_state(self):
        raw = {
            "mode": "plan",
            "status": "running",
            "plan_iterations": 3,
            "selected_skill_id": "ui-ux-pro-max",
            "implementation_outline": {"text": "test plan"},
            "plan_just_finished": True,
        }
        envelope = adapt_legacy_state(raw)
        assert envelope.workflow.plan.plan_iterations == 3
        assert envelope.workflow.plan.selected_skill_id == "ui-ux-pro-max"
        assert envelope.workflow.plan.implementation_outline == {"text": "test plan"}
        assert envelope.workflow.plan.plan_just_finished is True
