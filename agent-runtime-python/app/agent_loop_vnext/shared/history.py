"""对话历史构建器，将 chat_history 转为 LangChain 消息列表。

支持多模态消息：图片附件转为 image_url content block，
非图片附件提取文本后追加到消息内容。
"""

import base64
import logging

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent_loop_vnext.shared.file_processor import FileProcessor
from app.runtime.context import AttachmentInfo, ChatHistoryEntry, ExecutionContext

logger = logging.getLogger("app.agent_loop_vnext.history")

# 非图片附件总文本上限
_MAX_TOTAL_TEXT_LENGTH = 100_000


class HistoryBuilder:
    """对话历史构建器，将 chat_history 转为 LangChain 消息列表。"""

    def __init__(self) -> None:
        self._file_processor = FileProcessor()

    async def build_messages(
        self,
        context: ExecutionContext,
        system_prompt: str,
    ) -> list[BaseMessage]:
        """构建完整的 LLM 输入消息列表。"""
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        # 注入对话历史
        history = self._history_before_current(context)
        for entry in history:
            messages.append(await self._message_from_role(entry.role, entry.content, entry.attachments))

        # 注入当前用户消息（含附件）
        if context.prompt or context.attachments:
            messages.append(await self._build_user_message(context.prompt, context.attachments))

        return messages

    def _history_before_current(self, context: ExecutionContext) -> list[ChatHistoryEntry]:
        """返回当前消息之前的历史，去除与当前 prompt 重复的最后一条。"""
        history = list(context.chat_history)
        if not history:
            return history
        latest = history[-1]
        if latest.role.strip().lower() in {"user", "human"}:
            if context.prompt and latest.content == context.prompt:
                history.pop()
        return history

    async def _message_from_role(
        self,
        role: str,
        content: str,
        attachments: tuple[AttachmentInfo, ...] = (),
    ) -> BaseMessage:
        """将数据库 role 字符串转为 LangChain 消息类型。"""
        normalized = role.strip().lower()
        if normalized in {"assistant", "ai"}:
            return AIMessage(content=content)
        # vNext resume 答案渲染（自包含，不依赖 legacy）
        if "<<RESUME_ANSWERS>>" in content:
            from app.agent_loop_vnext.shared.resume_answers import render_resume_answer_text
            content = render_resume_answer_text(content)
        # 用户消息可能包含附件
        if attachments:
            return await self._build_user_message(content, attachments)
        return HumanMessage(content=content)

    async def _build_user_message(
        self,
        text: str,
        attachments: tuple[AttachmentInfo, ...],
    ) -> HumanMessage:
        """构造包含附件的多模态 HumanMessage。"""
        content_parts: list[dict] = []
        if text:
            content_parts.append({"type": "text", "text": text})

        total_text_len = 0
        for att in attachments:
            if att.mime_type.startswith("image/"):
                image_data = await self._resolve_image(att)
                if image_data:
                    content_parts.append(image_data)
            else:
                doc_text = await self._resolve_document(att)
                if doc_text:
                    # 总文本上限控制
                    if total_text_len + len(doc_text) <= _MAX_TOTAL_TEXT_LENGTH:
                        content_parts.append({"type": "text", "text": doc_text})
                        total_text_len += len(doc_text)
                    else:
                        remaining = _MAX_TOTAL_TEXT_LENGTH - total_text_len
                        if remaining > 100:
                            content_parts.append({"type": "text", "text": doc_text[:remaining] + "\n[...截断]"})
                            total_text_len = _MAX_TOTAL_TEXT_LENGTH
                        break

        if not content_parts:
            return HumanMessage(content=text or "")

        return HumanMessage(content=content_parts)

    async def _resolve_image(self, att: AttachmentInfo) -> dict | None:
        """解析图片附件为 image_url content block。"""
        try:
            if att.storage_type == "cos":
                # COS: 直接传公网 URL
                return {"type": "image_url", "image_url": {"url": att.url}}
            else:
                # 本地存储: 从 Java HTTP 接口拉取，转 Base64 data URL
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(att.url)
                    if resp.status_code == 200:
                        b64 = base64.b64encode(resp.content).decode()
                        data_url = f"data:{att.mime_type};base64,{b64}"
                        return {"type": "image_url", "image_url": {"url": data_url}}
                    else:
                        logger.warning("拉取图片失败: status=%d url=%s", resp.status_code, att.url)
        except Exception as e:
            logger.warning("拉取图片异常: %s | file=%s", e, att.file_name)
        return None

    async def _resolve_document(self, att: AttachmentInfo) -> str | None:
        """拉取非图片附件内容并提取文本。"""
        try:
            content_bytes: bytes | None = None

            if att.storage_type == "cos":
                # COS: 直接从公网 URL 下载
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(att.url)
                    if resp.status_code == 200:
                        content_bytes = resp.content
            else:
                # 本地存储: 从 Java HTTP 接口拉取
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(att.url)
                    if resp.status_code == 200:
                        content_bytes = resp.content

            if not content_bytes:
                logger.warning("拉取文件失败: url=%s", att.url)
                return f"[文件: {att.file_name} — 加载失败]"

            return self._file_processor.extract_text(content_bytes, att.mime_type, att.file_name)
        except Exception as e:
            logger.warning("拉取文件异常: %s | file=%s", e, att.file_name)
            return f"[文件: {att.file_name} — 加载失败]"
