import json
import logging
import time

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.log_utils import log_tool_call, log_model_call, log_response
from app.nodes.base import NodeMetadata, RuntimeNode
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState, ToolCallRecord
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.terminal_tools import TerminalTools
from app.core.config import settings

logger = logging.getLogger("app.nodes.execute_tools")


class ExecuteToolsNode(RuntimeNode):
    metadata = NodeMetadata(
        id="execute_tools", name="执行工具", description="执行模型请求的工具调用"
    )

    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        workspace = Workspace(context.workspace_path)
        skill_dir = self._get_skill_dir(state)
        file_tools = FileTools(workspace, skill_dir=skill_dir)
        terminal_tools = self._create_terminal_tools(workspace)
        tool_handlers = self._build_tool_handlers(file_tools, terminal_tools)

        max_rounds = 5
        for _round in range(max_rounds):
            if state.model_tool_calls:
                tool_calls_to_execute = state.model_tool_calls
                state.model_tool_calls = []
                state = await self._execute_tool_calls(
                    state, tool_calls_to_execute, services, tool_handlers
                )
                if not state.model_lc_messages or not state.model_response_obj:
                    break
                state = await self._continue_conversation(context, state, services, file_tools, terminal_tools)
                continue

            if state.model_response_text:
                return await self._execute_json_output(context, state, services, file_tools)

            logger.info("execute_tools | nothing to execute")
            break

        return state

    def _get_skill_dir(self, state: ExecutionState) -> str | None:
        try:
            caps = getattr(state, "selected_capabilities", None)
            if caps is None:
                return None
            skill = getattr(caps, "skill", None)
            if skill is None:
                return None
            return str(skill.source_path.parent)
        except Exception:
            return None

    def _create_terminal_tools(self, workspace: Workspace) -> TerminalTools | None:
        allowed = [cmd.strip() for cmd in settings.terminal_allowed_commands.split(",") if cmd.strip()]
        if not allowed:
            return None
        readonly = [cmd.strip() for cmd in settings.terminal_readonly_commands.split(",") if cmd.strip()]
        return TerminalTools(
            workspace=workspace,
            allowed_commands=allowed,
            readonly_commands=readonly,
            default_timeout=settings.terminal_default_timeout,
            max_timeout=settings.terminal_max_timeout,
            max_output_bytes=settings.terminal_max_output_bytes,
        )

    def _build_tool_handlers(self, file_tools: FileTools, terminal_tools: TerminalTools | None) -> dict:
        handlers = {
            "write_file": file_tools.write_file,
            "read_file": file_tools.read_file,
            "read_dir": file_tools.read_dir,
        }
        if terminal_tools is not None:
            handlers["run_command"] = terminal_tools.run_command
        return handlers

    async def _execute_tool_calls(
        self,
        state: ExecutionState,
        tool_calls: list[dict],
        services: RuntimeServices,
        tool_handlers: dict,
    ) -> ExecutionState:
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]
            tool_id = tc["id"]
            frontend_args = _to_frontend_args(tool_name, tool_args)

            await services.event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.TOOL_CALL,
                    {
                        "id": tool_id,
                        "name": tool_name,
                        "arguments": json.dumps(frontend_args, ensure_ascii=False),
                    },
                )
            )

            start_ms = time.monotonic()
            try:
                result = await self._invoke_tool(tool_handlers, tool_name, tool_args)
                duration_ms = (time.monotonic() - start_ms) * 1000
                log_tool_call(
                    logger,
                    tool_name,
                    duration_ms,
                    args_length=len(json.dumps(tool_args)),
                    result_length=len(result),
                    status="ok",
                )

                record = ToolCallRecord(
                    id=tool_id, name=tool_name, arguments=tool_args, result=result
                )
                state.executed_tool_calls.append(record)

                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.TOOL_RESULT,
                        {
                            "id": tool_id,
                            "name": tool_name,
                            "arguments": json.dumps(frontend_args, ensure_ascii=False),
                            "result": result,
                        },
                    )
                )

                if tool_name == "write_file" and "relative_path" in tool_args:
                    state.files_touched.append(tool_args["relative_path"])

            except Exception as e:
                duration_ms = (time.monotonic() - start_ms) * 1000
                log_tool_call(logger, tool_name, duration_ms, status="error")

                record = ToolCallRecord(
                    id=tool_id, name=tool_name, arguments=tool_args, error=str(e)
                )
                state.executed_tool_calls.append(record)
                state.errors.append(f"工具执行失败 [{tool_name}]: {e}")

                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.RUNTIME_ERROR,
                        {
                            "message": _sanitize_error_message(f"工具执行失败 [{tool_name}]: {e}"),
                            "code": int(AgentErrorCode.TOOL_CALL_FAILED),
                        },
                    )
                )
                if tool_name == "write_file":
                    break
                continue

        return state

    async def _execute_json_output(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
        file_tools: FileTools,
    ) -> ExecutionState:
        try:
            output = self._parse_json_output(state.model_response_text)
        except AgentRuntimeError:
            logger.info("model output is not JSON, skipping tool execution")
            return state

        message = output.get("message", "")
        files = output.get("files", [])

        if message:
            await services.event_bus.emit(
                RuntimeEvent(RuntimeEventType.TEXT_DELTA, {"text": message})
            )

        for i, file_item in enumerate(files):
            path = file_item.get("path", "")
            content = file_item.get("content", "")
            if not path:
                continue

            tool_id = f"json_write_{i}"
            args = {"relativeFilePath": path, "relative_path": path, "content": content}

            await services.event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.TOOL_CALL,
                    {
                        "id": tool_id,
                        "name": "write_file",
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                )
            )

            try:
                result = await file_tools.write_file(path, content)

                record = ToolCallRecord(
                    id=tool_id, name="write_file", arguments=args, result=result
                )
                state.executed_tool_calls.append(record)
                state.files_touched.append(path)

                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.TOOL_RESULT,
                        {
                            "id": tool_id,
                            "name": "write_file",
                            "arguments": json.dumps({"relativeFilePath": path}, ensure_ascii=False),
                            "result": result,
                        },
                    )
                )

            except Exception as e:
                state.errors.append(f"文件写入失败 [{path}]: {e}")
                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.RUNTIME_ERROR,
                        {
                            "message": _sanitize_error_message(f"文件写入失败 [{path}]: {e}"),
                            "code": int(AgentErrorCode.TOOL_CALL_FAILED),
                        },
                    )
                )
                break

        return state

    async def _invoke_tool(self, tool_handlers: dict, name: str, args: dict) -> str:
        handler = tool_handlers.get(name)
        if handler is None:
            raise AgentRuntimeError(f"未知工具: {name}", code=AgentErrorCode.TOOL_CALL_FAILED)
        return await handler(**args)

    def _parse_json_output(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise AgentRuntimeError("模型输出不是有效 JSON", code=AgentErrorCode.TOOL_CALL_FAILED)

    async def _continue_conversation(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
        file_tools: FileTools,
        terminal_tools: TerminalTools | None,
    ) -> ExecutionState:
        if not state.model_lc_messages or not state.model_response_obj:
            return state

        from langchain_core.messages import AIMessageChunk, ToolMessage
        from app.tools.langchain_tools import create_all_tools

        lc_messages = list(state.model_lc_messages)
        ai_msg = state.model_response_obj
        lc_messages.append(ai_msg)

        executed = [
            r for r in state.executed_tool_calls if r.result is not None or r.error is not None
        ]
        if not executed:
            return state

        for record in executed:
            tool_result = record.result if record.error is None else f"ERROR: {record.error}"
            lc_messages.append(ToolMessage(content=tool_result, tool_call_id=record.id))

        chat_model = services.chat_model_factory.create(state.resolved_model)
        lc_tools = create_all_tools(file_tools, terminal_tools=terminal_tools)
        if lc_tools:
            chat_model = chat_model.bind_tools(lc_tools)

        start_ms = time.monotonic()
        try:
            collected_chunks: list[AIMessageChunk] = []
            async for chunk in chat_model.astream(lc_messages):
                collected_chunks.append(chunk)
                delta = chunk.content or ""
                if delta:
                    await services.event_bus.emit(
                        RuntimeEvent(RuntimeEventType.TEXT_DELTA, {"text": delta})
                    )

            if not collected_chunks:
                raise AgentRuntimeError("模型返回为空", code=AgentErrorCode.MODEL_RESPONSE_EMPTY)

            full_response = collected_chunks[0]
            for c in collected_chunks[1:]:
                full_response = full_response + c

            duration_ms = (time.monotonic() - start_ms) * 1000
        except AgentRuntimeError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_ms) * 1000
            log_model_call(
                logger,
                state.resolved_model.get("provider", ""),
                state.resolved_model.get("modelName", ""),
                duration_ms,
            )
            raise AgentRuntimeError(
                f"模型调用失败: {e}", code=AgentErrorCode.MODEL_CALL_FAILED
            ) from e

        log_model_call(
            logger,
            state.resolved_model.get("provider", ""),
            state.resolved_model.get("modelName", ""),
            duration_ms,
        )

        text_content = full_response.content or ""
        state.model_response_text = text_content
        state.model_lc_messages = lc_messages
        state.model_response_obj = full_response

        if full_response.tool_calls:
            state.model_tool_calls = [
                {"id": tc["id"], "name": tc["name"], "arguments": tc["args"]}
                for tc in full_response.tool_calls
            ]
            logger.info(
                "continue_conversation | tool_calls=%d textLen=%d duration_ms=%.0f",
                len(full_response.tool_calls),
                len(text_content),
                duration_ms,
            )
        else:
            log_response(logger, text_content, label="model_response")
            logger.info(
                "continue_conversation | textLen=%d duration_ms=%.0f",
                len(text_content),
                duration_ms,
            )
            state.model_tool_calls = []

        return state


def _to_frontend_args(tool_name: str, args: dict) -> dict:
    mapped = dict(args)
    if "relative_path" in mapped:
        if tool_name == "read_dir":
            mapped["relativeDirPath"] = mapped["relative_path"]
            mapped.pop("relative_path", None)
        else:
            mapped["relativeFilePath"] = mapped["relative_path"]
            mapped.pop("relative_path", None)
    if "content" in mapped:
        content = mapped["content"]
        mapped["contentLength"] = len(content) if isinstance(content, str) else 0
        mapped.pop("content", None)
    return mapped


def _sanitize_error_message(message: str) -> str:
    import re

    sanitized = re.sub(r"[A-Za-z]:\\[^\s;,\]]+", "[路径已隐藏]", message)
    sanitized = re.sub(r"/home/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/var/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/tmp/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/opt/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    sanitized = re.sub(r"/usr/[^\s;,\]]+", "[路径已隐藏]", sanitized)
    return sanitized
