import re

from app.core.error_codes import AgentErrorCode
from app.core.exceptions import AgentRuntimeError

_AUTH_PATTERNS = (
    "authentication fails",
    "authentication failed",
    "authentication_error",
    "invalid api key",
    "incorrect api key",
    "unauthorized",
    "invalid_request_error",
    "401",
)

_QUOTA_PATTERNS = (
    "quota",
    "insufficient_quota",
    "rate limit",
    "too many requests",
    "429",
)

_TIMEOUT_PATTERNS = (
    "timeout",
    "timed out",
    "deadline exceeded",
    "read timeout",
)

_CONFIG_PATTERNS = (
    "没有可用的轻量模型配置",
    "模型 api key 不能为空",
    "模型名称不能为空",
    "不支持的模型提供商",
    "系统模型配置未设置",
)

_EMPTY_RESULT_PATTERNS = (
    "模型返回为空",
    "标题生成结果为空",
    "未返回有效结果",
)

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_\s-]?key\s*[:=]\s*)([^\s,'\"}]+)"),
    re.compile(r"(?i)(bearer\s+)([^\s,'\"}]+)"),
]


def sanitize_sensitive_text(text: str) -> str:
    sanitized = text or ""
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1****", sanitized)
    return sanitized


def to_safe_agent_error(
    exc: Exception,
    default_message: str,
    model_label: str = "轻量模型",
) -> AgentRuntimeError:
    if isinstance(exc, AgentRuntimeError):
        raw_message = exc.message
    else:
        raw_message = str(exc)
    sanitized = sanitize_sensitive_text(raw_message).strip()
    lower_message = sanitized.lower()

    if not sanitized:
        return AgentRuntimeError(default_message, code=AgentErrorCode.MODEL_CALL_FAILED)

    if isinstance(exc, AgentRuntimeError) and sanitized.startswith(
        (
            f"{model_label}鉴权失败",
            f"{model_label}额度不足",
            f"{model_label}响应超时",
            f"{model_label}配置不完整",
            f"{model_label}未返回有效结果",
        )
    ):
        return AgentRuntimeError(sanitized, code=exc.code)

    if "内容安全策略拦截" in sanitized:
        return AgentRuntimeError(sanitized, code=AgentErrorCode.CONTENT_SAFETY_REJECTED)

    if any(pattern in lower_message for pattern in _AUTH_PATTERNS):
        return AgentRuntimeError(
            f"{model_label}鉴权失败，请检查 AI_LIGHT_API_KEY、AI_LIGHT_BASE_URL 和 AI_LIGHT_MODEL 配置",
            code=AgentErrorCode.MODEL_CALL_FAILED,
        )

    if any(pattern in lower_message for pattern in _QUOTA_PATTERNS):
        return AgentRuntimeError(
            f"{model_label}额度不足或请求过于频繁，请稍后重试",
            code=AgentErrorCode.MODEL_QUOTA_EXCEEDED,
        )

    if any(pattern in lower_message for pattern in _TIMEOUT_PATTERNS):
        return AgentRuntimeError(
            f"{model_label}响应超时，请稍后重试",
            code=AgentErrorCode.MODEL_TIMEOUT,
        )

    if any(pattern in lower_message for pattern in _CONFIG_PATTERNS):
        return AgentRuntimeError(
            f"{model_label}配置不完整，请检查 AI_LIGHT_BASE_URL、AI_LIGHT_API_KEY、AI_LIGHT_MODEL 和 provider 配置",
            code=AgentErrorCode.MODEL_CONFIG_MISSING,
        )

    if any(pattern in sanitized for pattern in _EMPTY_RESULT_PATTERNS):
        return AgentRuntimeError(
            f"{model_label}未返回有效结果，请稍后重试",
            code=AgentErrorCode.MODEL_RESPONSE_EMPTY,
        )

    if isinstance(exc, AgentRuntimeError) and sanitized.startswith(("提示词不能为空", "初始化提示词不能为空", "会话消息不能为空")):
        return AgentRuntimeError(sanitized, code=exc.code)

    return AgentRuntimeError(default_message, code=AgentErrorCode.MODEL_CALL_FAILED)


def summarize_error_for_log(exc: Exception, default_message: str) -> str:
    safe_error = to_safe_agent_error(exc, default_message)
    return f"{type(exc).__name__}: {safe_error.message}"
