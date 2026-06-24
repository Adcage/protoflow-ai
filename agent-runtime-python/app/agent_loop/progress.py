from pydantic import BaseModel


class ProgressSnapshot(BaseModel):
    snapshot_id: str
    source_mode: str
    state_revision: int
    plan_stage: str | None = None
    task_status_fingerprint: str = ""
    validation_issue_fingerprint: str = ""
    workspace_fingerprint: str = ""
    pending_question_set_id: str | None = None
    last_tool_outcome_fingerprint: str = ""
    semantic_progress_fingerprint: str = ""
    created_at: str = ""


class ProgressDetector:
    MAX_SNAPSHOTS = 30

    def __init__(self) -> None:
        self._snapshots: list[ProgressSnapshot] = []

    def record(self, snapshot: ProgressSnapshot) -> None:
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.MAX_SNAPSHOTS:
            self._snapshots = self._snapshots[-self.MAX_SNAPSHOTS :]

    def detect_stagnation(self) -> bool:
        if len(self._snapshots) < 3:
            return False
        last_3 = self._snapshots[-3:]
        fp = last_3[0].semantic_progress_fingerprint
        return all(s.semantic_progress_fingerprint == fp for s in last_3)

    def detect_cycle(self) -> bool:
        if len(self._snapshots) < 4:
            return False
        for pattern_len in range(
            2, min(7, len(self._snapshots) // 2 + 1)
        ):
            recent = [
                s.semantic_progress_fingerprint
                for s in self._snapshots[-pattern_len * 2 :]
            ]
            first_half = recent[:pattern_len]
            second_half = recent[pattern_len:]
            if first_half == second_half:
                return True
        return False

    @property
    def snapshots(self) -> list[ProgressSnapshot]:
        return list(self._snapshots)
