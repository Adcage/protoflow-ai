from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.core.response import success
from app.core.sse import format_sse
from app.core.config import settings
from app.schemas.code_generation import CodeGenerationRequest
from app.services.agent_service import AgentService
from app.services.chat_model_factory import ChatModelFactory
from app.services.model_config_client import ModelConfigClient
from app.services.prompt_builder import PromptBuilder

logger = get_logger("app.api.code_generation")

router = APIRouter(prefix="/agent/code-generation", tags=["code-generation"])

_model_config_client = ModelConfigClient(settings.java_platform_base_url, settings.agent_internal_secret)
_chat_model_factory = ChatModelFactory()
_prompt_builder = PromptBuilder()
agent_service = AgentService(_model_config_client, _chat_model_factory, _prompt_builder)


async def event_stream(request: CodeGenerationRequest, request_id: str) -> AsyncIterator[str]:
    logger.info("agent_run_id=%s request_id=%s stream started", request.agentRunId, request_id)
    async for event in agent_service.stream(request):
        yield format_sse(event)
    logger.info("agent_run_id=%s request_id=%s stream completed", request.agentRunId, request_id)


# NOTE: gRPC CodeGenerationService (port 9091) is the primary channel for code generation.
# This HTTP SSE endpoint is retained as a fallback/degradation path only.
@router.post("/stream")
async def stream_code_generation(request: CodeGenerationRequest, http_request: Request) -> StreamingResponse:
    request_id = getattr(http_request.state, "request_id", "unknown")

    return StreamingResponse(event_stream(request, request_id), media_type="text/event-stream")


@router.post("/submit")
async def submit_code_generation(request: CodeGenerationRequest, http_request: Request) -> dict:
    request_id = getattr(http_request.state, "request_id", "unknown")
    logger.info(
        "agent_run_id=%s request_id=%s appId=%s codeGenType=%s submit accepted",
        request.agentRunId,
        request_id,
        request.appId,
        request.codeGenType,
    )
    return success(data={"agentRunId": request.agentRunId, "status": "accepted"}, request=http_request)
