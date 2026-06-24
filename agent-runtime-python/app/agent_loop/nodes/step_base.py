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


# 工具错误码中，根因属于模型决策而非运行时故障的，应当作为可观察的 tool result
# 返回给模型，让它自行修正（换工具、修正参数等），而不是终止整次 run。
# STATE_ERROR：状态机门禁拒绝（错误阶段调用提交工具），模型可换本阶段允许的工具重试
# TOOL_ARGS_ERROR：参数校验失败，模型可修正参数后重试
# TOOL_CALL_FAILED：工具执行失败（如资源不存在等），模型可换路径或跳过
# SKILL_RESOURCE_NOT_FOUND / SKILL_RESOURCE_READ_FAILED：Skill 资源读取失败，模型可换资源
#
# 以下工具错误码虽然也属于 62xxx 范围，但涉及安全策略，不得作为可恢复错误：
# PATH_TRAVERSAL_BLOCKED(62004), COMMAND_NOT_ALLOWED(62005),
# COMMAND_INJECTION_BLOCKED(62007) — 安全拦截必须终止 run。
_RECOVERABLE_TOOL_ERROR_CODES: frozenset[int] = frozenset(
    {
        int(AgentErrorCode.STATE_ERROR),
        int(AgentErrorCode.TOOL_ARGS_ERROR),
        int(AgentErrorCode.TOOL_CALL_FAILED),
        int(AgentErrorCode.SKILL_RESOURCE_NOT_FOUND),
        int(AgentErrorCode.SKILL_RESOURCE_READ_FAILED),
    }
)

_UNRECOVERABLE_SECURITY_ERROR_CODES: frozenset[int] = frozenset(
    {
        int(AgentErrorCode.PATH_TRAVERSAL_BLOCKED),
        int(AgentErrorCode.COMMAND_NOT_ALLOWED),
        int(AgentErrorCode.COMMAND_INJECTION_BLOCKED),
    }
)


def _classify_tool_error(error: BaseException) -> tuple[bool, int]:
    """把工具执行异常分类为可恢复 / 不可恢复。

    安全拦截（路径穿越、命令注入等）永远不可恢复，必须终止 run。
    其他 AgentRuntimeError 按可恢复白名单判断。
    可恢复错误由模型自身行为造成，应当让模型通过观察 tool result 自行修正；
    不可恢复错误必须终止 run 并上报 RUNTIME_ERROR。

    Returns:
        (is_recoverable, error_code)。error_code 是归一化后的 int。
    """
    if isinstance(error, AgentRuntimeError):
        code = int(getattr(error, "code", AgentErrorCode.INTERNAL_ERROR))
        if code in _UNRECOVERABLE_SECURITY_ERROR_CODES:
            return False, code
        if code in _RECOVERABLE_TOOL_ERROR_CODES:
            return True, code
    return False, int(AgentErrorCode.INTERNAL_ERROR)


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
    """返回当前 Agent Loop 使用的 loop 工具集合。

    Phase 3 后：
    - 真实写入逻辑由 plan_tools 提供的 state 提交工具完成；
    - 旧 select_skill / write_plan / ask_user 工具仅作为薄兼容入口，
      通过 delegate 委托到新工具，确保状态机门禁统一；
    - finish / request_replan 行为不变。
    """
    from app.agent_loop.tools.ask_user import AskUserTool
    from app.agent_loop.tools.complete_implementation import CompleteImplementationTool
    from app.agent_loop.tools.confirm_generation_mode import ConfirmGenerationModeTool
    from app.agent_loop.tools.plan_tools import (
        ChooseSkillTool,
        ConfirmDesignTool,
        PlanStageGuardTool,
        ProposeDesignTool,
        RecordProjectInspectionTool,
        SubmitRequirementBriefTool,
        WriteImplementationPlanTool,
    )
    from app.agent_loop.tools.request_replan import RequestReplanTool
    from app.agent_loop.tools.select_skill import SelectSkillTool
    from app.agent_loop.tools.submit_validation_report import SubmitValidationReportTool
    from app.agent_loop.tools.write_plan import WritePlanTool

    ask = AskUserTool()
    ask.set_state(state)
    ask.set_event_bus(event_bus)

    complete_impl = CompleteImplementationTool()
    complete_impl.set_state(state)
    request_replan = RequestReplanTool()
    request_replan.set_state(state)
    submit_validation = SubmitValidationReportTool()
    submit_validation.set_state(state)

    submit_brief = SubmitRequirementBriefTool()
    submit_brief.set_state(state)
    record_inspection = RecordProjectInspectionTool()
    record_inspection.set_state(state)
    choose_skill = ChooseSkillTool()
    choose_skill.set_state(state)
    propose_design = ProposeDesignTool()
    propose_design.set_state(state)
    confirm_design = ConfirmDesignTool()
    confirm_design.set_state(state)
    write_impl_plan = WriteImplementationPlanTool()
    write_impl_plan.set_state(state)
    plan_guard = PlanStageGuardTool()
    plan_guard.set_state(state)

    confirm_gen_mode = ConfirmGenerationModeTool()
    confirm_gen_mode.set_state(state)

    # 兼容旧 select_skill 入口：delegate 给 ChooseSkillTool
    select_skill = SelectSkillTool()
    select_skill.set_state(state)
    select_skill.set_delegate(choose_skill._arun)

    # 兼容旧 write_plan 入口：delegate 给 WriteImplementationPlanTool
    write_plan = WritePlanTool()
    write_plan.set_state(state)
    write_plan.set_delegate(write_impl_plan._arun)

    return [
        submit_brief,
        record_inspection,
        choose_skill,
        propose_design,
        confirm_design,
        write_impl_plan,
        plan_guard,
        confirm_gen_mode,
        select_skill,
        write_plan,
        ask,
        complete_impl,
        submit_validation,
        request_replan,
    ]


