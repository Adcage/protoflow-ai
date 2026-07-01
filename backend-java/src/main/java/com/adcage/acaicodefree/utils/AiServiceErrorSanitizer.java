package com.adcage.acaicodefree.utils;

import cn.hutool.core.util.StrUtil;

import java.util.Locale;
import java.util.regex.Pattern;

public final class AiServiceErrorSanitizer {

    private static final Pattern ERROR_CODE_PREFIX = Pattern.compile("^\\s*\\[\\d+]\\s*");
    private static final Pattern API_KEY_PATTERN = Pattern.compile("(?i)(api[_\\s-]?key\\s*[:=]\\s*)([^\\s,'\"}]+)");
    private static final Pattern BEARER_PATTERN = Pattern.compile("(?i)(bearer\\s+)([^\\s,'\"}]+)");

    private AiServiceErrorSanitizer() {
    }

    public static String sanitizeLightweightError(String rawMessage, String defaultMessage) {
        String normalized = ERROR_CODE_PREFIX.matcher(StrUtil.blankToDefault(rawMessage, "")).replaceFirst("").trim();
        if (StrUtil.isBlank(normalized)) {
            return defaultMessage;
        }
        String sanitized = BEARER_PATTERN.matcher(API_KEY_PATTERN.matcher(normalized).replaceAll("$1****"))
                .replaceAll("$1****");
        String lower = sanitized.toLowerCase(Locale.ROOT);

        if (sanitized.contains("内容安全策略拦截")) {
            return "提示词优化被内容安全策略拦截，请修改提示词后重试";
        }
        if (containsAny(lower,
                "authentication fails",
                "authentication failed",
                "authentication_error",
                "invalid api key",
                "incorrect api key",
                "unauthorized",
                "invalid_request_error",
                "error code: 401")) {
            return "轻量模型鉴权失败，请检查 AI_LIGHT_API_KEY、AI_LIGHT_BASE_URL 和 AI_LIGHT_MODEL 配置";
        }
        if (containsAny(lower, "quota", "insufficient_quota", "rate limit", "too many requests", "429")) {
            return "轻量模型额度不足或请求过于频繁，请稍后重试";
        }
        if (containsAny(lower, "timeout", "timed out", "deadline exceeded", "read timeout")) {
            return "轻量模型响应超时，请稍后重试";
        }
        if (containsAny(sanitized,
                "没有可用的轻量模型配置",
                "模型 API Key 不能为空",
                "模型名称不能为空",
                "不支持的模型提供商",
                "系统模型配置未设置")) {
            return "轻量模型配置不完整，请检查 AI_LIGHT_BASE_URL、AI_LIGHT_API_KEY、AI_LIGHT_MODEL 和 provider 配置";
        }
        if (containsAny(sanitized, "标题生成结果为空", "模型返回为空", "未返回有效结果")) {
            return "轻量模型未返回有效结果，请稍后重试";
        }
        if (StrUtil.startWithAny(sanitized, "提示词不能为空", "初始化提示词不能为空", "会话消息不能为空", "轻量模型")) {
            return sanitized;
        }
        return defaultMessage;
    }

    private static boolean containsAny(String text, String... patterns) {
        if (text == null || patterns == null) {
            return false;
        }
        for (String pattern : patterns) {
            if (text.contains(pattern)) {
                return true;
            }
        }
        return false;
    }
}
