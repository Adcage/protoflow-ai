"""无进展指纹与循环检测测试。"""


from app.agent_loop.progress import ProgressDetector, ProgressSnapshot


def _snapshot(fingerprint: str, plan_stage: str = "discover_direction") -> ProgressSnapshot:
    return ProgressSnapshot(
        snapshot_id="x",
        source_mode="plan",
        state_revision=1,
        plan_stage=plan_stage,
        semantic_progress_fingerprint=fingerprint,
    )


class TestStagnationDetection:
    def test_same_semantic_state_three_times_detects_stagnation(self):
        detector = ProgressDetector()
        for _ in range(3):
            detector.record(_snapshot("plan:discover:fp1"))
        assert detector.detect_stagnation() is True

    def test_two_identical_snapshots_do_not_trigger_stagnation(self):
        detector = ProgressDetector()
        detector.record(_snapshot("fp1"))
        detector.record(_snapshot("fp1"))
        assert detector.detect_stagnation() is False

    def test_text_only_change_is_not_progress(self):
        detector = ProgressDetector()
        detector.record(_snapshot("same_fp"))
        detector.record(_snapshot("same_fp"))
        detector.record(_snapshot("same_fp"))
        assert detector.detect_stagnation() is True

    def test_file_digest_change_is_progress(self):
        detector = ProgressDetector()
        detector.record(_snapshot("fp1"))
        detector.record(_snapshot("fp1"))
        detector.record(_snapshot("fp2"))
        assert detector.detect_stagnation() is False


class TestCycleDetection:
    def test_repeated_plan_route_same_stage_cycle_detected(self):
        detector = ProgressDetector()
        detector.record(_snapshot("a", plan_stage="S"))
        detector.record(_snapshot("b", plan_stage="S"))
        detector.record(_snapshot("a", plan_stage="S"))
        detector.record(_snapshot("b", plan_stage="S"))
        assert detector.detect_cycle() is True

    def test_user_answer_breaks_stagnation(self):
        detector = ProgressDetector()
        detector.record(_snapshot("fp1"))
        detector.record(_snapshot("fp1"))
        detector.record(_snapshot("fp_user_answer"))
        assert detector.detect_stagnation() is False
        assert detector.detect_cycle() is False


class TestSnapshotRetention:
    def test_snapshot_retention_is_bounded(self):
        detector = ProgressDetector()
        for i in range(35):
            detector.record(ProgressSnapshot(
                snapshot_id=str(i),
                source_mode="plan",
                state_revision=i,
                semantic_progress_fingerprint=f"fp-{i}",
            ))
        assert len(detector.snapshots) == ProgressDetector.MAX_SNAPSHOTS
        assert detector.snapshots[0].snapshot_id == "5"
        assert detector.snapshots[-1].snapshot_id == "34"
