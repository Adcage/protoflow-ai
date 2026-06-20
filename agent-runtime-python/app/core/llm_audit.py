import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles

from app.core.config import settings
from app.core.context import get_agent_run_id, get_trace_id
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("app.core.llm_audit")


@dataclass
class AuditRecord:
    trace_id: str = ""
    agent_run_id: str = ""
    timestamp: str = ""
    model: str = ""
    provider: str = ""
    base_url: str = ""
    api_key_prefix: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""


def _serialize_message(msg: Any) -> dict[str, Any]:
    role = getattr(msg, "type", "unknown")
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        content_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    content_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    content_parts.append("[image_url]")
                else:
                    content_parts.append(str(part)[:200])
            else:
                content_parts.append(str(part))
        content = "\n".join(content_parts)
    return {"role": role, "content": content}


def _extract_tools_from_kwargs(kwargs: dict) -> list[dict[str, Any]]:
    invocation_params = kwargs.get("invocation_params", {})
    if isinstance(invocation_params, dict):
        tools = invocation_params.get("tools")
        if tools and isinstance(tools, list):
            return tools
    tools_kwarg = kwargs.get("tools")
    if tools_kwarg and isinstance(tools_kwarg, list):
        return tools_kwarg
    return []


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return api_key[:2] + "***"
    return api_key[:4] + "***" + api_key[-2:]


class LlmAuditCallback(BaseCallbackHandler):
    def __init__(self, writer: "LlmAuditWriter"):
        self._writer = writer

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not self._writer.enabled:
            return

        try:
            lc_messages = messages[0] if messages else []
            serialized_messages = [_serialize_message(m) for m in lc_messages]

            tools = _extract_tools_from_kwargs(kwargs)

            invocation_params = kwargs.get("invocation_params", {})
            serialized_kwargs = serialized.get("kwargs", {}) if isinstance(serialized, dict) else {}
            model_name = ""
            base_url = ""
            api_key_prefix = ""
            provider = ""
            if isinstance(invocation_params, dict):
                model_name = invocation_params.get("model_name", "") or invocation_params.get(
                    "model", ""
                )
            if isinstance(serialized_kwargs, dict):
                base_url = serialized_kwargs.get("openai_api_base", "") or serialized_kwargs.get(
                    "base_url", ""
                )
            if isinstance(metadata, dict):
                api_key_prefix = metadata.get("llm_audit_api_key_prefix", "")
                provider = metadata.get("llm_audit_provider", "")
            if not provider:
                provider = (
                    metadata.get("ls_provider", "") if isinstance(metadata, dict) else ""
                )

            record = AuditRecord(
                trace_id=get_trace_id(),
                agent_run_id=get_agent_run_id(),
                timestamp=datetime.now(timezone.utc).isoformat(),
                model=model_name,
                base_url=base_url,
                api_key_prefix=api_key_prefix,
                messages=serialized_messages,
                tools=tools,
                source=provider,
            )

            self._writer.submit(record)
        except Exception as e:
            logger.warning("llm_audit callback error: %s", e)


class LlmAuditWriter:
    def __init__(self) -> None:
        self._enabled = settings.llm_audit_enabled
        self._base_dir = self._resolve_base_dir()
        self._queue: asyncio.Queue[AuditRecord | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._call_counter: dict[str, int] = {}
        self._first_timestamp: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _resolve_base_dir(self) -> Path:
        base_dir = Path(settings.llm_audit_dir)
        if not base_dir.is_absolute():
            base_dir = base_dir.resolve()
        return base_dir

    def get_callback(self) -> LlmAuditCallback:
        return LlmAuditCallback(self)

    def start(self) -> None:
        if not self._enabled:
            return
        self._task = asyncio.create_task(self._writer_loop())
        logger.info("llm_audit writer started | dir=%s", self._base_dir)

    async def stop(self) -> None:
        if not self._enabled or self._task is None:
            return
        await self._queue.put(None)
        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("llm_audit writer shutdown timed out")
        logger.info("llm_audit writer stopped")

    def submit(self, record: AuditRecord) -> None:
        if not self._enabled:
            return
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            logger.warning("llm_audit queue full, dropping record")

    async def _writer_loop(self) -> None:
        while True:
            record = await self._queue.get()
            if record is None:
                break
            try:
                await self._write_record(record)
            except Exception as e:
                logger.warning("llm_audit write error: %s", e)

    async def _write_record(self, record: AuditRecord) -> None:
        run_id = record.agent_run_id or record.trace_id or "unknown"

        key = str(run_id)
        if key not in self._first_timestamp:
            self._first_timestamp[key] = record.timestamp

        dt = datetime.fromisoformat(self._first_timestamp[key])
        date_str = dt.strftime("%Y-%m-%d")
        hm = dt.strftime("%H%M")
        output_dir = self._base_dir / date_str / f"{hm}_{run_id}"
        output_dir.mkdir(parents=True, exist_ok=True)

        key = str(run_id)
        seq = self._call_counter.get(key, 0) + 1
        self._call_counter[key] = seq

        json_path = output_dir / f"{seq:02d}_call.json"
        md_path = output_dir / f"{seq:02d}_call.md"

        json_data = {
            "trace_id": record.trace_id,
            "agent_run_id": record.agent_run_id,
            "timestamp": record.timestamp,
            "model": record.model,
            "provider": record.source,
            "base_url": record.base_url,
            "api_key_prefix": record.api_key_prefix,
            "messages": record.messages,
            "tools": record.tools,
        }

        async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(json_data, ensure_ascii=False, indent=2))

        md_content = self._render_md(record, seq)
        async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
            await f.write(md_content)

        if seq == 1:
            index_path = output_dir / "index.json"
            index_data = {
                "agent_run_id": record.agent_run_id,
                "trace_id": record.trace_id,
                "model": record.model,
                "timestamp": record.timestamp,
            }
            async with aiofiles.open(index_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(index_data, ensure_ascii=False, indent=2))

    def _render_md(self, record: AuditRecord, seq: int) -> str:
        lines = [
            f"# LLM Call #{seq}",
            "",
            f"**Time:** {record.timestamp} | **Model:** {record.model} | **Provider:** {record.source}",
            f"**Trace:** {record.trace_id} | **AgentRun:** {record.agent_run_id}",
            f"**Base URL:** {record.base_url} | **API Key:** {record.api_key_prefix}",
            "",
            "---",
            "",
            f"## Messages ({len(record.messages)})",
            "",
        ]

        for i, msg in enumerate(record.messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"### [{i + 1}] {role} ({len(content)} 字符)")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>展开完整内容</summary>")
            lines.append("")
            lines.append(content)
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if record.tools:
            lines.append("---")
            lines.append("")
            lines.append(f"## Tools ({len(record.tools)})")
            lines.append("")
            for j, tool in enumerate(record.tools):
                if tool.get("type") == "function":
                    func = tool.get("function", {})
                    name = func.get("name", "unknown")
                    desc = func.get("description", "")
                    params = func.get("parameters", {})
                    lines.append(f"### [{j + 1}] {name}")
                    lines.append("")
                    if desc:
                        lines.append(f"**描述:** {desc}")
                        lines.append("")
                    lines.append("**参数:**")
                    lines.append("```json")
                    lines.append(json.dumps(params, ensure_ascii=False, indent=2))
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)


_writer_instance: LlmAuditWriter | None = None


def get_llm_audit_writer() -> LlmAuditWriter:
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = LlmAuditWriter()
    return _writer_instance
