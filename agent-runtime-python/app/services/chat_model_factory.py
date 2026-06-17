from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.llm_audit import get_llm_audit_writer, _mask_api_key

SUPPORTED_PROVIDERS = {"openai", "openai-compatible"}


class ChatModelFactory:
    def create(self, config: dict) -> ChatOpenAI:
        provider = config.get("provider", "")
        model_name = config.get("modelName", "")
        api_key = config.get("apiKey", "")
        base_url = config.get("baseUrl", "")
        timeout = config.get("timeout", settings.model_request_timeout)

        if not model_name:
            raise AgentRuntimeError("模型名称不能为空", code=AgentErrorCode.MODEL_NAME_MISSING)

        if provider not in SUPPORTED_PROVIDERS:
            raise AgentRuntimeError(
                f"不支持的模型提供商: {provider}", code=AgentErrorCode.PROVIDER_NOT_SUPPORTED
            )

        if not api_key:
            raise AgentRuntimeError("模型 API Key 不能为空", code=AgentErrorCode.API_KEY_MISSING)

        kwargs: dict = {
            "model": model_name,
            "api_key": api_key,
            "timeout": timeout,
        }

        if base_url:
            kwargs["base_url"] = base_url

        writer = get_llm_audit_writer()
        if writer.enabled:
            audit_metadata = {
                "llm_audit_api_key_prefix": _mask_api_key(api_key),
                "llm_audit_provider": provider,
            }
            kwargs["callbacks"] = [writer.get_callback()]
            kwargs["metadata"] = audit_metadata

        return ChatOpenAI(**kwargs)
