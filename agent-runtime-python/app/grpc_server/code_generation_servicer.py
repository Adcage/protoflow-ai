import logging

from app.core.error_codes import AgentErrorCode
from app.grpc import code_generation_pb2
from app.grpc import code_generation_pb2_grpc
from app.grpc import common_pb2
from app.grpc_client.platform_client import GrpcPlatformClient
from app.runtime.orchestrator import RuntimeOrchestrator
from app.services.chat_model_factory import ChatModelFactory
from app.services.prompt_enhancer import PromptEnhancerService

logger = logging.getLogger("app.grpc_server.code_generation_servicer")


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

    async def RouteCodeGenType(self, request, context):
        prompt = request.prompt.lower() if request.prompt else ""
        vue_keywords = ["vue", "项目", "多页面", "后台", "管理系统", "dashboard"]
        multi_keywords = ["多个文件", "css", "js", "multi"]

        if any(kw in prompt for kw in vue_keywords):
            code_gen_type = common_pb2.VUE_PROJECT
        elif any(kw in prompt for kw in multi_keywords):
            code_gen_type = common_pb2.MULTI_FILE
        else:
            code_gen_type = common_pb2.SINGLE_FILE

        logger.info("RouteCodeGenType | promptLen=%d result=%s", len(request.prompt), code_gen_type)
        return code_generation_pb2.RouteCodeGenTypeResponse(code_gen_type=code_gen_type)

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
        injection_keywords = ["ignore previous instructions", "bypass", "jailbreak"]
        lower = prompt.lower()
        for kw in injection_keywords:
            if kw in lower:
                return code_generation_pb2.ValidatePromptResponse(
                    valid=False,
                    reason=f"[{AgentErrorCode.PROMPT_INJECTION_DETECTED}] 提示词包含不允许的内容",
                )
        return code_generation_pb2.ValidatePromptResponse(valid=True)

    async def EnhancePrompt(self, request, context):
        prompt = request.prompt
        model_config_id = request.model_config_id
        config_version = request.config_version

        logger.info(
            "EnhancePrompt called, promptLength=%d, modelConfigId=%s, configVersion=%s",
            len(prompt) if prompt else 0,
            model_config_id,
            config_version,
        )

        if not prompt or not prompt.strip():
            return code_generation_pb2.EnhancePromptResponse(
                success=False, error_message=f"[{AgentErrorCode.PROMPT_EMPTY}] 提示词不能为空"
            )

        try:
            platform_client = GrpcPlatformClient()
            model_config = await platform_client.get_model_config(model_config_id, config_version)
            logger.info(
                "EnhancePrompt got model_config, provider=%s, modelName=%s, baseUrl=%s",
                model_config.get("provider"),
                model_config.get("modelName"),
                model_config.get("baseUrl"),
            )
            chat_model_factory = ChatModelFactory()
            enhancer = PromptEnhancerService(chat_model_factory)
            enhanced = await enhancer.enhance(prompt, model_config)
            logger.info(
                "EnhancePrompt success, enhancedLength=%d", len(enhanced) if enhanced else 0
            )
            return code_generation_pb2.EnhancePromptResponse(success=True, enhanced_prompt=enhanced)
        except Exception as e:
            logger.error("EnhancePrompt failed: %s", e, exc_info=True)
            return code_generation_pb2.EnhancePromptResponse(success=False, error_message=str(e))
