from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessageChunk

from app.agent_loop.nodes.step_base import _stream_invoke
from app.agent_loop.tool_policy import PLAN_TOOLS
from app.runtime.event_mapper import ProtoEventMapper, _INTERNAL_TYPES
from app.runtime.events import RuntimeEvent, RuntimeEventType
from app.runtime.event_bus import SequencedRuntimeEvent


def _make_event_bus():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


def _emitted_text_deltas(bus):
    return [
        call.args[0].data["text"]
        for call in bus.emit.await_args_list
        if call.args[0].event_type == RuntimeEventType.TEXT_DELTA
    ]


def _make_sequenced(event_type, data=None):
    return SequencedRuntimeEvent(
        agent_run_id=1,
        seq=1,
        event=RuntimeEvent(event_type, data or {}),
    )


class _TextThenToolCallModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        yield AIMessageChunk(content="已整理需求，现在读取文件")
        yield AIMessageChunk(
            content="",
            tool_call_chunks=[
                {
                    "name": "read_file",
                    "args": '{"relative_path":"src/App.vue"}',
                    "id": "tool-1",
                    "index": 0,
                }
            ],
        )


class _PlainTextModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        yield AIMessageChunk(content="任务")
        yield AIMessageChunk(content="已完成")


class _EmptyModel:
    def bind_tools(self, _tools):
        return self

    async def astream(self, _messages):
        return
        yield


@pytest.mark.asyncio
async def test_tool_call_preamble_is_not_emitted_as_ai_response():
    event_bus = _make_event_bus()
    text, tool_calls, _ = await _stream_invoke(_TextThenToolCallModel(), [], event_bus)

    assert text == "已整理需求，现在读取文件"
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "read_file"
    deltas = _emitted_text_deltas(event_bus)
    assert deltas == [], f"pre-tool-call text should NOT be emitted as TEXT_DELTA, got: {deltas}"


@pytest.mark.asyncio
async def test_plain_user_facing_response_is_emitted_once():
    event_bus = _make_event_bus()
    text, tool_calls, _ = await _stream_invoke(_PlainTextModel(), [], event_bus)

    assert text == "任务已完成"
    assert tool_calls == []
    deltas = _emitted_text_deltas(event_bus)
    assert deltas == ["任务已完成"], f"expected single full-text emission, got: {deltas}"


@pytest.mark.asyncio
async def test_empty_model_emits_nothing():
    event_bus = _make_event_bus()
    text, tool_calls, _ = await _stream_invoke(_EmptyModel(), [], event_bus)

    assert text == ""
    assert tool_calls == []
    deltas = _emitted_text_deltas(event_bus)
    assert deltas == []


def test_plan_tools_are_all_classified():
    mapper = ProtoEventMapper()
    unclassified = []
    for tool_name in sorted(PLAN_TOOLS):
        seq_event = _make_sequenced(
            RuntimeEventType.TOOL_CALL,
            {"id": "call-1", "name": tool_name, "arguments": "{}"},
        )
        import logging

        with pytest.MonkeyPatch.context() as m:
            captured = []
            m.setattr(
                logging.getLogger("app.runtime.event_mapper"),
                "warning",
                lambda *a, **kw: captured.append(a),
            )
            mapper.map_event(seq_event)
            if any("unclassified" in str(c) for c in captured):
                unclassified.append(tool_name)

    assert unclassified == [], (
        f"Plan tools produced unclassified warnings: {unclassified}"
    )


def test_agent_loop_lifecycle_events_are_classified_or_internal():
    lifecycle_types = [
        RuntimeEventType.AGENT_LOOP_ITERATION,
        RuntimeEventType.AGENT_LOOP_COMPLETED,
    ]
    for et in lifecycle_types:
        assert et in _INTERNAL_TYPES, (
            f"{et} should be in _INTERNAL_TYPES to avoid 'unmapped runtime event type' warning"
        )

    mapper = ProtoEventMapper()
    for et in lifecycle_types:
        seq_event = _make_sequenced(et, {"iteration": 1, "mode": "plan"})
        result = mapper.map_event(seq_event)
        assert result is None, (
            f"{et} is internal and should not produce a proto event, got: {result}"
        )
