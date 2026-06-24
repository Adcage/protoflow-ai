from datetime import datetime, timezone

import pytest

from app.agent_loop.phase_report import (
    ArtifactRef,
    OpenItem,
    PhaseCompletionReport,
)
from app.core.exceptions import AgentRuntimeError


class TestPhaseCompletionReport:
    def test_valid_completed_report(self):
        report = PhaseCompletionReport.make_report(
            source_mode="plan",
            status="completed",
            summary="计划已完成",
            evidence_refs=["plan:v1"],
        )
        assert report.status == "completed"
        assert len(report.open_items) == 0
        assert report.report_id != ""
        assert report.created_at != ""

    def test_phase_report_rejects_unknown_status(self):
        with pytest.raises(Exception):
            PhaseCompletionReport.make_report(
                source_mode="plan",
                status="unknown_status",
                summary="test",
            )

    def test_completed_with_blocking_open_item_is_rejected(self):
        with pytest.raises(AgentRuntimeError):
            PhaseCompletionReport.make_report(
                source_mode="implement",
                status="completed",
                summary="声称完成",
                open_items=[
                    OpenItem(item_id="i1", description="未修 bug", blocking=True),
                ],
            )

    def test_completed_with_non_blocking_open_item_is_allowed(self):
        report = PhaseCompletionReport.make_report(
            source_mode="implement",
            status="completed",
            summary="主要完成",
            open_items=[
                OpenItem(item_id="i2", description="建议优化", blocking=False),
            ],
        )
        assert report.status == "completed"

    def test_blocked_with_blocking_open_items(self):
        report = PhaseCompletionReport.make_report(
            source_mode="plan",
            status="blocked",
            summary="预算耗尽",
            open_items=[
                OpenItem(item_id="i3", description="未确认设计", blocking=True),
            ],
        )
        assert report.status == "blocked"

    def test_report_id_is_auto_generated(self):
        report1 = PhaseCompletionReport.make_report(
            source_mode="implement", status="completed", summary="done"
        )
        report2 = PhaseCompletionReport.make_report(
            source_mode="implement", status="completed", summary="done"
        )
        assert report1.report_id != report2.report_id

    def test_created_at_is_auto_generated(self):
        report = PhaseCompletionReport.make_report(
            source_mode="validate", status="completed", summary="done"
        )
        assert report.created_at is not None

    def test_make_report_factory(self):
        report = PhaseCompletionReport.make_report(
            source_mode="implement",
            status="needs_route",
            summary="实现完成，等待路由",
            evidence_refs=["task:1", "task:2"],
            state_revision=5,
        )
        assert report.source_mode == "implement"
        assert report.status == "needs_route"
        assert report.state_revision == 5
        assert len(report.evidence_refs) == 2

    def test_summary_over_2000_is_rejected(self):
        with pytest.raises(AgentRuntimeError):
            PhaseCompletionReport.make_report(
                source_mode="plan",
                status="completed",
                summary="x" * 3000,
            )

    def test_valid_source_modes(self):
        for mode in ("plan", "implement", "validate", "route"):
            report = PhaseCompletionReport.make_report(
                source_mode=mode, status="completed", summary="done"
            )
            assert report.source_mode == mode

    def test_artifact_ref(self):
        ref = ArtifactRef(path="src/App.vue", content_digest="sha256:abc")
        assert ref.path == "src/App.vue"

    def test_open_item(self):
        item = OpenItem(item_id="oi1", description="缺少设计确认", blocking=True)
        assert item.blocking is True

    def test_summary_is_required(self):
        with pytest.raises(Exception):
            PhaseCompletionReport(
                report_id="test",
                source_mode="plan",
                status="completed",
                state_revision=0,
                created_at=datetime.now(timezone.utc),
            )

    def test_recommended_transition_must_be_valid_enum(self):
        with pytest.raises(Exception):
            PhaseCompletionReport.make_report(
                source_mode="plan",
                status="completed",
                summary="done",
                recommended_transition="invalid_mode",
            )
