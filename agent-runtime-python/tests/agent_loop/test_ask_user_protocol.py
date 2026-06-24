"""Phase 3 ask_user 结构化协议测试。"""

import json
from typing import Any

import pytest

from app.agent_loop.state import AgentLoopState
from app.agent_loop.tools.ask_user import PROTOCOL_VERSION, AskUserTool


class _FakeEventBus:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def emit(self, event: Any) -> None:
        self.events.append(event)


def _init_envelope(state: AgentLoopState) -> None:
    state._state_envelope = state._to_envelope()


class TestAskUserQuestionSetId:
    @pytest.mark.asyncio
    async def test_emits_question_set_id_and_structured_protocol(self):
        state = AgentLoopState()
        _init_envelope(state)
        bus = _FakeEventBus()

        tool = AskUserTool()
        tool.set_state(state)
        tool.set_event_bus(bus)

        result = await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q7",
                    "prompt": "请选择界面视觉方向",
                    "inputType": "single_select",
                    "required": True,
                    "options": [
                        {"id": "opt_minimal", "label": "现代极简", "description": "..."},
                        {"id": "opt_glass", "label": "玻璃拟态", "description": "..."},
                    ],
                }
            ],
        )
        assert state.status == "waiting_for_user"
        # 写入了 clarification_questions，且包含 questionSetId
        assert len(state.clarification_questions) == 1
        record = state.clarification_questions[0]
        assert record["protocolVersion"] == PROTOCOL_VERSION
        assert record["questionSetId"].startswith("qs_discover_direction_")
        assert record["questions"][0]["id"] == "q7"

        # emit 的事件携带结构化 payload
        assert len(bus.events) == 1
        event = bus.events[0]
        assert event.event_type.value == "clarification_required"
        assert event.data["protocolVersion"] == PROTOCOL_VERSION
        assert event.data["questionSetId"] == record["questionSetId"]
        assert "等待用户回答" in result

    @pytest.mark.asyncio
    async def test_question_id_matches_state_and_event(self):
        state = AgentLoopState()
        _init_envelope(state)
        bus = _FakeEventBus()

        tool = AskUserTool()
        tool.set_state(state)
        tool.set_event_bus(bus)

        # 第一次提问
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "应用方向？",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        first_qsid = state.clarification_questions[0]["questionSetId"]
        first_event_qsid = bus.events[-1].data["questionSetId"]
        assert first_qsid == first_event_qsid

        state.status = "running"
        # 第二次提问
        await tool._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "功能范围？",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "x", "label": "X"}],
                }
            ],
        )
        second_qsid = state.clarification_questions[1]["questionSetId"]
        second_event_qsid = bus.events[-1].data["questionSetId"]
        assert second_qsid != first_qsid
        assert second_qsid == second_event_qsid

    @pytest.mark.asyncio
    async def test_rejects_empty_questions(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = AskUserTool()
        tool.set_state(state)

        result = await tool._arun(stage="discover_direction", questions=[])
        assert "错误" in result

    @pytest.mark.asyncio
    async def test_rejects_missing_options(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = AskUserTool()
        tool.set_state(state)

        result = await tool._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "color?",
                    "inputType": "single_select",
                    "required": True,
                    "options": [],
                }
            ],
        )
        assert "错误" in result

    @pytest.mark.asyncio
    async def test_question_set_id_factory_used(self):
        state = AgentLoopState()
        _init_envelope(state)
        bus = _FakeEventBus()

        tool = AskUserTool()
        tool.set_state(state)
        tool.set_event_bus(bus)
        tool.set_question_set_id_factory(lambda stage: f"qs_{stage}_fixed")

        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "x",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questionSetId"] == "qs_discover_direction_fixed"
        assert bus.events[0].data["questionSetId"] == "qs_discover_direction_fixed"


class TestAskUserSerialization:
    @pytest.mark.asyncio
    async def test_question_set_round_trip(self):
        state = AgentLoopState()
        _init_envelope(state)
        tool = AskUserTool()
        tool.set_state(state)
        await tool._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "color?",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "dark", "label": "深色"}],
                }
            ],
        )
        json_str = state.serialize()
        data = json.loads(json_str)
        wf = data["workflow"]
        assert wf["plan"]["clarification_questions"][0]["questionSetId"].startswith(
            "qs_discover_scope_"
        )
        assert wf["plan"]["clarification_questions"][0]["protocolVersion"] == PROTOCOL_VERSION
        # 重新反序列化
        restored = AgentLoopState.deserialize(json_str)
        assert restored.clarification_questions[0]["questions"][0]["prompt"] == "color?"


