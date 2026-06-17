import logging
import time

from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.log_utils import log_model_call, log_response
from app.nodes.base import NodeMetadata, RuntimeNode
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.state import ExecutionState
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.nodes.call_model")


class CallModelNode(RuntimeNode):
    metadata = NodeMetadata(id="call_model", name="调用模型", description="调用大模型生成代码")

    async def run(
        self,
        context: ExecutionContext,
        state: ExecutionState,
        services: RuntimeServices,
    ) -> ExecutionState:
        if not state.resolved_model:
            raise AgentRuntimeError("模型配置未解析", code=AgentErrorCode.MODEL_CONFIG_MISSING)

        if not state.prompt_messages:
            raise AgentRuntimeError("提示词消息为空", code=AgentErrorCode.PROMPT_EMPTY)

        chat_model = services.chat_model_factory.create(state.resolved_model)

        lc_tools = []
        from app.tools.langchain_tools import create_all_tools
        from app.tools.file_tools import Workspace, FileTools

        workspace = Workspace(context.workspace_path)
        skill_dir = self._get_skill_dir(state)
        file_tools = FileTools(workspace, skill_dir=skill_dir)
        terminal_tools = self._create_terminal_tools(workspace)
        lc_tools = create_all_tools(file_tools, terminal_tools=terminal_tools)

        if lc_tools:
            chat_model = chat_model.bind_tools(lc_tools)

        lc_messages = []
        for msg in state.prompt_messages:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            else:
                lc_messages.append(HumanMessage(content=msg["content"]))

        start_ms = time.monotonic()
        try:
            text_content, tool_calls, response_obj = await self._stream_invoke(
                chat_model, lc_messages, services.event_bus
            )
            duration_ms = (time.monotonic() - start_ms) * 1000
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

        state.model_lc_messages = lc_messages
        state.model_response_obj = response_obj
        state.model_response_text = text_content

        if tool_calls:
            state.model_tool_calls = tool_calls
            logger.info(
                "call_model | tool_calls=%d textLen=%d duration_ms=%.0f",
                len(tool_calls),
                len(text_content),
                duration_ms,
            )
        else:
            log_response(logger, text_content, label="model_response")
            logger.info("call_model | textLen=%d duration_ms=%.0f", len(text_content), duration_ms)

        if not text_content and not tool_calls:
            raise AgentRuntimeError("模型返回为空", code=AgentErrorCode.MODEL_RESPONSE_EMPTY)

        return state

    async def _stream_invoke(self, chat_model, lc_messages, event_bus):
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

    def _create_terminal_tools(self, workspace):
        from app.core.config import settings
        from app.tools.terminal_tools import TerminalTools as TT

        allowed = [cmd.strip() for cmd in settings.terminal_allowed_commands.split(",") if cmd.strip()]
        if not allowed:
            return None
        readonly = [cmd.strip() for cmd in settings.terminal_readonly_commands.split(",") if cmd.strip()]
        return TT(
            workspace=workspace,
            allowed_commands=allowed,
            readonly_commands=readonly,
            default_timeout=settings.terminal_default_timeout,
            max_timeout=settings.terminal_max_timeout,
            max_output_bytes=settings.terminal_max_output_bytes,
        )
