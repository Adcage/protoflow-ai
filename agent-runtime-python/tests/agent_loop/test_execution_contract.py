"""ExecutionContract 测试。

Phase 2 Task 2-1: 验证三类来源产生相同合同结构，
DirectImplementationBrief 字段校验，ExecutionContract 边界约束。
"""

import pytest

from app.agent_loop.execution_contract import (
    ContractTask,
    DirectImplementationBrief,
    ExecutionContract,
    from_direct_brief,
    from_implementation_plan,
    from_validation_repair,
)
from app.agent_loop.state_v2 import ImplementationPlan, ImplementationTask
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


def _valid_brief(**overrides) -> DirectImplementationBrief:
    defaults = dict(
        generation_mode="application",
        goal="Fix button color",
        allowed_files=["src/App.vue"],
        acceptance_criteria=["Button is blue"],
        verification_requirements=["Visual check passes"],
    )
    defaults.update(overrides)
    return DirectImplementationBrief(**defaults)


def _valid_contract(**overrides) -> ExecutionContract:
    defaults = dict(
        source="direct",
        generation_mode="application",
        expected_artifact_format="vue_project",
        goal="Fix button color",
        tasks=[ContractTask(task_id="t1", goal="Fix button", allowed_files=["src/App.vue"])],
    )
    defaults.update(overrides)
    return ExecutionContract(**defaults)


class TestDirectImplementationBriefRequiresExactAllowedFiles:
    def test_empty_allowed_files_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(allowed_files=[])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_wildcard_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(allowed_files=["*"])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_glob_pattern_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(allowed_files=["src/**/*.vue"])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_vague_description_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(allowed_files=["相关文件"])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_exact_path_succeeds(self):
        brief = _valid_brief(allowed_files=["src/components/Button.vue"])
        assert brief.allowed_files == ["src/components/Button.vue"]


class TestDirectBriefNormalizesToSingleTaskContract:
    def test_creates_contract_with_direct_task_001(self):
        brief = _valid_brief()
        contract = from_direct_brief(brief, expected_artifact_format="vue_project")

        assert contract.source == "direct"
        assert contract.generation_mode == "application"
        assert contract.expected_artifact_format == "vue_project"
        assert len(contract.tasks) == 1
        assert contract.tasks[0].task_id == "direct_task_001"
        assert contract.tasks[0].goal == brief.goal
        assert contract.tasks[0].allowed_files == brief.allowed_files

    def test_contract_inherits_brief_criteria(self):
        brief = _valid_brief()
        contract = from_direct_brief(brief, expected_artifact_format="vue_project")

        assert contract.acceptance_criteria == brief.acceptance_criteria
        assert contract.verification_requirements == brief.verification_requirements

    def test_contract_auto_generates_id(self):
        brief = _valid_brief()
        contract = from_direct_brief(brief, expected_artifact_format="vue_project")

        assert contract.contract_id
        assert contract.contract_version == 1


