import json
import logging
import os
import re

from app.grpc import code_generation_pb2
from app.grpc import common_pb2
from app.runtime.events import RuntimeEventType
from app.runtime.event_bus import SequencedRuntimeEvent

logger = logging.getLogger("app.runtime.event_mapper")

_VISIBLE_TOOLS = frozenset({
    "write_file",
    "read_file",
    "read_dir",
    "run_checks",
})

_STATUS_TOOLS: dict[str, str] = {
    "select_skill": "正在选择设计方案...",
    "write_plan": "正在制定实现计划...",
    "read_asset": "正在查询设计资源...",
    "run_command": "正在执行命令...",
    "decide_route": "正在路由决策...",
    "decide_validation": "正在输出校验结论...",
    "request_replan": "正在请求重新规划...",
    "submit_requirement_brief": "正在提交需求摘要...",
    "record_project_inspection": "正在记录项目检查...",
    "choose_skill": "正在选择设计方案...",
    "propose_design": "正在提出设计建议...",
    "confirm_design": "正在确认设计方案...",
    "write_implementation_plan": "正在编写实施计划...",
    "plan_stage_guard": "正在处理阶段状态...",
    "confirm_generation_mode": "正在确认生成模式...",
    "complete_implementation": "正在提交实现完成...",
    "submit_validation_report": "正在提交校验报告...",
}

_HIDDEN_TOOLS = frozenset({"finish", "ask_user"})

_INTERNAL_TYPES = frozenset({
    RuntimeEventType.NODE_STARTED,
    RuntimeEventType.NODE_COMPLETED,
    RuntimeEventType.CAPABILITY_SELECTED,
    RuntimeEventType.MODEL_SELECTED,
    RuntimeEventType.MODE_SWITCHED,
    RuntimeEventType.AGENT_LOOP_ITERATION,
    RuntimeEventType.AGENT_LOOP_COMPLETED,
})


def _sanitize_path_in_message(message: str) -> str:
    sanitized = re.sub(r"[A-Za-z]:\\[^\s;,\]]+", "[路径已隐藏]", message)
    sanitized = re.sub(r"/home/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/var/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/tmp/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/opt/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/usr/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    return sanitized


def _sanitize_path(path: str) -> str:
    return os.path.basename(path) if path else path


def _sanitize_tool_arguments(tool_name: str, arguments_str: str) -> str:
    if not arguments_str:
        return arguments_str
    try:
        args = json.loads(arguments_str) if isinstance(arguments_str, str) else dict(arguments_str)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _sanitize_path_in_message(str(arguments_str))

    if tool_name == "write_file":
        args.pop("content", None)
        if "relative_path" in args:
            args["relativeFilePath"] = _sanitize_path(args.pop("relative_path"))
        if "contentLength" not in args:
            pass
    elif tool_name == "read_file":
        if "relative_path" in args:
            args["relativeFilePath"] = _sanitize_path(args.pop("relative_path"))
        args.pop("scope", None)
    elif tool_name == "read_dir":
        if "relative_path" in args:
            args["relativeDirPath"] = _sanitize_path(args.pop("relative_path"))
    elif tool_name == "ask_user":
        pass
    else:
        for key in list(args.keys()):
            val = str(args[key])
            args[key] = _sanitize_path_in_message(val)

    return json.dumps(args, ensure_ascii=False)


def _sanitize_tool_result(tool_name: str, result_str: str) -> str:
    if not result_str:
        return result_str
    if tool_name in ("write_file", "read_dir"):
        return _sanitize_path_in_message(result_str)
    if tool_name == "read_file":
        return _sanitize_path_in_message(result_str)
    if tool_name == "ask_user":
        return _sanitize_path_in_message(result_str)
    return _sanitize_path_in_message(result_str)


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
    RuntimeEventType.STATUS: common_pb2.STATUS,
}


