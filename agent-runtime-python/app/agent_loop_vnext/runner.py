"""vNext 单实现链路 Runner — 迭代循环 + 工具调用。

核心职责：
1. 创建 Workspace/FileTools
2. 解析模型配置、初始化 RAG
3. 构建系统提示词（ImplementorPromptBuilder）
4. 构建消息列表（HistoryBuilder）
5. 绑定工具到模型
6. 迭代循环：流式调用模型 → 文本实时发射 → 收集 tool_calls → 执行工具 → 结果反馈模型 → 继续循环
7. 退出条件：模型无 tool_calls（纯文本收尾）
"""

import logging

from langchain_core.messages import AIMessage, ToolMessage

from app.agent_loop_vnext.state import SingleImplementState
from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.agent_loop_vnext.runner")


class SingleImplementLoopRunner:
    """vNext 单实现链路运行器。"""

    AGENT_NAME = "implementor"

    def __init__(self, context: ExecutionContext, services: RuntimeServices) -> None:
        self._context = context
        self._services = services
        self._state = SingleImplementState()
        self._event_bus = services.event_bus
        self._accumulated_text: str = ""  # 累积 AI 回复文本（供 complete_agent_run 兜底保存）

    @property
    def state(self) -> SingleImplementState:
        return self._state

    async def run(self) -> None:
        """执行 vNext 迭代循环。"""
        from app.tools.file_tools import FileTools, Workspace

        await self._event_bus.emit(RuntimeEvent(
            RuntimeEventType.AGENT_START,
            {"agent_name": self.AGENT_NAME},
        ))

        # 1. 创建 Workspace（从 context.workspace_path，Java 传入）
        workspace = Workspace(self._context.workspace_path)
        file_tools = FileTools(workspace)

        # 2. 解析模型配置（必须先于 RAG 初始化和工具创建）
        await self._services.model_resolver.load_bundle(self._context)
        from app.modeling.roles import ModelRole
        resolved = self._services.model_resolver.resolve(ModelRole.PRIMARY)
        chat_model = self._services.chat_model_factory.create({
            "provider": resolved.provider,
            "modelName": resolved.model_name,
            "apiKey": resolved.api_key,
            "baseUrl": resolved.base_url,
            "timeout": settings.model_request_timeout,
        })

        # 3. RAG 服务（启动时已初始化，直接使用）
        rag_service = self._services.rag_service
        rag_enabled = rag_service is not None and rag_service.enabled

        # 4. 创建工具集（通过 LoopStrategy，ImplementorLoop 创建全量，PlaygroundLoop 可自带过滤）
        skill_registry = None
        if self._services.asset_manager is not None:
            skill_registry = self._services.asset_manager.get_index().skill_registry

        from app.agent_loop_vnext.loops import get_loop_strategy
        strategy = get_loop_strategy(
            self._context.generation_mode,
            is_test=self._context.is_test,
        )
        tools = strategy.create_tools(
            file_tools=file_tools,
            skill_registry=skill_registry,
            state=self._state,
            rag_service=rag_service if rag_enabled else None,
        )

        # Playground 模式：根据 enabled_tools 过滤工具
        enabled_tools = self._context.runtime_options.get("enabled_tools")
        if enabled_tools is not None:
            tool_name_set = set(enabled_tools)
            tools = [t for t in tools if t.name in tool_name_set]
            logger.info("playground tool filter | enabled=%s | filtered_count=%d", enabled_tools, len(tools))

        # 将 event_bus 注入需要它的工具（如 AskUserTool）
        for tool in tools:
            if hasattr(tool, 'event_bus') and tool.event_bus is None:
                tool.event_bus = self._event_bus

        # 5. 构建系统提示词（通过同一个 LoopStrategy 策略）
        system_prompt = strategy.build_system_prompt(
            context=self._context,
            state=self._state,
            tools=tools,
            skill_registry=skill_registry,
            rag_service=rag_service if rag_enabled else None,
        )

        # 5. 构建消息列表（使用 HistoryBuilder，支持附件多模态）
        from app.agent_loop_vnext.shared.history import HistoryBuilder
        history_builder = HistoryBuilder()
        messages = await history_builder.build_messages(self._context, system_prompt)

        # 6. 绑定工具到模型
        chat_model_with_tools = chat_model.bind_tools(tools)

        # 7. 迭代循环
        try:
            while True:
                # 流式调用模型：文本边收边发，收集完整响应后提取 tool_calls
                text_content, tool_calls = await self._stream_model_call(chat_model_with_tools, messages)

                # 累积 AI 回复文本（仅收尾的纯文本，工具调用中间的文本不累积）
                if not tool_calls and text_content:
                    self._accumulated_text += text_content

                # 无 tool_calls → 模型纯文本收尾，退出循环
                if not tool_calls:
                    logger.info("model finished without tool_calls | iteration=%d", self._state.iteration)
                    self._state.status = "completed"
                    break

                # 追加 AIMessage（含 tool_calls）到消息列表
                messages.append(AIMessage(
                    content=text_content or "",
                    tool_calls=tool_calls,
                ))

                # 执行工具，追加 ToolMessage 到消息列表
                await self._execute_tool_calls(tool_calls, tools, messages)

                # 递增迭代
                self._state.iteration += 1
                logger.info("iteration completed | iteration=%d", self._state.iteration)

                # AskUser 触发暂停
                if self._state.status == "waiting_for_user":
                    logger.info("ask_user triggered, pausing loop | iteration=%d", self._state.iteration)
                    break

            # 发射完成事件
            if self._state.status == "waiting_for_user":
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.DONE,
                    {"message": "waiting_for_user", "agent_name": self.AGENT_NAME},
                ))
            else:
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.DONE,
                    {"message": "对话完成", "agent_name": self.AGENT_NAME},
                ))

        except AgentRuntimeError as e:
            logger.error("vNext runner error: %s", e)
            self._state.status = "failed"
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.RUNTIME_ERROR,
                {"message": str(e), "code": int(e.code), "agent_name": self.AGENT_NAME},
            ))
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.DONE,
                {"message": f"失败: {e}", "agent_name": self.AGENT_NAME},
            ))
        except Exception as e:
            logger.error("vNext runner unexpected error: %s", e, exc_info=True)
            self._state.status = "failed"
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.RUNTIME_ERROR,
                {
                    "message": str(e),
                    "code": int(AgentErrorCode.INTERNAL_ERROR),
                    "agent_name": self.AGENT_NAME,
                },
            ))
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.DONE,
                {"message": f"异常: {e}", "agent_name": self.AGENT_NAME},
            ))

    async def _stream_model_call(self, chat_model_with_tools, messages: list) -> tuple[str, list[dict]]:
        """流式调用模型，文本实时发射，收集完整响应后提取 tool_calls。

        Returns:
            (text_content, tool_calls) — 文本内容和工具调用列表
        """
        collected_chunks = []

        async for chunk in chat_model_with_tools.astream(messages):
            collected_chunks.append(chunk)

            # 文本内容 → 实时发射 TEXT_DELTA
            text = getattr(chunk, "content", None)
            if text:
                logger.debug("TEXT_DELTA chunk | length=%d", len(text))
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.TEXT_DELTA,
                    {"text": text, "agent_name": self.AGENT_NAME},
                ))

        if not collected_chunks:
            return "", []

        # 合并所有 chunks 为完整响应
        full_response = collected_chunks[0]
        for c in collected_chunks[1:]:
            full_response = full_response + c

        text_content = full_response.content or ""

        # 从完整响应提取 tool_calls（合并后才有完整参数）
        tool_calls = []
        if hasattr(full_response, "tool_calls") and full_response.tool_calls:
            tool_calls = [
                {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                for tc in full_response.tool_calls
            ]

        return text_content, tool_calls

    async def _execute_tool_calls(self, tool_calls: list[dict], tools: list, messages: list) -> None:
        """执行工具调用，发射事件，追加 ToolMessage 到消息列表。"""
        import time

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"]

            # 参数摘要：记录参数名和值长度，不记录完整内容
            args_summary = {k: (v if len(str(v)) < 100 else str(v)[:100] + "...") for k, v in tool_args.items()}
            logger.info("tool_call | name=%s id=%s args=%s", tool_name, tool_id, args_summary)

            # 发射 TOOL_CALL 事件
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.TOOL_CALL,
                {
                    "id": tool_id,
                    "name": tool_name,
                    "arguments": tool_args,
                    "agent_name": self.AGENT_NAME,
                },
            ))

            # 查找匹配的工具并执行
            result = ""
            tool_found = False
            start_ms = time.monotonic()
            for tool in tools:
                if tool.name == tool_name:
                    tool_found = True
                    try:
                        result = await tool._arun(**tool_args)
                    except AgentRuntimeError as e:
                        result = f"工具执行失败: {e}"
                        logger.warning("tool error | name=%s error=%s", tool_name, e)
                    except Exception as e:
                        result = f"工具执行失败: {e}"
                        logger.error("tool unexpected error | name=%s error=%s", tool_name, e, exc_info=True)
                    break

            if not tool_found:
                result = f"未知工具: {tool_name}"
                logger.error("unknown tool | name=%s", tool_name)

            duration_ms = int((time.monotonic() - start_ms) * 1000)
            result_len = len(result) if result else 0
            result_status = "ok" if tool_found and not result.startswith("工具执行失败:") else "error"

            # INFO：摘要（耗时、结果长度、状态）
            logger.info(
                "tool_result | name=%s duration=%dms result_len=%d status=%s",
                tool_name, duration_ms, result_len, result_status,
            )
            # DEBUG：结果前 200 字
            logger.debug(
                "tool_result_detail | name=%s result_preview=%s",
                tool_name, (result[:200] + "...") if result_len > 200 else result,
            )

            # 发射 TOOL_RESULT 事件
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.TOOL_RESULT,
                {
                    "id": tool_id,
                    "name": tool_name,
                    "result": result,
                    "agent_name": self.AGENT_NAME,
                },
            ))

            # 追加 ToolMessage 到消息列表（让模型看到工具结果）
            messages.append(ToolMessage(
                content=result,
                tool_call_id=tool_id,
            ))
