from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError


PhaseReportStatus = Literal[
    "completed", "needs_user", "needs_route", "blocked", "failed"
]

PhaseReportSourceMode = Literal["plan", "implement", "validate", "route"]

RecommendedTransition = Literal[
    "plan", "implement", "validate", "finished", "wait_user", "blocked"
]


class ArtifactRef(BaseModel):
    path: str
    content_digest: str = ""


class OpenItem(BaseModel):
    item_id: str
    description: str
    blocking: bool = True


class PhaseCompletionReport(BaseModel):
    report_id: str
    source_mode: PhaseReportSourceMode
    status: PhaseReportStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    open_items: list[OpenItem] = Field(default_factory=list)
    recommended_transition: RecommendedTransition | None = None
    state_revision: int
    created_at: datetime

    @model_validator(mode="after")
    def _validate_status_open_items_consistency(self) -> "PhaseCompletionReport":
        blocking_items = [oi for oi in self.open_items if oi.blocking]
        if self.status == "completed" and blocking_items:
            raise AgentRuntimeError(
                f"status=completed 但存在 blocking open items: {[oi.item_id for oi in blocking_items]}",
                code=AgentErrorCode.STATE_ERROR,
            )
        if len(self.summary) < 1:
            raise AgentRuntimeError(
                "summary 不能为空字符串",
                code=AgentErrorCode.STATE_ERROR,
            )
        if len(self.summary) > 2000:
            raise AgentRuntimeError(
                f"summary 超过 2000 字限制 (当前 {len(self.summary)} 字)",
                code=AgentErrorCode.STATE_ERROR,
            )
        return self

    @classmethod
    def make_report(
        cls,
        source_mode: PhaseReportSourceMode,
        status: PhaseReportStatus,
        summary: str,
        *,
        evidence_refs: list[str] | None = None,
        artifacts: list[ArtifactRef] | None = None,
        open_items: list[OpenItem] | None = None,
        recommended_transition: RecommendedTransition | None = None,
        state_revision: int = 0,
    ) -> "PhaseCompletionReport":
        return cls(
            report_id=uuid4().hex,
            source_mode=source_mode,
            status=status,
            summary=summary,
            evidence_refs=evidence_refs or [],
            artifacts=artifacts or [],
            open_items=open_items or [],
            recommended_transition=recommended_transition,
            state_revision=state_revision,
            created_at=datetime.now(timezone.utc),
        )