class TestPlanNormalizesWithoutLosingProhibitedChanges:
    def test_preserves_prohibited_changes(self):
        plan_tasks = [
            ImplementationTask(
                task_id="task_1",
                goal="Create component",
                allowed_files=["src/Comp.vue"],
                prohibited_files=["src/main.ts"],
                acceptance_criteria=["Component renders"],
                test_requirements=["No console errors"],
            )
        ]
        plan = ImplementationPlan(
            plan_version=1,
            source_design_version=1,
            tasks=plan_tasks,
            prohibited_changes=["package.json"],
            acceptance_criteria=["All tasks done"],
        )

        contract = from_implementation_plan(
            plan, generation_mode="application", expected_artifact_format="vue_project"
        )

        assert contract.source == "plan"
        assert contract.prohibited_changes == ["package.json"]
        assert contract.tasks[0].prohibited_changes == ["src/main.ts"]
        assert contract.acceptance_criteria == ["All tasks done"]

    def test_maps_plan_tasks_to_contract_tasks(self):
        plan_tasks = [
            ImplementationTask(
                task_id="t1",
                goal="Task 1",
                allowed_files=["src/a.vue"],
            ),
            ImplementationTask(
                task_id="t2",
                goal="Task 2",
                allowed_files=["src/b.vue"],
            ),
        ]
        plan = ImplementationPlan(
            plan_version=1,
            source_design_version=1,
            tasks=plan_tasks,
        )

        contract = from_implementation_plan(
            plan, generation_mode="application", expected_artifact_format="vue_project"
        )

        assert len(contract.tasks) == 2
        assert contract.tasks[0].task_id == "t1"
        assert contract.tasks[1].task_id == "t2"

    def test_test_requirements_map_to_verification_requirements(self):
        plan_tasks = [
            ImplementationTask(
                task_id="t1",
                goal="Task 1",
                allowed_files=["src/a.vue"],
                test_requirements=["Unit test passes"],
            ),
        ]
        plan = ImplementationPlan(
            plan_version=1,
            source_design_version=1,
            tasks=plan_tasks,
        )

        contract = from_implementation_plan(
            plan, generation_mode="application", expected_artifact_format="vue_project"
        )

        assert contract.tasks[0].verification_requirements == ["Unit test passes"]


class TestValidationRepairRequiresIssueIds:
    def test_empty_active_issue_ids_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            ExecutionContract(
                source="validation_repair",
                generation_mode="application",
                expected_artifact_format="vue_project",
                goal="Fix validation issues",
                tasks=[ContractTask(task_id="t1", goal="Fix", allowed_files=["src/a.vue"])],
                active_issue_ids=[],
            )
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_validation_repair_with_issue_ids_succeeds(self):
        contract = _valid_contract(
            source="validation_repair",
            active_issue_ids=["issue_001"],
        )
        assert contract.active_issue_ids == ["issue_001"]

    def test_from_validation_repair_empty_issue_ids_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            from_validation_repair(
                generation_mode="application",
                expected_artifact_format="vue_project",
                active_issue_ids=[],
                goal="Fix issues",
                allowed_files=["src/a.vue"],
            )
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_from_validation_repair_creates_contract(self):
        contract = from_validation_repair(
            generation_mode="application",
            expected_artifact_format="vue_project",
            active_issue_ids=["issue_001", "issue_002"],
            goal="Fix validation issues",
            allowed_files=["src/App.vue"],
        )
        assert contract.source == "validation_repair"
        assert contract.active_issue_ids == ["issue_001", "issue_002"]
        assert len(contract.tasks) == 1
        assert contract.tasks[0].task_id == "repair_task_001"


class TestContractRejectsUnresolvedGenerationMode:
    def test_unresolved_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_contract(generation_mode="unresolved")
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_application_succeeds(self):
        contract = _valid_contract(generation_mode="application")
        assert contract.generation_mode == "application"


class TestContractRejectsEmptyTasks:
    def test_empty_tasks_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_contract(tasks=[])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_non_empty_tasks_succeeds(self):
        contract = _valid_contract(
            tasks=[ContractTask(task_id="t1", goal="Do stuff", allowed_files=["src/a.vue"])]
        )
        assert len(contract.tasks) == 1


class TestDirectBriefRequiresNonEmptyCriteria:
    def test_empty_acceptance_criteria_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(acceptance_criteria=[])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_non_empty_acceptance_criteria_succeeds(self):
        brief = _valid_brief(acceptance_criteria=["Works"])
        assert brief.acceptance_criteria == ["Works"]


class TestDirectBriefRequiresNonEmptyVerification:
    def test_empty_verification_requirements_fails(self):
        with pytest.raises(AgentRuntimeError) as exc_info:
            _valid_brief(verification_requirements=[])
        assert exc_info.value.code == AgentErrorCode.STATE_ERROR

    def test_non_empty_verification_requirements_succeeds(self):
        brief = _valid_brief(verification_requirements=["Check passes"])
        assert brief.verification_requirements == ["Check passes"]
