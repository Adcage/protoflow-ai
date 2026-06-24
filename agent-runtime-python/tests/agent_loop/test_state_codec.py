import json

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.state_v2 import (
    ArtifactTypeState,
    ExecutionStateV2,
    PlanStateV2,
    RoutingStateV2,
    ValidationStateV2,
    WorkflowState,
    WorkflowStateEnvelope,
)
from app.agent_loop.state_codec import decode_loop_state, encode_loop_state
from app.core.exceptions import AgentRuntimeError


class TestDecodeLoopState:
    def test_decode_empty_creates_default_state(self):
        envelope = decode_loop_state(None)
        assert envelope.schema_version == 3
        assert envelope.workflow.current_mode == "route"

    def test_decode_empty_string_creates_default_state(self):
        envelope = decode_loop_state("")
        assert envelope.schema_version == 3

    def test_decode_unknown_version_blocks(self):
        with pytest.raises(AgentRuntimeError):
            decode_loop_state(json.dumps({"schema_version": 999}))

    def test_decode_v2_state_migrates_to_v3(self):
        envelope = WorkflowStateEnvelope(
            schema_version=2,
            workflow=WorkflowState(current_mode="implement", iteration=5)
        )
        raw = envelope.model_dump_json()
        restored = decode_loop_state(raw)
        assert restored.schema_version == 3
        assert restored.workflow.current_mode == "implement"
        assert restored.workflow.iteration == 5

    def test_decode_legacy_state_without_schema_version(self):
        legacy = {
            "mode": "implement",
            "status": "running",
            "iteration": 3,
            "mode_switches": 1,
            "files_touched": ["src/App.vue"],
            "plan_iterations": 2,
        }
        envelope = decode_loop_state(json.dumps(legacy))
        assert envelope.schema_version == 3
        assert envelope.workflow.current_mode == "implement"

    def test_decode_invalid_json_blocks(self):
        with pytest.raises(AgentRuntimeError):
            decode_loop_state("not valid json{{{")


class TestEncodeLoopState:
    def test_encode_strips_api_key(self):
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(
                resolved_model={"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-secret-key"}
            )
        )
        encoded = encode_loop_state(envelope)
        data = json.loads(encoded)
        assert "apiKey" not in data["workflow"]["resolved_model"]

    def test_encode_stores_skill_refs_not_content(self):
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(
                plan=PlanStateV2(
                    selected_skill_id="ui-ux-pro-max",
                    implementation_outline={"skill_source_path": "skills/ui-ux-pro-max/SKILL.md"},
                )
            )
        )
        encoded = encode_loop_state(envelope)
        data = json.loads(encoded)
        plan = data["workflow"]["plan"]
        assert plan["selected_skill_id"] == "ui-ux-pro-max"
        assert plan["implementation_outline"].get("skill_source_path") == "skills/ui-ux-pro-max/SKILL.md"

    def test_encode_preserves_write_file_content(self):
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(
                executed_tool_calls=[
                    {
                        "id": "t1",
                        "name": "write_file",
                        "arguments": {
                            "relative_path": "src/App.vue",
                            "content": "x" * 5000,
                        },
                        "result": "写入成功",
                    }
                ]
            )
        )
        encoded = encode_loop_state(envelope)
        data = json.loads(encoded)
        args = data["workflow"]["executed_tool_calls"][0]["arguments"]
        assert "content" in args
        assert len(args["content"]) == 5000

    def test_round_trip_v2_state(self):
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(
                current_mode="implement",
                iteration=10,
                mode_switches=2,
                is_test=True,
                plan=PlanStateV2(
                    plan_iterations=3,
                    selected_skill_id="ui-ux-pro-max",
                ),
                execution=ExecutionStateV2(
                    files_touched=["src/App.vue", "src/main.ts"],
                    implement_phase_files=["src/App.vue"],
                ),
                validation=ValidationStateV2(
                    validate_iterations=1,
                    validation_status="pending",
                ),
                routing=RoutingStateV2(
                    route_decided=True,
                    route_decision={"mode": "implement", "reason": "test"},
                ),
                artifact_type=ArtifactTypeState(
                    requested="vue_project",
                    effective="vue_project",
                ),
            )
        )
        encoded = encode_loop_state(envelope)
        restored = decode_loop_state(encoded)

        assert restored.schema_version == 3
        assert restored.workflow.current_mode == "implement"
        assert restored.workflow.iteration == 10
        assert restored.workflow.plan.selected_skill_id == "ui-ux-pro-max"
        assert restored.workflow.execution.files_touched == ["src/App.vue", "src/main.ts"]
        assert restored.workflow.routing.route_decided is True
        assert restored.workflow.artifact_type is not None
        assert restored.workflow.artifact_type.effective == "vue_project"


class TestSanitizePersistedState:
    def test_nested_sensitive_key_is_removed(self):
        envelope = WorkflowStateEnvelope(
            workflow=WorkflowState(
                resolved_model={
                    "provider": "openai",
                    "apiKey": "sk-top-secret",
                    "nested": {"token": "bearer-xyz"},
                }
            )
        )
        encoded = encode_loop_state(envelope)
        data = json.loads(encoded)
        assert "apiKey" not in data["workflow"]["resolved_model"]
        assert "token" not in data["workflow"]["resolved_model"]["nested"]
        assert data["workflow"]["resolved_model"]["provider"] == "openai"


class TestResumeRefetchesIncompleteModelConfig:
    def test_model_config_incomplete_without_api_key(self):
        from app.agent_loop.nodes.init import _model_config_incomplete

        assert _model_config_incomplete(None) is True
        assert _model_config_incomplete({}) is True
        assert _model_config_incomplete({"provider": "openai", "modelName": "gpt-4"}) is True
        assert _model_config_incomplete({"provider": "openai", "modelName": "gpt-4", "apiKey": ""}) is True

    def test_model_config_complete_with_api_key(self):
        from app.agent_loop.nodes.init import _model_config_incomplete

        assert _model_config_incomplete({"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-valid"}) is False

    def test_v2_deserialize_strips_api_key_so_init_will_refetch(self):
        state = AgentLoopState()
        state.resolved_model = {"provider": "openai", "modelName": "gpt-4", "apiKey": "sk-secret"}
        json_str = state.serialize()
        restored = AgentLoopState.deserialize(json_str)
        assert "apiKey" not in (restored.resolved_model or {})
        from app.agent_loop.nodes.init import _model_config_incomplete

        assert _model_config_incomplete(restored.resolved_model) is True