def _count_consecutive_writes(state: AgentLoopState, path: str) -> int:
    """统计同一文件累计成功写入次数（不限连续），用于拦截模型反复重写同一文件陷入循环。"""
    if not path:
        return 0
    count = 0
    for record in state.executed_tool_calls:
        if record.name != "write_file":
            continue
        rec_path = (record.arguments or {}).get("relative_path", "")
        if rec_path == path and not record.error:
            count += 1
    return count


def _append_system_message(state: AgentLoopState, content: str) -> None:
    """向 state.conversation_messages 追加一条 system 消息（容忍 None/缺失）。"""
    if not hasattr(state, "conversation_messages") or state.conversation_messages is None:
        state.conversation_messages = []
    state.conversation_messages.append({"role": "system", "content": content})


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
        from app.runtime.state import ToolCallRecord

        for tc in tool_calls:
            is_write_file = (
                tc["name"] == "write_file" and "relative_path" in tc["arguments"]
            )
            target_path = tc["arguments"].get("relative_path") if is_write_file else None
            consecutive_before = (
                _count_consecutive_writes(state, target_path) if target_path else 0
            )

            if is_write_file and consecutive_before >= 3:
                error_msg = (
                    f"系统拦截：{target_path} 已累计成功写入 {consecutive_before} 次，"
                    f"禁止继续重写同一文件以避免循环。"
                    f"请改用其他动作之一：\n"
                    f"1. 写入项目规则要求的其他待生成文件\n"
                    f"2. 提交当前阶段的完成结果\n"
                    f"3. 如确有必要，先读取当前文件内容确认现状后再判断"
                )
                log_tool_call(logger, tc["name"], 0.0, status="blocked")

                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                        result=None,
                        error=error_msg,
                    )
                )
                await services.event_bus.emit(
                    RuntimeEvent(
                        RuntimeEventType.TOOL_RESULT,
                        {
                            "id": tc["id"],
                            "name": tc["name"],
                            "result": error_msg,
                            "is_error": True,
                        },
                    )
                )
                _append_system_message(state, error_msg)
                continue

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

                if is_write_file:
                    path = target_path
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

                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=tc["id"], name=tc["name"], arguments=tc["arguments"], result=result
                    )
                )

                if is_write_file:
                    path = target_path
                    consecutive_after = _count_consecutive_writes(state, path)
                    if consecutive_after == 2:
                        warning = (
                            f"系统提示：{path} 已累计成功写入 {consecutive_after} 次。"
                            f"再写一次将被系统拦截。"
                            f"建议：除非这次重写带来明确的功能扩展、"
                            f"bug 修复或显著优化（不是微调），"
                            f"否则请改用其他动作：写入其他待生成文件或提交完成结果。"
                        )
                        _append_system_message(state, warning)
            except Exception as e:
                duration_tool = (time.monotonic() - start_tool) * 1000
                log_tool_call(logger, tc["name"], duration_tool, status="error")
                is_recoverable, _ = _classify_tool_error(e)

                state.executed_tool_calls.append(
                    ToolCallRecord(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=tc["arguments"],
                        result=None,
                        error=str(e),
                    )
                )

                if is_recoverable:
                    # 状态机门禁 / 参数校验等可恢复错误：把错误作为 tool result
                    # 返回给模型，让它在同一轮里换工具或修正参数后重试；
                    # 不修改 state.status，不发 RUNTIME_ERROR，整次 run 继续。
                    await services.event_bus.emit(
                        RuntimeEvent(
                            RuntimeEventType.TOOL_RESULT,
                            {
                                "id": tc["id"],
                                "name": tc["name"],
                                "result": str(e),
                                "is_error": True,
                            },
                        )
                    )
                    _append_system_message(
                        state,
                        f"工具 {tc['name']} 在当前阶段/参数不被接受：{e}。"
                        f"请使用本阶段允许的工具或修正参数后重试，不要直接结束对话。",
                    )
                    continue

                state.status = "failed"
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

    state.record_state_change()

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

    if text_content and not tool_calls:
        await event_bus.emit(RuntimeEvent(RuntimeEventType.TEXT_DELTA, {"text": text_content}))
    elif text_content and tool_calls:
        logger.debug(
            "internal model text suppressed before tool call | length=%d",
            len(text_content),
        )

    return text_content, tool_calls, full_response
