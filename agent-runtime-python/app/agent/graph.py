import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.events.agent_event import AgentEvent
from app.services.prompt_builder import PromptBuilder
from app.tools.file_tools import FileTools
from app.tools.workspace import Workspace

prompt_builder = PromptBuilder()

_FALLBACK_CONTENT = "<template><main><h1>AI Generated App</h1></main></template>\n"


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:vue|html)?\s*\n?", "", text)
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text.strip()


async def invoke_model(state: AgentState) -> AgentState:
    request = state["request"]
    events = list(state["events"])
    seq = len(events) + 1
    chat_model = state.get("chat_model")

    if chat_model is None:
        events.append(AgentEvent(
            agentRunId=request.agentRunId, seq=seq, eventType="ai_response",
            data={"text": "已生成 Vue 页面源码（降级模板），准备写入 src/App.vue", "fallback": True},
        ))
        return {
            "request": request, "events": events,
            "model_config": state.get("model_config"), "chat_model": None,
            "generated_content": _FALLBACK_CONTENT, "error": None,
            "grpc_tool_client": state.get("grpc_tool_client"),
            "grpc_platform_client": state.get("grpc_platform_client"),
        }

    system_prompt = prompt_builder.build_vue_app_prompt(request.prompt)
    response: AIMessage = await chat_model.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=request.prompt),
    ])
    content = _strip_markdown_fences(response.content or "")

    if not content:
        events.append(AgentEvent(
            agentRunId=request.agentRunId, seq=seq, eventType="error",
            data={"message": "模型返回内容为空"},
        ))
        return {
            "request": request, "events": events,
            "model_config": state.get("model_config"), "chat_model": chat_model,
            "generated_content": None, "error": "模型返回内容为空",
            "grpc_tool_client": state.get("grpc_tool_client"),
            "grpc_platform_client": state.get("grpc_platform_client"),
        }

    events.append(AgentEvent(
        agentRunId=request.agentRunId, seq=seq, eventType="ai_response",
        data={"text": "已生成 Vue 页面源码，准备写入 src/App.vue"},
    ))

    return {
        "request": request, "events": events,
        "model_config": state.get("model_config"), "chat_model": chat_model,
        "generated_content": content, "error": None,
        "grpc_tool_client": state.get("grpc_tool_client"),
        "grpc_platform_client": state.get("grpc_platform_client"),
    }


async def write_file(state: AgentState) -> AgentState:
    request = state["request"]
    events = list(state["events"])
    seq = len(events) + 1
    generated_content = state.get("generated_content")
    tool_client = state.get("grpc_tool_client")

    if generated_content is None:
        events.append(AgentEvent(
            agentRunId=request.agentRunId, seq=seq, eventType="error",
            data={"message": "无生成内容，跳过文件写入"},
        ))
        return {
            "request": request, "events": events,
            "model_config": state.get("model_config"), "chat_model": state.get("chat_model"),
            "generated_content": None, "error": state.get("error") or "无生成内容",
            "grpc_tool_client": tool_client, "grpc_platform_client": state.get("grpc_platform_client"),
        }

    path = "src/App.vue"

    events.append(AgentEvent(
        agentRunId=request.agentRunId, seq=seq, eventType="tool_request",
        data={"id": "tool-1", "name": "write_file", "arguments": {"path": path}},
    ))
    seq += 1

    if tool_client:
        result = await tool_client.write_file(path, generated_content)
    else:
        workspace = Workspace(request.workspacePath or f"storage/agent-workspaces/{request.agentRunId}/source")
        tools = FileTools(workspace)
        result = tools.write_file(path, generated_content)

    events.append(AgentEvent(
        agentRunId=request.agentRunId, seq=seq, eventType="tool_executed",
        data={"id": "tool-1", "name": "write_file", "arguments": {"path": path}, "result": result},
    ))
    seq += 1

    events.append(AgentEvent(agentRunId=request.agentRunId, seq=seq, eventType="done", data={"message": "completed"}))
    return {
        "request": request, "events": events,
        "model_config": state.get("model_config"), "chat_model": state.get("chat_model"),
        "generated_content": generated_content, "error": None,
        "grpc_tool_client": tool_client, "grpc_platform_client": state.get("grpc_platform_client"),
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("invoke_model", invoke_model)
    graph.add_node("write_file", write_file)
    graph.set_entry_point("invoke_model")
    graph.add_edge("invoke_model", "write_file")
    graph.add_edge("write_file", END)
    return graph.compile()
