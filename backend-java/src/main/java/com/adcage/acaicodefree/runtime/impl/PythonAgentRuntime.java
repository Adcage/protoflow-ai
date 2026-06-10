package com.adcage.acaicodefree.runtime.impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Deprecated
// @Component // 已被 GrpcPythonAgentRuntime 替代，注释掉避免 Bean 冲突
public class PythonAgentRuntime implements CodeGenerationRuntime {

    private static final String NAME = "python-agent";

    @Value("${agent.python.base-url:http://localhost:9000}")
    private String pythonBaseUrl;

    @Resource
    private WorkspaceProperties workspaceProperties;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public Flux<String> stream(CodeGenerationRequest request) {
        return Flux.create(sink -> {
            try {
                HttpRequest httpRequest = buildRequest(request);
                HttpResponse<java.util.stream.Stream<String>> response = httpClient.send(
                        httpRequest,
                        HttpResponse.BodyHandlers.ofLines()
                );
                if (response.statusCode() != 200) {
                    sink.error(new RuntimeException("Python Agent Runtime 返回错误状态码: " + response.statusCode()));
                    return;
                }
                try (java.util.stream.Stream<String> lines = response.body()) {
                    lines.filter(line -> line.startsWith("data:"))
                            .map(line -> line.substring("data:".length()).trim())
                            .filter(line -> !line.isBlank())
                            .forEach(line -> {
                                try {
                                    @SuppressWarnings("unchecked")
                                    Map<String, Object> event = objectMapper.readValue(line, Map.class);
                                    String eventType = String.valueOf(event.get("eventType"));
                                    @SuppressWarnings("unchecked")
                                    Map<String, Object> data = (Map<String, Object>) event.get("data");
                                    String mapped = mapLegacyEventToStreamMessage(eventType, data);
                                    if (mapped != null) {
                                        sink.next(mapped);
                                    }
                                } catch (Exception e) {
                                    log.warn("解析 Python Agent 事件失败: {}", e.getMessage());
                                }
                            });
                }
                sink.complete();
            } catch (Exception e) {
                log.error("Python Agent Runtime 调用失败: {}", e.getMessage(), e);
                sink.error(e);
            }
        });
    }

    private HttpRequest buildRequest(CodeGenerationRequest request) throws Exception {
        Map<String, Object> body = new HashMap<>();
        body.put("agentRunId", String.valueOf(request.getAgentRunId()));
        body.put("appId", request.getAppId());
        body.put("sessionId", request.getSessionId());
        body.put("userId", request.getLoginUser().getId());
        body.put("prompt", request.getMessage());
        body.put("codeGenType", request.getApp().getCodeGenType());
        body.put("workspacePath", StrUtil.blankToDefault(
                request.getWorkspacePath(),
                resolveWorkspacePath(request.getAgentRunId())
        ));
        body.put("modelConfigId", request.getModelConfigId());
        body.put("configVersion", request.getConfigVersion());
        String jsonBody = objectMapper.writeValueAsString(body);
        return HttpRequest.newBuilder()
                .uri(URI.create(pythonBaseUrl + "/agent/code-generation/stream"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();
    }

    private String resolveWorkspacePath(Long agentRunId) {
        if (agentRunId == null) {
            return workspaceProperties.getAgentWorkspaceDir() + "/unknown/source";
        }
        return workspaceProperties.getAgentWorkspaceDir() + "/" + agentRunId + "/source";
    }

    private String mapLegacyEventToStreamMessage(String eventType, Map<String, Object> data) {
        return switch (eventType) {
            case "ai_response" -> {
                Object text = data.get("text");
                if (text == null) text = data.getOrDefault("content", "");
                yield JSONUtil.toJsonStr(new AiResponseMessage(String.valueOf(text)));
            }
            case "tool_request" -> JSONUtil.toJsonStr(new ToolRequestMessage(
                    String.valueOf(data.getOrDefault("id", "unknown")),
                    String.valueOf(data.getOrDefault("name", "unknown")),
                    String.valueOf(data.getOrDefault("arguments", "{}"))
            ));
            case "tool_executed" -> JSONUtil.toJsonStr(new ToolExecutedMessage(
                    String.valueOf(data.getOrDefault("id", "unknown")),
                    String.valueOf(data.getOrDefault("name", "unknown")),
                    String.valueOf(data.getOrDefault("arguments", "{}")),
                    String.valueOf(data.getOrDefault("result", ""))
            ));
            case "error" -> JSONUtil.toJsonStr(new AiResponseMessage("生成失败：" + data.getOrDefault("message", "")));
            case "done" -> JSONUtil.toJsonStr(new AiResponseMessage(String.valueOf(data.getOrDefault("message", ""))));
            default -> JSONUtil.toJsonStr(new AiResponseMessage(String.valueOf(data)));
        };
    }
}