class ProtoEventMapper:
    def __init__(self) -> None:
        self._emitted_question_set_ids: set[str] = set()

    def reset_question_set_dedupe(self) -> None:
        self._emitted_question_set_ids.clear()

    def map_event(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> code_generation_pb2.CodeGenerationEvent | None:
        event = sequenced_event.event

        # CLARIFICATION_REQUIRED 由 event_mapper 折叠为 ask_user TOOL_REQUEST，
        # 同一 questionSetId 只下发一次。
        if event.event_type == RuntimeEventType.CLARIFICATION_REQUIRED:
            return self._map_clarification_required(sequenced_event)

        if event.event_type in _INTERNAL_TYPES:
            return None

        if event.event_type == RuntimeEventType.TOOL_CALL:
            return self._map_tool_call(sequenced_event)

        if event.event_type == RuntimeEventType.TOOL_RESULT:
            return self._map_tool_result(sequenced_event)

        event_type_proto = _EVENT_TYPE_MAP.get(event.event_type)
        if event_type_proto is None:
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
        elif event.event_type == RuntimeEventType.RUNTIME_ERROR:
            kwargs["error"] = common_pb2.ErrorData(
                message=_sanitize_path_in_message(data.get("message", "")),
                code=data.get("code", 0),
            )
        elif event.event_type == RuntimeEventType.DONE:
            kwargs["done"] = common_pb2.DoneData(
                message=_sanitize_path_in_message(data.get("message", "")),
            )
        elif event.event_type == RuntimeEventType.STATUS:
            kwargs["status"] = common_pb2.StatusData(
                message=data.get("message", ""),
            )

        return code_generation_pb2.CodeGenerationEvent(**kwargs)

    def _map_clarification_required(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> code_generation_pb2.CodeGenerationEvent | None:
        data = sequenced_event.event.data or {}
        question_set_id = data.get("questionSetId", "")
        questions = data.get("questions") or []
        if not question_set_id or not questions:
            return None
        if question_set_id in self._emitted_question_set_ids:
            return None
        self._emitted_question_set_ids.add(question_set_id)

        arguments = json.dumps(
            {
                "protocolVersion": data.get("protocolVersion", 1),
                "questionSetId": question_set_id,
                "stage": data.get("stage", ""),
                "questions": questions,
            },
            ensure_ascii=False,
        )
        return code_generation_pb2.CodeGenerationEvent(
            agent_run_id=str(sequenced_event.agent_run_id),
            seq=sequenced_event.seq,
            event_type=common_pb2.TOOL_REQUEST,
            tool_request=common_pb2.ToolRequestData(
                id=question_set_id,
                name="ask_user",
                arguments=arguments,
            ),
        )

    def _map_tool_call(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> code_generation_pb2.CodeGenerationEvent | None:
        data = sequenced_event.event.data
        tool_name = data.get("name", "")

        if tool_name in _HIDDEN_TOOLS:
            return None

        if tool_name in _STATUS_TOOLS:
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.STATUS,
                status=common_pb2.StatusData(
                    message=_STATUS_TOOLS[tool_name],
                ),
            )

        if tool_name in _VISIBLE_TOOLS:
            sanitized_args = _sanitize_tool_arguments(tool_name, data.get("arguments", ""))
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.TOOL_REQUEST,
                tool_request=common_pb2.ToolRequestData(
                    id=data.get("id", ""),
                    name=tool_name,
                    arguments=sanitized_args,
                ),
            )

        status_msg = _STATUS_TOOLS.get(tool_name)
        if status_msg:
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.STATUS,
                status=common_pb2.StatusData(message=status_msg),
            )

        logger.warning("unclassified tool in TOOL_CALL: %s", tool_name)
        return None

    def _map_tool_result(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> code_generation_pb2.CodeGenerationEvent | None:
        data = sequenced_event.event.data
        tool_name = data.get("name", "")

        if tool_name in _HIDDEN_TOOLS:
            return None

        # ask_user TOOL_RESULT 不映射为 AI_RESPONSE；只下发一次 TOOL_REQUEST（来自 CLARIFICATION_REQUIRED 折叠）
        if tool_name == "ask_user":
            return None

        if tool_name in _STATUS_TOOLS:
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.STATUS,
                status=common_pb2.StatusData(
                    message=f"{_STATUS_TOOLS[tool_name].rstrip('.')}完成",
                ),
            )

        if tool_name in _VISIBLE_TOOLS:
            sanitized_args = _sanitize_tool_arguments(tool_name, data.get("arguments", ""))
            sanitized_result = _sanitize_tool_result(tool_name, data.get("result", ""))
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.TOOL_EXECUTED,
                tool_executed=common_pb2.ToolExecutedData(
                    id=data.get("id", ""),
                    name=tool_name,
                    arguments=sanitized_args,
                    result=sanitized_result,
                ),
            )

        status_msg = _STATUS_TOOLS.get(tool_name)
        if status_msg:
            return code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.STATUS,
                status=common_pb2.StatusData(
                    message=f"{status_msg.rstrip('.')}完成",
                ),
            )

        logger.warning("unclassified tool in TOOL_RESULT: %s", tool_name)
        return None
