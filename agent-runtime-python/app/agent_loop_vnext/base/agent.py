"""Agent 基类：封装「模型调用→工具执行→循环」的通用引擎。

子类只需定义 name/description/create_tools()/build_system_prompt()。
基类自动处理：模型解析、消息历史构建、迭代循环、工具执行、AskUser 暂停、
错误处理、事件发射。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langchain_core.messages import AIMessage, ToolMessage

from app.agent_loop_vnext.base.state import AgentRunState
from app.agent_loop_vnext.base.result import AgentResult
from app.agent_loop_vnext.shared.tools.base import AgentTool
from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.runtime.context import ExecutionContext
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.services import RuntimeServices

logger = logging.getLogger("app.agent_loop_vnext.base.agent")


class Agent(ABC):
    """Agent 基类：通用循环引擎。

    子类必须定义：
    - name / description：Agent 标识（类变量）
    - create_tools()：返回工具集（物理隔离，每 Agent 专属）
    - build_system_prompt()：返回系统提示词

    基类自动处理：
    - Workspace + FileTools 创建
    - 模型配置解析 + 模型实例化
    - 消息历史构建（HistoryBuilder）
    - 迭代循环（流式调用→工具执行→反馈→继续）
    - AskUser 暂停检测 + 事件发射
    - 错误处理 + AgentResult 返回
    """

    name: ClassVar[str]
    description: ClassVar[str]

    def __init__(self) -> None:
        self._state: AgentRunState = AgentRunState()
        self._event_bus: Any = None

    @property
    def state(self) -> AgentRunState:
        return self._state

    @abstractmethod
    def create_tools(
        self,
        file_tools: Any,
        services: RuntimeServices,
    ) -> list[AgentTool]:
        """子类返回自己的工具集。"""

    @abstractmethod
    def build_system_prompt(
        self,
        context: ExecutionContext,
        services: RuntimeServices,
    ) -> str:
        """子类构建自己的系统提示词。"""

    async def run(
        self,
        context: ExecutionContext,
        services: RuntimeServices,
    ) -> AgentResult:
        """执行 Agent 主循环。"""
        from app.tools.file_tools import FileTools, Workspace

        self._event_bus = services.event_bus
        self._state = AgentRunState()

        # 1. 创建 Workspace + FileTools
        workspace = Workspace(context.workspace_path)
        file_tools = FileTools(workspace)

        # 2. 创建工具集 + 注入 event_bus
        tools = self.create_tools(file_tools, services)
        for tool in tools:
            if hasattr(tool, "event_bus") and tool.event_bus is None:
                tool.event_bus = self._event_bus

        # 3. 解析模型配置
        await services.model_resolver.load_bundle(context)
        from app.modeling.roles import ModelRole

        resolved = services.model_resolver.resolve(ModelRole.PRIMARY)
        chat_model = services.chat_model_factory.create({
            "provider": resolved.provider,
            "modelName": resolved.model_name,
            "apiKey": resolved.api_key,
            "baseUrl": resolved.base_url,
            "timeout": settings.model_request_timeout,
        })

        # 4. 构建系统提示词
        system_prompt = self.build_system_prompt(context, services)

        # 5. 构建消息列表
        from app.agent_loop_vnext.shared.history import HistoryBuilder

        history_builder = HistoryBuilder()
        messages = await history_builder.build_messages(context, system_prompt)

        # 6. 绑定工具到模型
        chat_model_with_tools = chat_model.bind_tools(tools)

        # 7. 迭代循环
        try:
            while True:
                # 流式调用模型：文本边收边发，收集完整响应后提取 tool_calls
                text_content, tool_calls = await self._stream_model_call(
                    chat_model_with_tools, messages,
                )

                # 无 tool_calls → 模型纯文本收尾，退出循环
                if not tool_calls:
                    logger.info(
                        "model finished without tool_calls | iteration=%d agent=%s",
                        self._state.iteration,
                        self.name,
                    )
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
                logger.info(
                    "iteration completed | iteration=%d agent=%s",
                    self._state.iteration,
                    self.name,
                )

                # AskUser 触发暂停
                if self._state.status == "waiting_for_user":
                    logger.info(
                        "ask_user triggered, pausing loop | iteration=%d agent=%s",
                        self._state.iteration,
                        self.name,
                    )
                    break

            # 发射完成事件
            if self._state.status == "waiting_for_user":
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.DONE,
                    {"message": "waiting_for_user"},
                ))
            else:
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.DONE,
                    {"message": "对话完成"},
                ))

        except AgentRuntimeError as e:
            logger.error("Agent error | agent=%s error=%s", self.name, e)
            self._state.status = "failed"
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.RUNTIME_ERROR,
                {"message": str(e), "code": int(e.code)},
            ))
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.DONE,
                {"message": f"失败: {e}"},
            ))
            return AgentResult(
                status="failed",
                iteration=self._state.iteration,
                error=str(e),
                agent_name=self.name,
            )
        except Exception as e:
            logger.error(
                "Agent unexpected error | agent=%s error=%s",
                self.name,
                e,
                exc_info=True,
            )
            self._state.status = "failed"
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.RUNTIME_ERROR,
                {"message": str(e), "code": int(AgentErrorCode.INTERNAL_ERROR)},
            ))
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.DONE,
                {"message": f"异常: {e}"},
            ))
            return AgentResult(
                status="failed",
                iteration=self._state.iteration,
                error=str(e),
                agent_name=self.name,
            )

        return AgentResult(
            status=self._state.status,
            iteration=self._state.iteration,
            state=self._state if self._state.status == "waiting_for_user" else None,
            agent_name=self.name,
        )

    async def _stream_model_call(
        self,
        chat_model_with_tools: Any,
        messages: list,
    ) -> tuple[str, list[dict]]:
        """流式调用模型，文本实时发射，收集完整响应后提取 tool_calls。"""
        collected_chunks = []

        async for chunk in chat_model_with_tools.astream(messages):
            collected_chunks.append(chunk)

            # 文本内容 → 实时发射 TEXT_DELTA
            text = getattr(chunk, "content", None)
            if text:
                logger.debug("TEXT_DELTA chunk | length=%d", len(text))
                await self._event_bus.emit(RuntimeEvent(
                    RuntimeEventType.TEXT_DELTA,
                    {"text": text},
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

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        tools: list,
        messages: list,
    ) -> None:
        """执行工具调用，发射事件，追加 ToolMessage 到消息列表。"""
        import time

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"]

            # 参数摘要：记录参数名和值长度，不记录完整内容
            args_summary = {
                k: (v if len(str(v)) < 100 else str(v)[:100] + "...")
                for k, v in tool_args.items()
            }
            logger.info(
                "tool_call | name=%s id=%s args=%s agent=%s",
                tool_name,
                tool_id,
                args_summary,
                self.name,
            )

            # 发射 TOOL_CALL 事件
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.TOOL_CALL,
                {"id": tool_id, "name": tool_name, "arguments": tool_args},
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
                        logger.error(
                            "tool unexpected error | name=%s error=%s",
                            tool_name,
                            e,
                            exc_info=True,
                        )
                    break

            if not tool_found:
                result = f"未知工具: {tool_name}"
                logger.error("unknown tool | name=%s", tool_name)

            duration_ms = int((time.monotonic() - start_ms) * 1000)
            result_len = len(result) if result else 0
            result_status = (
                "ok"
                if tool_found and not result.startswith("工具执行失败:")
                else "error"
            )

            # INFO：摘要（耗时、结果长度、状态）
            logger.info(
                "tool_result | name=%s duration=%dms result_len=%d status=%s",
                tool_name,
                duration_ms,
                result_len,
                result_status,
            )

            # 发射 TOOL_RESULT 事件
            await self._event_bus.emit(RuntimeEvent(
                RuntimeEventType.TOOL_RESULT,
                {"id": tool_id, "name": tool_name, "result": result},
            ))

            # 追加 ToolMessage 到消息列表（让模型看到工具结果）
            messages.append(ToolMessage(
                content=result,
                tool_call_id=tool_id,
            ))
