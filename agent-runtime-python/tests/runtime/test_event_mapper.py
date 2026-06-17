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
            RuntimeEventType.STATUS,
            RuntimeEventType.NODE_STARTED,
            RuntimeEventType.NODE_COMPLETED,
            RuntimeEventType.CAPABILITY_SELECTED,
            RuntimeEventType.MODEL_SELECTED,
            RuntimeEventType.CLARIFICATION_REQUIRED,
            RuntimeEventType.MODE_SWITCHED,
        ],
    )
    def test_internal_events_not_mapped(self, event_type):
        seq_event = _make_sequenced(event_type)
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
