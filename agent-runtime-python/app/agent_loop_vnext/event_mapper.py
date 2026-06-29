"""vNext Agent Loop 事件映射器。

与 LegacyEventMapper 的区别：
1. 使用策略模式（status_strategies）动态生成工具描述，无硬编码 _STATUS_TOOLS
2. TOOL_CALL 时额外发射 STATUS {description} 事件，供前端状态条展示
3. _sanitize 逻辑精简，仅处理 vNext 工具
"""

import json
import logging

from app.grpc import code_generation_pb2
from app.grpc import common_pb2
from app.runtime.event_mapper import (
    ProtoEventMapper,
    _sanitize_path,
    _sanitize_path_in_message,
)
from app.runtime.event_bus import SequencedRuntimeEvent
from app.agent_loop_vnext.status_strategies import get_tool_status_description

logger = logging.getLogger("app.agent_loop_vnext.event_mapper")


# ---------------------------------------------------------------------------
# vNext 工具常量
# ---------------------------------------------------------------------------

_VISIBLE_TOOLS = frozenset({
    "Read",
    "Write",
    "Edit",
    "Insert",
    "Glob",
    "Grep",
    "LoadSkill",
    "Bash",
    "AskUser",
})

_HIDDEN_TOOLS_RESULT = frozenset({"AskUser"})


# ---------------------------------------------------------------------------
# vNext 脱敏逻辑
# ---------------------------------------------------------------------------


def _sanitize_tool_arguments(tool_name: str, arguments_str: str) -> str:
    """vNext 工具参数脱敏。"""
    if not arguments_str:
        return arguments_str
    try:
        args = json.loads(arguments_str) if isinstance(arguments_str, str) else dict(arguments_str)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _sanitize_path_in_message(str(arguments_str))

    if tool_name == "Read":
        if "path" in args:
            args["path"] = _sanitize_path(args["path"])
        args.pop("view_range", None)
    elif tool_name == "Write":
        args.pop("content", None)
        if "path" in args:
            args["path"] = _sanitize_path(args["path"])
    elif tool_name == "Edit":
        args.pop("old_str", None)
        args.pop("new_str", None)
        if "path" in args:
            args["path"] = _sanitize_path(args["path"])
    elif tool_name == "Insert":
        args.pop("insert_text", None)
        if "path" in args:
            args["path"] = _sanitize_path(args["path"])
    elif tool_name in ("Glob", "Grep"):
        if "path" in args:
            args["path"] = _sanitize_path(args["path"])
    elif tool_name == "LoadSkill":
        pass
    elif tool_name == "Bash":
        if "command" in args:
            cmd = args["command"]
            args["command"] = (cmd[:200] + "...") if len(cmd) > 200 else cmd
    else:
        for key in list(args.keys()):
            val = str(args[key])
            args[key] = _sanitize_path_in_message(val)

    return json.dumps(args, ensure_ascii=False)


def _sanitize_tool_result(tool_name: str, result_str: str) -> str:
    """vNext 工具结果脱敏。"""
    if not result_str:
        return result_str
    return _sanitize_path_in_message(result_str)


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class VNextEventMapper(ProtoEventMapper):
    """vNext Agent Loop 事件映射器。

    核心差异：
    - _map_tool_call 额外发射一条 STATUS 事件（描述由策略模式生成）
    - _map_tool_result 仅保留 TOOL_EXECUTED 事件
    - 无 _STATUS_TOOLS 硬编码
    - is_test=True 时跳过脱敏（测试应用调试用）
    """

    def __init__(self, is_test: bool = False) -> None:
        super().__init__()
        self._is_test = is_test

    def set_is_test(self, is_test: bool) -> None:
        self._is_test = is_test

    def _sanitize_args(self, tool_name: str, arguments_raw) -> str:
        """根据 is_test 决定是否脱敏。"""
        if self._is_test:
            # 测试模式：不脱敏，返回原始参数
            if isinstance(arguments_raw, str):
                return arguments_raw
            return json.dumps(arguments_raw, ensure_ascii=False)
        return _sanitize_tool_arguments(tool_name, arguments_raw)

    def _sanitize_res(self, tool_name: str, result_str: str) -> str:
        """根据 is_test 决定是否脱敏。"""
        if self._is_test:
            return result_str
        return _sanitize_tool_result(tool_name, result_str)

    def _map_tool_call(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> list[code_generation_pb2.CodeGenerationEvent]:
        data = sequenced_event.event.data
        tool_name = data.get("name", "")

        events: list[code_generation_pb2.CodeGenerationEvent] = []

        # 脱敏参数
        arguments_raw = data.get("arguments", "")
        sanitized_args = self._sanitize_args(tool_name, arguments_raw)

        # 1. TOOL_REQUEST 事件（向后兼容，前端当前依赖此事件）
        events.append(code_generation_pb2.CodeGenerationEvent(
            agent_run_id=str(sequenced_event.agent_run_id),
            seq=sequenced_event.seq,
            event_type=common_pb2.TOOL_REQUEST,
            tool_request=common_pb2.ToolRequestData(
                id=data.get("id", ""),
                name=tool_name,
                arguments=sanitized_args,
            ),
        ))

        # 2. STATUS 事件：使用策略模式生成描述
        #    尝试解析参数为字典供策略使用
        raw_args: dict = {}
        if arguments_raw:
            try:
                raw_args = json.loads(arguments_raw) if isinstance(arguments_raw, str) else dict(arguments_raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        description = get_tool_status_description(tool_name, raw_args, is_test=self._is_test)
        if description:
            events.append(code_generation_pb2.CodeGenerationEvent(
                agent_run_id=str(sequenced_event.agent_run_id),
                seq=sequenced_event.seq,
                event_type=common_pb2.STATUS,
                status=common_pb2.StatusData(
                    message=description,
                ),
            ))

        return events

    def _map_tool_result(
        self, sequenced_event: SequencedRuntimeEvent
    ) -> list[code_generation_pb2.CodeGenerationEvent]:
        data = sequenced_event.event.data
        tool_name = data.get("name", "")

        if tool_name in _HIDDEN_TOOLS_RESULT:
            return []

        # TOOL_RESULT 映射为 TOOL_EXECUTED（保持向后兼容）
        sanitized_args = self._sanitize_args(tool_name, data.get("arguments", ""))
        sanitized_result = self._sanitize_res(tool_name, data.get("result", ""))
        return [code_generation_pb2.CodeGenerationEvent(
            agent_run_id=str(sequenced_event.agent_run_id),
            seq=sequenced_event.seq,
            event_type=common_pb2.TOOL_EXECUTED,
            tool_executed=common_pb2.ToolExecutedData(
                id=data.get("id", ""),
                name=tool_name,
                arguments=sanitized_args,
                result=sanitized_result,
            ),
        )]
