import grpc
import logging

from app.core.error_codes import AgentErrorCode
from app.grpc import code_generation_pb2
from app.grpc import code_generation_pb2_grpc
from app.grpc import common_pb2
from app.grpc_client.platform_client import GrpcPlatformClient
from app.services.chat_model_factory import ChatModelFactory
from app.services.prompt_enhancer import PromptEnhancerService

logger = logging.getLogger("app.grpc_server.code_generation_servicer")


class CodeGenerationServicer(code_generation_pb2_grpc.CodeGenerationServiceServicer):

    async def StreamGenerate(self, request, context):
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "StreamGenerate not yet implemented")

    async def StreamModify(self, request, context):
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "StreamModify not yet implemented")

    async def RouteCodeGenType(self, request, context):
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "RouteCodeGenType not yet implemented")

    async def ValidatePrompt(self, request, context):
        prompt = request.prompt
        if not prompt or len(prompt.strip()) == 0:
            return code_generation_pb2.ValidatePromptResponse(
                valid=False, reason=f"[{AgentErrorCode.PROMPT_EMPTY}] 提示词不能为空"
            )
        if len(prompt) > 2000:
            return code_generation_pb2.ValidatePromptResponse(
                valid=False, reason=f"[{AgentErrorCode.PROMPT_LENGTH_EXCEEDED}] 提示词长度不能超过2000字"
            )
        injection_keywords = ["ignore previous instructions", "bypass", "jailbreak"]
        lower = prompt.lower()
        for kw in injection_keywords:
            if kw in lower:
                return code_generation_pb2.ValidatePromptResponse(
                    valid=False, reason=f"[{AgentErrorCode.PROMPT_INJECTION_DETECTED}] 提示词包含不允许的内容"
                )
        return code_generation_pb2.ValidatePromptResponse(valid=True)

    async def EnhancePrompt(self, request, context):
        prompt = request.prompt
        model_config_id = request.model_config_id
        config_version = request.config_version

        logger.info("EnhancePrompt called, promptLength=%d, modelConfigId=%s, configVersion=%s",
                     len(prompt) if prompt else 0, model_config_id, config_version)

        if not prompt or not prompt.strip():
            return code_generation_pb2.EnhancePromptResponse(
                success=False, error_message=f"[{AgentErrorCode.PROMPT_EMPTY}] 提示词不能为空"
            )

        try:
            platform_client = GrpcPlatformClient()
            model_config = await platform_client.get_model_config(model_config_id, config_version)
            logger.info("EnhancePrompt got model_config, provider=%s, modelName=%s, baseUrl=%s",
                         model_config.get("provider"), model_config.get("modelName"), model_config.get("baseUrl"))
            chat_model_factory = ChatModelFactory()
            enhancer = PromptEnhancerService(chat_model_factory)
            enhanced = await enhancer.enhance(prompt, model_config)
            logger.info("EnhancePrompt success, enhancedLength=%d", len(enhanced) if enhanced else 0)
            return code_generation_pb2.EnhancePromptResponse(success=True, enhanced_prompt=enhanced)
        except Exception as e:
            logger.error("EnhancePrompt failed: %s", e, exc_info=True)
            return code_generation_pb2.EnhancePromptResponse(
                success=False, error_message=str(e)
            )
