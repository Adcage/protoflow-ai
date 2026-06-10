from __future__ import annotations

from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel

from app.events.agent_event import AgentEvent
from app.grpc_client.platform_client import GrpcPlatformClient
from app.grpc_client.tool_client import GrpcToolClient
from app.schemas.code_generation import CodeGenerationRequest


class AgentState(TypedDict):
    request: CodeGenerationRequest
    events: list[AgentEvent]
    model_config: dict | None
    chat_model: BaseChatModel | None
    generated_content: str | None
    error: str | None
    grpc_tool_client: GrpcToolClient | None
    grpc_platform_client: GrpcPlatformClient | None