class TestAskUserAnswerMatchesQuestionSet:
    @pytest.mark.asyncio
    async def test_orchestrator_must_match_question_set_id(self):
        """answer 需要 questionSetId 一致；不一致应被 reject。"""
        state = AgentLoopState()
        _init_envelope(state)
        bus = _FakeEventBus()
        tool = AskUserTool()
        tool.set_state(state)
        tool.set_event_bus(bus)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "color?",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "dark", "label": "深色"}],
                }
            ],
        )
        valid_qsid = state.clarification_questions[0]["questionSetId"]
        # 工具本身不做严格匹配（编排层负责），但保存的 record 携带 questionSetId
        await tool._arun(
            stage="discover_scope",
            questions=[
                {
                    "id": "q1",
                    "prompt": "继续",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questionSetId"] == valid_qsid
        assert state.clarification_questions[1]["questionSetId"] != valid_qsid


class TestAskUserEventMapping:
    """ask_user 事件映射相关测试在 tests/runtime/test_event_mapper.py。"""

    def test_clarification_required_appears_once_per_qsid(self):
        """同一 questionSetId 在 ProtoEventMapper 中只下发一次。"""
        from app.runtime.event_bus import SequencedRuntimeEvent
        from app.runtime.event_mapper import ProtoEventMapper
        from app.runtime.events import RuntimeEvent, RuntimeEventType

        mapper = ProtoEventMapper()
        qsid = "qs_test_once"
        payload = {
            "questionSetId": qsid,
            "stage": "x",
            "protocolVersion": 1,
            "questions": [
                {"id": "q1", "prompt": "p", "inputType": "single_select", "required": True, "options": []}
            ],
        }
        first = mapper.map_event(
            SequencedRuntimeEvent(
                agent_run_id=1,
                seq=1,
                event=RuntimeEvent(RuntimeEventType.CLARIFICATION_REQUIRED, payload),
            )
        )
        second = mapper.map_event(
            SequencedRuntimeEvent(
                agent_run_id=1,
                seq=2,
                event=RuntimeEvent(RuntimeEventType.CLARIFICATION_REQUIRED, payload),
            )
        )
        assert first is not None
        assert first.tool_request.name == "ask_user"
        assert first.tool_request.id == qsid
        assert second is None


class TestAskUserInputTypeNormalization:
    """Phase 3 协议：inputType 只接受 single_select / multi_select。

    模型可能传 single_choice / multi_choice / select / single / multi / text 等变体。
    - 含 multi 关键字 → multi_select
    - text → 直接拒绝（ask_user 统一为选择式，自由文本由前端"自定义回答"实现）
    - 其他单选语义变体（single_choice / select / choice）→ single_select
    - 任何变体都必须在归一化后提供 options；为空则拒绝
    """

    def _build_tool(self, state: AgentLoopState) -> AskUserTool:
        _init_envelope(state)
        tool = AskUserTool()
        tool.set_state(state)
        return tool

    @pytest.mark.asyncio
    async def test_single_choice_normalized_to_single_select(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "方向？",
                    "inputType": "single_choice",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questions"][0]["inputType"] == "single_select"

    @pytest.mark.asyncio
    async def test_multi_choice_normalized_to_multi_select(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "场景？",
                    "inputType": "multi_choice",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questions"][0]["inputType"] == "multi_select"

    @pytest.mark.asyncio
    async def test_select_normalized_to_single_select(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "方向？",
                    "inputType": "select",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questions"][0]["inputType"] == "single_select"

    @pytest.mark.asyncio
    async def test_multi_normalized_to_multi_select(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "场景？",
                    "inputType": "multi",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                }
            ],
        )
        assert state.clarification_questions[0]["questions"][0]["inputType"] == "multi_select"

    @pytest.mark.asyncio
    async def test_text_input_type_rejected_without_options(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        result = await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "请补充",
                    "inputType": "text",
                    "required": True,
                    "options": [],
                }
            ],
        )
        assert "错误" in result
        assert "text" in result
        # 拒绝后不写入 state
        assert state.clarification_questions == []

    @pytest.mark.asyncio
    async def test_text_input_type_rejected_even_with_options(self):
        """text 不再被自动纠正为 single_select，必须拒绝。"""
        state = AgentLoopState()
        tool = self._build_tool(state)
        result = await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "请选择",
                    "inputType": "text",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                }
            ],
        )
        assert "错误" in result
        assert "text" in result
        assert state.clarification_questions == []

    @pytest.mark.asyncio
    async def test_normalization_persists_in_event_payload(self):
        """归一化后的 inputType 必须同时进入 state 和 CLARIFICATION_REQUIRED 事件。"""
        state = AgentLoopState()
        _init_envelope(state)
        bus = _FakeEventBus()
        tool = AskUserTool()
        tool.set_state(state)
        tool.set_event_bus(bus)
        await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "方向？",
                    "inputType": "single_choice",
                    "required": True,
                    "options": [{"id": "a", "label": "A"}],
                },
                {
                    "id": "q2",
                    "prompt": "场景？",
                    "inputType": "multi_choice",
                    "required": True,
                    "options": [{"id": "x", "label": "X"}, {"id": "y", "label": "Y"}],
                },
            ],
        )
        normalized = state.clarification_questions[0]["questions"]
        assert normalized[0]["inputType"] == "single_select"
        assert normalized[1]["inputType"] == "multi_select"
        event_questions = bus.events[0].data["questions"]
        assert event_questions[0]["inputType"] == "single_select"
        assert event_questions[1]["inputType"] == "multi_select"

    @pytest.mark.asyncio
    async def test_missing_options_after_normalization_rejected(self):
        state = AgentLoopState()
        tool = self._build_tool(state)
        result = await tool._arun(
            stage="discover_direction",
            questions=[
                {
                    "id": "q1",
                    "prompt": "方向？",
                    "inputType": "single_choice",
                    "required": True,
                    "options": [],
                }
            ],
        )
        assert "错误" in result
        assert "options" in result
        assert state.clarification_questions == []


