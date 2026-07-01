import logging

from app.core.error_codes import AgentErrorCode
from app.core.model_error_sanitizer import summarize_error_for_log, to_safe_agent_error
from app.grpc import code_generation_pb2
from app.grpc import code_generation_pb2_grpc
from app.grpc import common_pb2
from app.runtime.orchestrator import RuntimeOrchestrator
from app.services.lightweight_ai_service import LightweightAiService

logger = logging.getLogger("app.grpc_server.code_generation_servicer")

_EN_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "ignore the above",
    "disregard previous",
    "disregard all",
    "bypass",
    "jailbreak",
    "system prompt",
    "you are now",
    "act as",
    "pretend you are",
    "roleplay as",
    "new instruction",
    "override instruction",
    "forget everything",
    "forget your instructions",
    "ignore your rules",
    "do anything now",
    "DAN mode",
]

_CN_INJECTION_PATTERNS = [
    "忽略之前的指令",
    "忽略所有指令",
    "忽略上述",
    "无视之前的",
    "绕过限制",
    "越狱",
    "系统提示词",
    "你现在是一个",
    "假装你是",
    "扮演",
    "新指令",
    "覆盖指令",
    "忘记一切",
    "忘记你的指令",
    "忽略你的规则",
    "不受限制",
]

_ENCODING_TRICKS = [
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
    "\u00ad",
    "\\x",
    "\\u00",
    "\\nignore",
    "\\n.system",
]


def _detect_prompt_injection(prompt: str) -> str:
    normalized = prompt.lower()
    stripped = "".join(c for c in normalized if c.isalnum() or c.isspace())

    for pattern in _EN_INJECTION_PATTERNS:
        if pattern in normalized or pattern in stripped:
            return "提示词包含不允许的内容"

    for pattern in _CN_INJECTION_PATTERNS:
        if pattern in prompt or pattern in stripped:
            return "提示词包含不允许的内容"

    for trick in _ENCODING_TRICKS:
        if trick in prompt:
            return "提示词包含不允许的字符"

    role_patterns = ["<|im_start|>", "<|system|>", "[system]", "### system", "=== system"]
    for rp in role_patterns:
        if rp in normalized:
            return "提示词包含不允许的内容"

    return ""


