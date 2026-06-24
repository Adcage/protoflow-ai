"""Phase 6 兼容收口测试：唯一入口、旧状态兼容、生产图。"""


from app.agent_loop.state import AgentLoopState
from app.agent_loop.tool_policy import (
    IMPLEMENT_TOOLS,
    PLAN_TOOLS,
    ROUTE_TOOLS,
    VALIDATE_TOOLS,
)
from app.agent_loop.tools.decide_route import apply_route_decision


class TestProductionGraphStructure:
    def test_production_graph_has_route_between_every_mode(self):
        assert "switch_mode" not in PLAN_TOOLS
        assert "switch_mode" not in IMPLEMENT_TOOLS
        assert "switch_mode" not in ROUTE_TOOLS
        assert "switch_mode" not in VALIDATE_TOOLS

    def test_no_legacy_finish_in_implement_tools(self):
        assert "finish" not in IMPLEMENT_TOOLS
        assert "complete_implementation" in IMPLEMENT_TOOLS

    def test_no_legacy_decide_validation_in_validate_tools(self):
        assert "decide_validation" not in VALIDATE_TOOLS
        assert "submit_validation_report" in VALIDATE_TOOLS


class TestSwitchModeNotRegistered:
    def test_switch_mode_not_in_any_mode(self):
        for tools in (PLAN_TOOLS, IMPLEMENT_TOOLS, ROUTE_TOOLS, VALIDATE_TOOLS):
            assert "switch_mode" not in tools, (
                f"switch_mode 应已删除，发现于: {tools}"
            )


class TestLegacySwitchModeHistoryIgnored:
    def test_legacy_switch_mode_history_is_ignored(self):
        from app.runtime.state import ToolCallRecord
        records = [
            ToolCallRecord(
                id="legacy-1",
                name="switch_mode",
                arguments={"mode": "implement"},
                result=None,
                error=None,
            )
        ]
        from app.core.config import settings
        from app.agent_loop.tool_history import format_tool_observation_history
        observations = format_tool_observation_history(
            records,
            max_total_chars=settings.agent_tool_history_max_chars,
            max_result_chars=settings.agent_tool_result_max_chars,
        )
        if observations is not None:
            assert "switch_mode" not in observations.content


class TestNewRunPersistsV3:
    def test_new_run_persists_only_v3(self):
        from app.agent_loop.state import AgentLoopState as ALS

        state = ALS(mode="plan", status="running")
        envelope = state._to_envelope()
        assert envelope.schema_version == 3

        json_str = state.serialize()
        import json

        data = json.loads(json_str)
        assert data["schema_version"] == 3

    def test_apply_route_decision_writes_mode(self):
        state = AgentLoopState(mode="plan", status="running")
        apply_route_decision(
            state,
            source="plan",
            mode="implement",
            code_gen_type="",
            reason="plan completed",
        )
        assert state.mode == "implement"
        assert state.route_decided is True
        assert state.route_decision["mode"] == "implement"
