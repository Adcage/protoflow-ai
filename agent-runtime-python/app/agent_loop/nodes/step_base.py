import json
import logging
import time
from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_core.tools import BaseTool

from app.agent_loop.state import AgentLoopState
from app.agent_loop.message_builder import build_llm_messages
from app.agent_loop.tool_resolver import ResolvedToolSet
from app.agent_loop.tool_policy import AgentMode
from app.agent_loop.tools.ask_user import AskUserTool
from app.agent_loop.tools.finish_tool import FinishTool
from app.agent_loop.tools.request_replan import RequestReplanTool
from app.agent_loop.tools.select_skill import SelectSkillTool
from app.agent_loop.tools.write_plan import WritePlanTool
from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.log_utils import log_model_call, log_response, log_tool_call
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices
from app.tools.file_tools import Workspace, FileTools
from app.tools.terminal_tools import TerminalTools

logger = logging.getLogger("app.agent_loop.nodes.step_base")


def _get_skill_dir(state: AgentLoopState) -> str | None:
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


def _get_assets_dir(state: AgentLoopState) -> str | None:
    try:
        index = getattr(state, "_asset_index", None)
        if index is None:
            return None
        bundled_root = getattr(index, "bundled_root", None)
        if bundled_root is None:
            return None
        return str(bundled_root)
    except Exception:
        return None


def _create_terminal_tools_for_mode(
    workspace: Workspace, readonly: bool, allowed_script_dirs: list[str] | None = None
) -> TerminalTools | None:
    allowed = [cmd.strip() for cmd in settings.terminal_allowed_commands.split(",") if cmd.strip()]
    if not allowed:
        return None
    readonly_cmds = [
        cmd.strip() for cmd in settings.terminal_readonly_commands.split(",") if cmd.strip()
    ]
    return TerminalTools(
        workspace=workspace,
        allowed_commands=allowed,
        readonly_commands=readonly_cmds,
        allowed_script_dirs=allowed_script_dirs,
        default_timeout=settings.terminal_default_timeout,
        max_timeout=settings.terminal_max_timeout,
        max_output_bytes=settings.terminal_max_output_bytes,
    )


def _make_loop_tools(state: AgentLoopState, event_bus) -> list[BaseTool]:
    ask = AskUserTool()
    ask.set_state(state)
    ask.set_event_bus(event_bus)
    finish = FinishTool()
    finish.set_state(state)
    request_replan = RequestReplanTool()
    request_replan.set_state(state)
    select_skill = SelectSkillTool()
    select_skill.set_state(state)
    write_plan = WritePlanTool()
    write_plan.set_state(state)
    return [write_plan, select_skill, ask, finish, request_replan]


