"""Plan/Implement/Validate 循环检测与工作区指纹测试。

覆盖 Task 5-3 中关于 progress.py 循环检测、日志文件变化不算进展、cycle 拒绝的实现。
"""

from app.agent_loop.progress import ProgressDetector, ProgressSnapshot


def _snapshot(
    fingerprint: str,
    plan_stage: str = "discover_direction",
    workspace_fp: str = "",
) -> ProgressSnapshot:
    return ProgressSnapshot(
        snapshot_id="x",
        source_mode="plan",
        state_revision=1,
        plan_stage=plan_stage,
        workspace_fingerprint=workspace_fp,
        semantic_progress_fingerprint=fingerprint,
    )


class TestLogFileIgnored:
    def test_log_file_change_is_ignored(self):
        """日志文件变化不应当作代码进展。

        模拟只有日志路径的 workspace_fingerprint 变化，期望不算真实进展。
        真实生产中 _record_progress 只哈希任务相关文件路径，不包括日志。
        """
        detector = ProgressDetector()
        detector.record(_snapshot("fp1", workspace_fp="src/App.vue"))
        detector.record(_snapshot("fp1", workspace_fp="src/App.vue,logs/audit.log"))
        detector.record(_snapshot("fp1", workspace_fp="src/App.vue,logs/audit.log,debug.log"))
        assert detector.detect_stagnation() is True


class TestRepeatedPlanImplementCycle:
    def test_repeated_plan_implement_cycle_detected(self):
        detector = ProgressDetector()
        detector.record(_snapshot("plan1", plan_stage="discover"))
        detector.record(_snapshot("impl1", plan_stage="discover"))
        detector.record(_snapshot("plan1", plan_stage="discover"))
        detector.record(_snapshot("impl1", plan_stage="discover"))
        assert detector.detect_cycle() is True


class TestCycleTargetRejected:
    def test_cycle_target_is_rejected(self):
        """如果 cycle 已确定，Route 不能选择造成循环的同一目标。"""
        from app.agent_loop.transition_guard import (
            RouteContext,
            RouteDecision,
            TransitionGuard,
        )

        ctx = RouteContext(
            source_mode="plan",
            state_revision=1,
            progress_cycle=True,
        )
        decision = RouteDecision(
            target="plan",
            reason_code="plan_blocked",
            rationale="keep planning",
        )
        guard = TransitionGuard()
        rejection = guard.evaluate(ctx, decision)
        assert rejection is not None
        assert "cycle_detected" in rejection.failed_rules