class CodeGenerationServicer(code_generation_pb2_grpc.CodeGenerationServiceServicer):
    async def StreamGenerate(self, request, context):
        logger.info("StreamGenerate | agentRunId=%s appId=%s", request.agent_run_id, request.app_id)
        try:
            orchestrator = RuntimeOrchestrator()
            async for event in orchestrator.stream_generate(request):
                yield event
        except Exception as e:
            logger.error(
                "StreamGenerate error | agentRunId=%s error=%s",
                request.agent_run_id,
                e,
                exc_info=True,
            )
            yield code_generation_pb2.CodeGenerationEvent(
                agent_run_id=request.agent_run_id,
                seq=1,
                event_type=common_pb2.ERROR,
                error=common_pb2.ErrorData(message=str(e), code=AgentErrorCode.INTERNAL_ERROR),
            )

    async def StreamModify(self, request, context):
        logger.info("StreamModify | agentRunId=%s appId=%s", request.agent_run_id, request.app_id)
        try:
            orchestrator = RuntimeOrchestrator()
            async for event in orchestrator.stream_modify(request):
                yield event
        except Exception as e:
            logger.error(
                "StreamModify error | agentRunId=%s error=%s",
                request.agent_run_id,
                e,
                exc_info=True,
            )
            yield code_generation_pb2.CodeGenerationEvent(
                agent_run_id=request.agent_run_id,
                seq=1,
                event_type=common_pb2.ERROR,
                error=common_pb2.ErrorData(message=str(e), code=AgentErrorCode.INTERNAL_ERROR),
            )

    async def ValidatePrompt(self, request, context):
        prompt = request.prompt
        if not prompt or len(prompt.strip()) == 0:
            return code_generation_pb2.ValidatePromptResponse(
                valid=False, reason=f"[{AgentErrorCode.PROMPT_EMPTY}] 提示词不能为空"
            )
        if len(prompt) > 2000:
            return code_generation_pb2.ValidatePromptResponse(
                valid=False,
                reason=f"[{AgentErrorCode.PROMPT_LENGTH_EXCEEDED}] 提示词长度不能超过2000字",
            )
        injection_result = _detect_prompt_injection(prompt)
        if injection_result:
            return code_generation_pb2.ValidatePromptResponse(
                valid=False,
                reason=f"[{AgentErrorCode.PROMPT_INJECTION_DETECTED}] {injection_result}",
            )
        return code_generation_pb2.ValidatePromptResponse(valid=True)

    async def EnhancePrompt(self, request, context):
        prompt = request.prompt

        logger.info(
            "EnhancePrompt called, promptLength=%d",
            len(prompt) if prompt else 0,
        )

        if not prompt or not prompt.strip():
            return code_generation_pb2.EnhancePromptResponse(
                success=False, error_message=f"[{AgentErrorCode.PROMPT_EMPTY}] 提示词不能为空"
            )

        try:
            lightweight_service = LightweightAiService()
            enhanced = await lightweight_service.enhance_prompt(prompt)
            logger.info(
                "EnhancePrompt success, enhancedLength=%d", len(enhanced) if enhanced else 0
            )
            return code_generation_pb2.EnhancePromptResponse(success=True, enhanced_prompt=enhanced)
        except Exception as e:
            safe_error = to_safe_agent_error(e, default_message="提示词优化服务暂时不可用")
            logger.error(
                "EnhancePrompt failed: %s",
                summarize_error_for_log(e, default_message="提示词优化服务暂时不可用"),
            )
            return code_generation_pb2.EnhancePromptResponse(
                success=False,
                error_message=str(safe_error),
            )

    async def GenerateAppTitle(self, request, context):
        init_prompt = request.init_prompt
        logger.info("GenerateAppTitle called, promptLength=%d", len(init_prompt) if init_prompt else 0)

        if not init_prompt or not init_prompt.strip():
            return code_generation_pb2.GenerateTitleResponse(
                success=False, error_message=f"[{AgentErrorCode.PROMPT_EMPTY}] 初始化提示词不能为空"
            )

        try:
            lightweight_service = LightweightAiService()
            title = await lightweight_service.generate_app_title(init_prompt)
            return code_generation_pb2.GenerateTitleResponse(success=True, title=title)
        except Exception as e:
            safe_error = to_safe_agent_error(e, default_message="轻量标题生成服务暂时不可用")
            logger.error(
                "GenerateAppTitle failed: %s",
                summarize_error_for_log(e, default_message="轻量标题生成服务暂时不可用"),
            )
            return code_generation_pb2.GenerateTitleResponse(
                success=False,
                error_message=str(safe_error),
            )

    async def GenerateSessionTitle(self, request, context):
        first_user_message = request.first_user_message
        logger.info(
            "GenerateSessionTitle called, messageLength=%d",
            len(first_user_message) if first_user_message else 0,
        )

        if not first_user_message or not first_user_message.strip():
            return code_generation_pb2.GenerateTitleResponse(
                success=False, error_message=f"[{AgentErrorCode.PROMPT_EMPTY}] 会话消息不能为空"
            )

        try:
            lightweight_service = LightweightAiService()
            title = await lightweight_service.generate_session_title(
                request.app_name, request.app_init_prompt, first_user_message
            )
            return code_generation_pb2.GenerateTitleResponse(success=True, title=title)
        except Exception as e:
            safe_error = to_safe_agent_error(e, default_message="轻量标题生成服务暂时不可用")
            logger.error(
                "GenerateSessionTitle failed: %s",
                summarize_error_for_log(e, default_message="轻量标题生成服务暂时不可用"),
            )
            return code_generation_pb2.GenerateTitleResponse(
                success=False,
                error_message=str(safe_error),
            )