def _serialize_tool_arguments(arguments: Any) -> str:
    """把工具调用参数序列化为合法 JSON 字符串。

    早期实现用 ``str(dict)`` 产生 Python repr（单引号），不是合法 JSON，
    导致下游 event_mapper / Java 无法 json.loads，工具参数（含文件路径）丢失，
    进而使 read_file 的完整文件内容、run_checks 的多行校验结果被原样追加进
    持久化消息，刷新时泄漏到对话气泡。这里统一用 json.dumps 输出标准 JSON。
    """
    if arguments is None:
        return "{}"
    if isinstance(arguments, str):
        # 已经是字符串：校验是否为合法 JSON，是则原样返回，否则尝试再兜底
        try:
            json.loads(arguments)
            return arguments
        except (json.JSONDecodeError, ValueError):
            return json.dumps({"raw": arguments}, ensure_ascii=False)
    try:
        return json.dumps(arguments, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


async def _execute_single_step(
    state: AgentLoopState,
    context: ExecutionContext,
    services: RuntimeServices,
    system_prompt: str,
    toolset: ResolvedToolSet,
    file_tools: FileTools,
) -> AgentLoopState:
    if not state.resolved_model:
        state.status = "failed"
        return state

    effective_tools = list(toolset.tools)
    chat_model = services.chat_model_factory.create(state.resolved_model)
    chat_model = chat_model.bind_tools(effective_tools)

    lc_messages = build_llm_messages(system_prompt, context, state)

    start_ms = time.monotonic()
    try:
        text_content, tool_calls, response_obj = await _stream_invoke(
            chat_model, lc_messages, services.event_bus
        )
        duration_ms = (time.monotonic() - start_ms) * 1000
    except AgentRuntimeError:
        raise
    except Exception as e:
        duration_ms = (time.monotonic() - start_ms) * 1000
        log_model_call(logger, "", "", duration_ms)
        state.status = "failed"
        await services.event_bus.emit(
            RuntimeEvent(
                RuntimeEventType.RUNTIME_ERROR,
                {"message": str(e), "code": int(AgentErrorCode.MODEL_CALL_FAILED)},
            )
        )
        return state

    log_model_call(
        logger,
        state.resolved_model.get("provider", ""),
        state.resolved_model.get("modelName", ""),
        duration_ms,
    )

    if not text_content and not tool_calls:
        state.status = "failed"
        return state

    if text_content:
        log_response(logger, text_content, label="model_response")

    if tool_calls:
        for tc in tool_calls:
            await services.event_bus.emit(
                RuntimeEvent(
                    RuntimeEventType.TOOL_CALL,
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": _serialize_tool_arguments(tc["arguments"]),
                    },
                )
            )

            start_tool = time.monotonic()
            try:
                toolset.require(tc["name"])
                result = await toolset.invoke(tc["name"], tc["arguments"])
                duration_tool = (time.monotonic() - start_tool) * 1000
                log_tool_call(logger, tc["name"], duration_tool, status="ok")

                if tc["name"] == "write_file" and "relative_path" in tc["arguments"]:
                    path = tc["arguments"]["relative_path"]
                    state.files_touched.append(path)
                    if toolset.mode == AgentMode.IMPLEMENT:
                        if path not in state.implement_phase_files:
                            state.implement_phase_files.append(path)

                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.TOOL_RESULT,
                        {"id": tc["id"], "name": tc["name"], "result": result},
                    )
                )

                from app.runtime.state import ToolCallRecord

                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=tc["id"], name=tc["name"], arguments=tc["arguments"], result=result
                    )
                )
            except Exception as e:
                duration_tool = (time.monotonic() - start_tool) * 1000
                log_tool_call(logger, tc["name"], duration_tool, status="error")
                state.status = "failed"
                from app.runtime.state import ToolCallRecord

                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                        result=None,
                        error=str(e),
                    )
                )
                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.RUNTIME_ERROR,
                        {
                            "message": f"工具执行失败 [{tc['name']}]: {e}",
                            "code": int(AgentErrorCode.TOOL_CALL_FAILED),
                        },
                    )
                )
    state.model_response_text = text_content
    state.iteration += 1

    ago_state = state
    await services.event_bus.emit(
        RuntimeEvent(
            RuntimeEventType.AGENT_LOOP_ITERATION,
            {"iteration": ago_state.iteration, "mode": ago_state.mode},
        )
    )

    return state


async def _stream_invoke(chat_model, lc_messages, event_bus):
    collected_chunks: list[AIMessageChunk] = []
    async for chunk in chat_model.astream(lc_messages):
        collected_chunks.append(chunk)
        delta = chunk.content or ""
        if delta:
            await event_bus.emit(RuntimeEvent(RuntimeEventType.TEXT_DELTA, {"text": delta}))

    if not collected_chunks:
        return "", [], None

    full_response = collected_chunks[0]
    for c in collected_chunks[1:]:
        full_response = full_response + c

    text_content = full_response.content or ""
    tool_calls = []
    if full_response.tool_calls:
        tool_calls = [
            {"id": tc["id"], "name": tc["name"], "arguments": tc["args"]}
            for tc in full_response.tool_calls
        ]

    return text_content, tool_calls, full_response
