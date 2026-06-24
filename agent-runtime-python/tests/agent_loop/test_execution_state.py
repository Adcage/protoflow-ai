"""任务级执行账本和动态调用预算测试。"""


from app.agent_loop.execution_state import (
    CallBudget,
    ExecutionState,
    ExecutionTaskState,
)


class TestCallBudgetFormula:
    def test_budget_formula_for_tasks_and_issues(self):
        budget = CallBudget.calculate(remaining_tasks=3, active_issues=2)
        assert budget.soft_limit == 18
        assert budget.hard_limit == 36

    def test_budget_minimum_and_maximum(self):
        small = CallBudget.calculate(0, 0)
        assert small.soft_limit == 8
        assert small.hard_limit == 16

        huge = CallBudget.calculate(100, 100)
        assert huge.soft_limit == 700
        assert huge.hard_limit == 120

    def test_budget_does_not_shrink_mid_entry(self):
        budget = CallBudget.calculate(5, 0)
        original_hard = budget.hard_limit
        for _ in range(3):
            budget.model_call_count += 1
        assert budget.hard_limit == original_hard

    def test_hard_limit_blocks_without_completion(self):
        budget = CallBudget.calculate(2, 0)
        budget.model_call_count = budget.hard_limit
        assert budget.reached_hard_limit() is True


class TestExecutionTaskStateValidation:
    def test_only_one_active_task(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="in_progress"),
                ExecutionTaskState(task_id="t2", plan_version=1, status="in_progress"),
            ],
        )
        assert state.count_active_in_progress() == 2

    def test_completed_task_requires_evidence(self):
        task = ExecutionTaskState(task_id="t1", plan_version=1, status="completed")
        assert task.changed_files == []
        assert task.verification_refs == []

    def test_validation_repair_scoped_to_issue_files(self):
        state = ExecutionState(
            run_kind="validation_repair",
            source_plan_version=1,
            active_issue_ids=["issue-1"],
            tasks=[],
        )
        compliant, violations = state.file_scope_compliant(["src/main.vue"])
        assert compliant is True
        assert violations == []


class TestExecutionStateTransitions:
    def test_set_active_task_marks_in_progress(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="pending"),
            ],
        )
        state.set_active_task("t1")
        assert state.active_task_id == "t1"
        assert state.get_active_task().status == "in_progress"
        assert state.get_active_task().attempt_count == 1

    def test_complete_active_task(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="pending"),
            ],
        )
        state.set_active_task("t1")
        state.complete_active_task()
        assert state.active_task_id is None
        assert state.tasks[0].status == "completed"

    def test_record_file_change(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="pending"),
            ],
        )
        state.set_active_task("t1")
        state.record_file_change("src/App.vue", "created", "abc123")
        active = state.get_active_task()
        assert len(active.changed_files) == 1
        assert active.changed_files[0].relative_path == "src/App.vue"

    def test_record_failure(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="in_progress"),
            ],
        )
        state.set_active_task("t1")
        state.record_failure("test failed")
        assert state.get_active_task().status == "failed"
        assert state.get_active_task().failure_reason == "test failed"

    def test_all_target_tasks_completed(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="completed"),
                ExecutionTaskState(task_id="t2", plan_version=1, status="completed"),
            ],
        )
        assert state.all_target_tasks_completed() is True

    def test_all_issues_addressed(self):
        state = ExecutionState(
            run_kind="validation_repair",
            source_plan_version=1,
            active_issue_ids=["i1", "i2"],
        )
        assert state.all_issues_addressed(["i1", "i2", "i3"]) is True
        assert state.all_issues_addressed(["i1"]) is False

    def test_initialize_budget(self):
        state = ExecutionState(
            run_kind="initial",
            source_plan_version=1,
            tasks=[
                ExecutionTaskState(task_id="t1", plan_version=1, status="pending"),
                ExecutionTaskState(task_id="t2", plan_version=1, status="in_progress"),
            ],
            active_issue_ids=["i1"],
        )
        state.initialize_budget()
        assert state.call_budget is not None
        assert state.call_budget.soft_limit == max(8, 2 * 4 + 1 * 3)
        assert state.call_budget.hard_limit == state.call_budget.soft_limit * 2
