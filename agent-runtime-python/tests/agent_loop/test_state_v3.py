"""Phase 2: 状态 v3 编解码和 v2/legacy 迁移测试。"""

import json

import pytest

from app.agent_loop.execution_contract import (
    DirectImplementationBrief,
    ExecutionContract,
    from_direct_brief,
    from_implementation_plan,
    from_validation_repair,
)
from app.agent_loop.state_codec import decode_loop_state, encode_loop_state
from app.agent_loop.state_v2 import (
    ArtifactTypeState,
    ExecutionStateV2,
    WorkflowState,
    WorkflowStateEnvelope,
)
from app.core.exceptions import AgentRuntimeError


def _make_v2_envelope():
    return WorkflowStateEnvelope(
        schema_version=2,
        workflow=WorkflowState(
            current_mode="implement",
            iteration=5,
            artifact_type=ArtifactTypeState(
                requested="vue_project",
                effective="vue_project",
            ),
        ),
    )


class TestV2ToV3Migration:
    def test_v2_decode_migrates_to_v3(self):
        v2 = _make_v2_envelope()
        raw = v2.model_dump_json()
        result = decode_loop_state(raw)
        assert result.schema_version == 3
        assert result.workflow.generation_mode == "application"

    def test_v2_single_file_maps_to_application_web_single_file(self):
        v2 = WorkflowStateEnvelope(
            schema_version=2,
            workflow=WorkflowState(
                artifact_type=ArtifactTypeState(
                    requested="single_file",
                    effective="single_file",
                ),
            ),
        )
        raw = v2.model_dump_json()
        result = decode_loop_state(raw)
        assert result.schema_version == 3
        assert result.workflow.generation_mode == "application"

    def test_unknown_legacy_code_gen_type_fails(self):
        bad_v2 = {
            "schema_version": 2,
            "workflow": {
                "current_mode": "plan",
                "artifact_type": {
                    "requested": "unknown_type_xyz",
                    "effective": "unknown_type_xyz",
                },
            },
        }
        with pytest.raises(AgentRuntimeError):
            decode_loop_state(json.dumps(bad_v2))

    def test_v3_roundtrip_preserves_generation_mode(self):
        v3 = WorkflowStateEnvelope(
            schema_version=3,
            workflow=WorkflowState(
                current_mode="implement",
                generation_mode="application",
            ),
        )
        encoded = encode_loop_state(v3)
        data = json.loads(encoded)
        assert data["schema_version"] == 3
        assert data["workflow"]["generation_mode"] == "application"

    def test_resume_preserves_execution_contract_and_generation_mode(self):
        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="web_single_file",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
        )
        v3 = WorkflowStateEnvelope(
            schema_version=3,
            workflow=WorkflowState(
                current_mode="implement",
                generation_mode="application",
                execution=ExecutionStateV2(
                    execution_contract=contract.model_dump(),
                ),
            ),
        )
        encoded = encode_loop_state(v3)
        restored = decode_loop_state(encoded)
        assert restored.workflow.generation_mode == "application"
        assert restored.workflow.execution.execution_contract is not None
        assert restored.workflow.execution.execution_contract["source"] == "direct"

    def test_legacy_decode_sets_generation_mode_application(self):
        legacy = {
            "mode": "implement",
            "status": "running",
            "iteration": 3,
            "recommended_code_gen_type": "vue_project",
        }
        result = decode_loop_state(json.dumps(legacy))
        assert result.schema_version == 3
        assert result.workflow.generation_mode == "application"


class TestExecutionContractIntegration:
    def test_direct_brief_normalizes_to_single_task_contract(self):
        brief = DirectImplementationBrief(
            generation_mode="application",
            goal="修改标题",
            allowed_files=["index.html"],
            acceptance_criteria=["标题已修改"],
            verification_requirements=["页面可渲染"],
        )
        contract = from_direct_brief(brief, "web_single_file")
        assert contract.source == "direct"
        assert contract.generation_mode == "application"
        assert len(contract.tasks) == 1
        assert contract.tasks[0].task_id == "direct_task_001"

    def test_plan_normalizes_without_losing_prohibited_changes(self):
        from app.agent_loop.state_v2 import ImplementationPlan, ImplementationTask

        plan = ImplementationPlan(
            source_design_version=1,
            tasks=[
                ImplementationTask(
                    task_id="t1",
                    goal="创建页面",
                    allowed_files=["src/App.vue"],
                    acceptance_criteria=["页面存在"],
                )
            ],
            prohibited_changes=["package.json"],
        )
        contract = from_implementation_plan(plan, "application", "vue_project")
        assert contract.source == "plan"
        assert contract.prohibited_changes == ["package.json"]

    def test_validation_repair_requires_issue_ids(self):
        with pytest.raises(AgentRuntimeError, match="active_issue_ids"):
            from_validation_repair(
                generation_mode="application",
                expected_artifact_format="vue_project",
                active_issue_ids=[],
                goal="修复",
                allowed_files=["src/App.vue"],
            )

    def test_contract_rejects_format_outside_mode_definition(self):
        with pytest.raises(AgentRuntimeError, match="unresolved"):
            ExecutionContract(
                source="direct",
                generation_mode="unresolved",
                expected_artifact_format="web_single_file",
                goal="test",
                tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
            )


class TestV3RoundtripNoCodeGenTypeKeys:
    """Phase 2 Task 2-2: v3 序列化后不应包含 codeGenType / code_gen_type 键。"""

    def _collect_keys_recursive(self, obj, keys_out: set) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys_out.add(k)
                self._collect_keys_recursive(v, keys_out)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_keys_recursive(item, keys_out)

    def test_v3_roundtrip_has_no_code_gen_type_keys(self):
        contract = ExecutionContract(
            source="direct",
            generation_mode="application",
            expected_artifact_format="web_single_file",
            goal="test",
            tasks=[{"task_id": "t1", "goal": "g", "allowed_files": ["a.html"]}],
        )
        v3 = WorkflowStateEnvelope(
            schema_version=3,
            workflow=WorkflowState(
                current_mode="implement",
                generation_mode="application",
                execution=ExecutionStateV2(
                    execution_contract=contract.model_dump(),
                ),
            ),
        )
        encoded = encode_loop_state(v3)
        data = json.loads(encoded)

        all_keys: set[str] = set()
        self._collect_keys_recursive(data, all_keys)

        forbidden_patterns = ["code_gen_type", "CodeGenType", "codeGenType"]
        for key in all_keys:
            for pattern in forbidden_patterns:
                assert pattern not in key, (
                    f"v3 序列化结果包含禁止的键: {key} (匹配模式: {pattern})"
                )

        restored = decode_loop_state(encoded)
        assert restored.workflow.generation_mode == "application"