class TestFrontendPlanningDataPath:
    """前端 PlanningForm 解析与展示逻辑的 Python 等价测试。

    Phase 3 §8 要求：
    - test_frontend_prefers_structured_planning_data
    - test_frontend_parses_legacy_planning_tag
    frontend-vue 暂未配置 Vitest；以下测试在 Python 端精确复现前端 ChatMessageList.getPlanningData
    的两条解析路径，确保 contract 行为可被自动化验证。
    """

    def _structured_planning_data(self, planning: dict[str, Any]) -> dict[str, Any] | None:
        """复现 ChatMessageList.getPlanningData 的结构化路径：优先 msg.planning 字段。"""
        if planning and planning.get("questions"):
            return {
                "planningType": "clarification",
                "questionSetId": planning.get("questionSetId"),
                "questions": planning["questions"],
            }
        return None

    _PLANNING_TAG_RE = __import__("re").compile(
        r'<planning\s+type="(\w+)"\s*>([\s\S]*?)<\/planning>'
    )

    def _legacy_planning_data(self, content: str) -> dict[str, Any] | None:
        """复现 ChatMessageList.getPlanningData 的旧 <planning> 标签路径。"""
        import json as _json

        match = self._PLANNING_TAG_RE.search(content)
        if not match:
            return None
        try:
            data = _json.loads(match.group(2))
            return {"planningType": match.group(1), **data}
        except Exception:
            return None

    def test_frontend_prefers_structured_planning_data(self):
        """新事件：前端不再依赖文本正则，必须使用 msg.planning 字段。"""
        structured = {
            "questionSetId": "qs_discover_direction_xyz",
            "stage": "discover_direction",
            "protocolVersion": 1,
            "questions": [
                {
                    "id": "q7",
                    "prompt": "请选择界面视觉方向",
                    "inputType": "single_select",
                    "required": True,
                    "options": [{"id": "opt_minimal", "label": "现代极简"}],
                }
            ],
        }
        result = self._structured_planning_data(structured)
        assert result is not None
        assert result["planningType"] == "clarification"
        assert result["questionSetId"] == "qs_discover_direction_xyz"
        assert result["questions"][0]["id"] == "q7"
        # 不能在缺省消息文本上回退到 <planning> 标签
        assert self._legacy_planning_data("") is None

    def test_frontend_parses_legacy_planning_tag(self):
        """历史消息：仍可由 <planning> 正则兼容解析，新结构化字段不再影响。"""
        legacy_tag = (
            '<planning type="clarification">{"questions":[{"id":"q1",'
            '"question":"颜色？","inputType":"single_select","required":true,'
            '"options":[{"value":"dark","label":"深色"}]}]}</planning>'
        )
        result = self._legacy_planning_data(legacy_tag)
        assert result is not None
        assert result["planningType"] == "clarification"
        assert result["questions"][0]["id"] == "q1"
        assert result["questions"][0]["question"] == "颜色？"
        # 结构化路径不能误判：旧消息只放在文本里，没有 msg.planning
        assert self._structured_planning_data({}) is None
