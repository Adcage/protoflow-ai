import logging

from app.grpc import code_generation_pb2
from app.grpc import common_pb2
from app.runtime.events import RuntimeEventType
from app.runtime.event_bus import SequencedRuntimeEvent

logger = logging.getLogger("app.runtime.event_mapper")

_CODE_GEN_TYPE_MAP = {
    1: common_pb2.SINGLE_FILE,
    2: common_pb2.MULTI_FILE,
    3: common_pb2.VUE_PROJECT,
}

_EVENT_TYPE_MAP: dict[RuntimeEventType, int] = {
    RuntimeEventType.TEXT_DELTA: common_pb2.AI_RESPONSE,
    RuntimeEventType.TOOL_CALL: common_pb2.TOOL_REQUEST,
    RuntimeEventType.TOOL_RESULT: common_pb2.TOOL_EXECUTED,
    RuntimeEventType.RUNTIME_ERROR: common_pb2.ERROR,
    RuntimeEventType.DONE: common_pb2.DONE,
}


class ProtoEventMapper:
    def map_event(self, sequenced_event: SequencedRuntimeEvent) -> code_generation_pb2.CodeGenerationEvent | None:
        event = sequenced_event.event
        event_type_proto = _EVENT_TYPE_MAP.get(event.event_type)

        if event_type_proto is None:
            if event.event_type in (RuntimeEventType.STATUS, RuntimeEventType.NODE_STARTED,
                                     RuntimeEventType.NODE_COMPLETED, RuntimeEventType.MODEL_SELECTED):
                return None
            logger.warning("unmapped runtime event type: %s", event.event_type)
            return None

        data = event.data
        kwargs: dict = {
            "agent_run_id": str(sequenced_event.agent_run_id),
            "seq": sequenced_event.seq,
            "event_type": event_type_proto,
        }

        if event.event_type == RuntimeEventType.TEXT_DELTA:
            kwargs["ai_response"] = common_pb2.AiResponseData(
                text=data.get("text", ""),
                fallback=data.get("fallback", False),
            )
        elif event.event_type == RuntimeEventType.TOOL_CALL:
            kwargs["tool_request"] = common_pb2.ToolRequestData(
                id=data.get("id", ""),
                name=data.get("name", ""),
                arguments=data.get("arguments", ""),
            )
        elif event.event_type == RuntimeEventType.TOOL_RESULT:
            kwargs["tool_executed"] = common_pb2.ToolExecutedData(
                id=data.get("id", ""),
                name=data.get("name", ""),
                arguments=data.get("arguments", ""),
                result=data.get("result", ""),
            )
        elif event.event_type == RuntimeEventType.RUNTIME_ERROR:
            kwargs["error"] = common_pb2.ErrorData(
                message=data.get("message", ""),
                code=data.get("code", 0),
            )
        elif event.event_type == RuntimeEventType.DONE:
            kwargs["done"] = common_pb2.DoneData(
                message=data.get("message", ""),
            )

        return code_generation_pb2.CodeGenerationEvent(**kwargs)

