import json

import pytest

from app.grpc import common_pb2
from app.runtime.event_mapper import ProtoEventMapper
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.event_bus import SequencedRuntimeEvent


def _make_sequenced(
    event_type: RuntimeEventType, data: dict | None = None
) -> SequencedRuntimeEvent:
    return SequencedRuntimeEvent(
        agent_run_id=1,
        seq=1,
        event=RuntimeEvent(event_type, data or {}),
    )


class TestProtoEventMapper:
    def setup_method(self):
        self.mapper = ProtoEventMapper()

    def test_text_delta_maps_to_ai_response(self):
        seq_event = _make_sequenced(
            RuntimeEventType.TEXT_DELTA, {"text": "hello", "fallback": False}
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.AI_RESPONSE
        assert result.ai_response.text == "hello"
        assert result.ai_response.fallback is False

    def test_tool_call_maps_to_tool_request(self):
        seq_event = _make_sequenced(
            RuntimeEventType.TOOL_CALL,
            {
                "id": "call_1",
                "name": "write_file",
                "arguments": '{"path": "a.py"}',
            },
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.TOOL_REQUEST
        assert result.tool_request.id == "call_1"
        assert result.tool_request.name == "write_file"

    def test_tool_result_maps_to_tool_executed(self):
        seq_event = _make_sequenced(
            RuntimeEventType.TOOL_RESULT,
            {
                "id": "call_1",
                "name": "write_file",
                "arguments": '{"path": "a.py"}',
                "result": "ok",
            },
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.TOOL_EXECUTED
        assert result.tool_executed.result == "ok"

    @pytest.mark.parametrize(
        ("event_type", "expected_message"),
        [
            (RuntimeEventType.TOOL_CALL, "正在请求重新规划..."),
            (RuntimeEventType.TOOL_RESULT, "正在请求重新规划完成"),
        ],
    )
    def test_request_replan_maps_to_status(self, event_type, expected_message):
        seq_event = _make_sequenced(
            event_type,
            {
                "id": "call_replan",
                "name": "request_replan",
                "arguments": '{"reason": "计划缺少路由方案"}',
                "result": "已提交重新规划请求",
            },
        )

        result = self.mapper.map_event(seq_event)

        assert result is not None
        assert result.event_type == common_pb2.STATUS
        assert result.status.message == expected_message

    def test_runtime_error_maps_to_error(self):
        seq_event = _make_sequenced(
            RuntimeEventType.RUNTIME_ERROR, {"message": "fail", "code": 60001}
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.ERROR
        assert result.error.message == "fail"
        assert result.error.code == 60001

    def test_runtime_error_sanitizes_paths(self):
        seq_event = _make_sequenced(
            RuntimeEventType.RUNTIME_ERROR,
            {
                "message": "读取文件失败: E:\\storage\\workspace\\secret.txt",
                "code": 60001,
            },
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert "storage" not in result.error.message
        assert "secret.txt" not in result.error.message
        assert "[路径已隐藏]" in result.error.message

    def test_done_sanitizes_paths(self):
        seq_event = _make_sequenced(
            RuntimeEventType.DONE,
            {
                "message": "完成 /home/user/workspace/project",
            },
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert "workspace" not in result.done.message
        assert "[路径已隐藏]" in result.done.message

    def test_done_maps_to_done(self):
        seq_event = _make_sequenced(RuntimeEventType.DONE, {"message": "completed"})
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.DONE
        assert result.done.message == "completed"

    @pytest.mark.parametrize(
        "event_type",
        [
            RuntimeEventType.NODE_STARTED,
            RuntimeEventType.NODE_COMPLETED,
            RuntimeEventType.CAPABILITY_SELECTED,
            RuntimeEventType.MODEL_SELECTED,
            RuntimeEventType.MODE_SWITCHED,
        ],
    )
    def test_internal_events_not_mapped(self, event_type):
        seq_event = _make_sequenced(event_type)
        result = self.mapper.map_event(seq_event)
        assert result is None

    def test_clarification_required_maps_to_single_tool_request(self):
        """CLARIFICATION_REQUIRED 必须映射为单条 ask_user TOOL_REQUEST。"""
        payload = {
            "questionSetId": "qs_protocol_test",
            "stage": "propose_design",
            "protocolVersion": 1,
            "questions": [
                {
                    "id": "q7",
                    "prompt": "请选择界面视觉方向",
                    "inputType": "single_select",
                    "required": True,
                    "options": [
                        {"id": "opt_minimal", "label": "现代极简", "description": ""},
                    ],
                }
            ],
        }
        seq_event = _make_sequenced(
            RuntimeEventType.CLARIFICATION_REQUIRED, payload
        )
        result = self.mapper.map_event(seq_event)
        assert result is not None
        assert result.event_type == common_pb2.TOOL_REQUEST
        assert result.tool_request.name == "ask_user"
        assert result.tool_request.id == "qs_protocol_test"
        arguments = json.loads(result.tool_request.arguments)
        assert arguments["questionSetId"] == "qs_protocol_test"
        assert arguments["protocolVersion"] == 1
        assert arguments["questions"][0]["id"] == "q7"

    def test_clarification_required_deduped_per_question_set_id(self):
        """同一 questionSetId 第二次 CLARIFICATION_REQUIRED 应被丢弃。"""
        payload = {
            "questionSetId": "qs_dup",
            "stage": "x",
            "protocolVersion": 1,
            "questions": [
                {"id": "q1", "prompt": "p", "inputType": "single_select", "required": True, "options": []}
            ],
        }
        first = self.mapper.map_event(
            _make_sequenced(RuntimeEventType.CLARIFICATION_REQUIRED, payload)
        )
        second = self.mapper.map_event(
            _make_sequenced(RuntimeEventType.CLARIFICATION_REQUIRED, payload)
        )
        assert first is not None
        assert second is None

    def test_ask_user_tool_result_not_mapped_to_ai_response(self):
        """ask_user TOOL_RESULT 不再被映射为 AI_RESPONSE 气泡。"""
        seq_event = _make_sequenced(
            RuntimeEventType.TOOL_RESULT,
            {
                "id": "ask-user-result-1",
                "name": "ask_user",
                "arguments": "{}",
                "result": "已向用户提问",
            },
        )
        result = self.mapper.map_event(seq_event)
        assert result is None

    def test_agent_run_id_and_seq_preserved(self):
        seq_event = SequencedRuntimeEvent(
            agent_run_id=42,
            seq=7,
            event=RuntimeEvent(RuntimeEventType.DONE, {"message": "ok"}),
        )
        result = self.mapper.map_event(seq_event)
        assert result.agent_run_id == "42"
        assert result.seq == 7
