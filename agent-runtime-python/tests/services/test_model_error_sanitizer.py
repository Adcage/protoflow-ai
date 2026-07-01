from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError
from app.core.model_error_sanitizer import sanitize_sensitive_text, to_safe_agent_error


def test_to_safe_agent_error_masks_authentication_failure():
    exc = RuntimeError(
        "Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key: sk-test-secret is invalid'}}"
    )

    safe_error = to_safe_agent_error(exc, default_message="提示词优化服务暂时不可用")

    assert safe_error.code == AgentErrorCode.MODEL_CALL_FAILED
    assert "鉴权失败" in safe_error.message
    assert "sk-test-secret" not in safe_error.message


def test_to_safe_agent_error_maps_missing_config():
    exc = AgentRuntimeError("模型 API Key 不能为空", code=AgentErrorCode.API_KEY_MISSING)

    safe_error = to_safe_agent_error(exc, default_message="轻量标题生成服务暂时不可用")

    assert safe_error.code == AgentErrorCode.MODEL_CONFIG_MISSING
    assert "配置不完整" in safe_error.message


def test_to_safe_agent_error_keeps_existing_sanitized_auth_failure():
    exc = AgentRuntimeError(
        "轻量模型鉴权失败，请检查 AI_LIGHT_API_KEY、AI_LIGHT_BASE_URL 和 AI_LIGHT_MODEL 配置",
        code=AgentErrorCode.MODEL_CALL_FAILED,
    )

    safe_error = to_safe_agent_error(exc, default_message="提示词优化服务暂时不可用")

    assert safe_error.code == AgentErrorCode.MODEL_CALL_FAILED
    assert safe_error.message == exc.message


def test_sanitize_sensitive_text_replaces_api_key_value():
    sanitized = sanitize_sensitive_text("Authentication Fails, Your api key: sk-test-secret is invalid")

    assert "sk-test-secret" not in sanitized
    assert "****" in sanitized
