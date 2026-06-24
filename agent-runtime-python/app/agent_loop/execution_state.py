"""任务级执行账本和动态调用预算。

Phase 4 Task 4-1: 实现 Implement 模式下的任务追踪、调用预算和文件变更记录。
"""

from typing import Literal

from pydantic import BaseModel, Field


ImplementRunKind = Literal["initial", "user_modification", "validation_repair"]
TaskStatus = Literal["pending", "in_progress", "completed", "blocked", "failed"]


class FileChangeRef(BaseModel):
    relative_path: str
    change_type: Literal["created", "modified", "deleted"]
    content_digest: str | None = None


class ExecutionTaskState(BaseModel):
    task_id: str
    plan_version: int
    status: TaskStatus = "pending"
    attempt_count: int = 0
    changed_files: list[FileChangeRef] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    verification_refs: list[str] = Field(default_factory=list)
    failure_reason: str | None = None


class CallBudget(BaseModel):
    soft_limit: int
    hard_limit: int
    model_call_count: int = 0

    @staticmethod
    def calculate(remaining_tasks: int, active_issues: int) -> "CallBudget":
        soft = max(8, remaining_tasks * 4 + active_issues * 3)
        hard = min(120, soft * 2)
        return CallBudget(soft_limit=soft, hard_limit=hard)

    def reached_soft_limit(self) -> bool:
        return self.model_call_count >= self.soft_limit

    def reached_hard_limit(self) -> bool:
        return self.model_call_count >= self.hard_limit


class ExecutionState(BaseModel):
    run_kind: ImplementRunKind = "initial"
    source_plan_version: int = 0
    active_task_id: str | None = None
    tasks: list[ExecutionTaskState] = Field(default_factory=list)
    active_issue_ids: list[str] = Field(default_factory=list)
    call_budget: CallBudget | None = None
    completion_candidate: dict | None = None

    def initialize_budget(self) -> None:
        remaining = sum(
            1 for t in self.tasks if t.status in ("pending", "in_progress", "failed")
        )
        active_issues = len(self.active_issue_ids)
        self.call_budget = CallBudget.calculate(remaining, active_issues)

    def increment_model_call(self) -> int:
        if self.call_budget is not None:
            self.call_budget.model_call_count += 1
            return self.call_budget.model_call_count
        return 0

    def get_active_task(self) -> ExecutionTaskState | None:
        if self.active_task_id is None:
            return None
        for t in self.tasks:
            if t.task_id == self.active_task_id:
                return t
        return None
    def set_active_task(self, task_id: str) -> None:
        active = self.get_active_task()
        if active is not None and active.status == "in_progress":
            active.status = "pending"
        self.active_task_id = task_id
        for t in self.tasks:
            if t.task_id == task_id and t.status == "pending":
                t.status = "in_progress"
                t.attempt_count += 1
                break

    def record_file_change(
        self,
        relative_path: str,
        change_type: Literal["created", "modified", "deleted"],
        content_digest: str | None = None,
    ) -> None:
        active = self.get_active_task()
        if active is None:
            return
        for fc in active.changed_files:
            if fc.relative_path == relative_path:
                fc.change_type = change_type
                fc.content_digest = content_digest
                return
        active.changed_files.append(
            FileChangeRef(
                relative_path=relative_path,
                change_type=change_type,
                content_digest=content_digest,
            )
        )

    def record_tool_call(self, tool_call_id: str) -> None:
        active = self.get_active_task()
        if active is not None:
            active.tool_call_ids.append(tool_call_id)

    def record_failure(self, reason: str) -> None:
        active = self.get_active_task()
        if active is not None:
            active.status = "failed"
            active.failure_reason = reason

    def complete_active_task(self) -> None:
        active = self.get_active_task()
        if active is not None:
            active.status = "completed"
            self.active_task_id = None

    def count_active_in_progress(self) -> int:
        return sum(1 for t in self.tasks if t.status == "in_progress")

    def all_target_tasks_completed(self) -> bool:
        non_blocked = [t for t in self.tasks if t.status != "blocked"]
        if not non_blocked:
            return False
        return all(t.status == "completed" for t in non_blocked)

    def all_issues_addressed(self, addressed_ids: list[str]) -> bool:
        if not self.active_issue_ids:
            return True
        return set(self.active_issue_ids).issubset(set(addressed_ids))

    def file_scope_compliant(self, written_files: list[str]) -> tuple[bool, list[str]]:
        allowed = set()
        prohibited = set()
        for t in self.tasks:
            allowed.update(t.allowed_files if hasattr(t, "allowed_files") else [])
            prohibited.update(t.prohibited_files if hasattr(t, "prohibited_files") else [])
        violations = [f for f in written_files if f in prohibited]
        if violations:
            return False, violations
        return True, []
