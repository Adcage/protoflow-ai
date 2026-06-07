from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.agent.graph import build_graph
from app.schemas.code_generation import CodeGenerationRequest


class FakeChatModel:
    async def ainvoke(self, messages):
        return AIMessage(content="<template><main><h1>Portfolio</h1></main></template>")


@pytest.mark.asyncio
async def test_graph_writes_app_vue_with_fake_model(tmp_path: Path):
    request = CodeGenerationRequest(
        agentRunId="1",
        appId=2,
        sessionId=3,
        userId=4,
        prompt="create app",
        codeGenType="vue_project",
        workspacePath=str(tmp_path),
    )
    graph = build_graph()
    result = await graph.ainvoke({
        "request": request,
        "events": [],
        "model_config": None,
        "chat_model": FakeChatModel(),
        "generated_content": None,
        "error": None,
    })

    app_vue = tmp_path / "src" / "App.vue"
    assert app_vue.exists()
    content = app_vue.read_text(encoding="utf-8")
    assert "Portfolio" in content

    event_types = [e.eventType for e in result["events"]]
    assert "ai_response" in event_types
    ai_events = [e for e in result["events"] if e.eventType == "ai_response"]
    assert ai_events
    assert "text" in ai_events[0].data
    ai_response_idx = event_types.index("ai_response")
    tool_request_idx = event_types.index("tool_request")
    assert ai_response_idx < tool_request_idx


@pytest.mark.asyncio
async def test_graph_fallback_without_model(tmp_path: Path):
    request = CodeGenerationRequest(
        agentRunId="2",
        appId=3,
        sessionId=4,
        userId=5,
        prompt="create app",
        codeGenType="vue_project",
        workspacePath=str(tmp_path),
    )
    graph = build_graph()
    result = await graph.ainvoke({
        "request": request,
        "events": [],
        "model_config": None,
        "chat_model": None,
        "generated_content": None,
        "error": None,
    })

    assert (tmp_path / "src" / "App.vue").exists()
    event_types = [e.eventType for e in result["events"]]
    assert "ai_response" in event_types
    ai_events = [e for e in result["events"] if e.eventType == "ai_response"]
    assert ai_events
    assert "text" in ai_events[0].data
    assert "tool_request" in event_types
