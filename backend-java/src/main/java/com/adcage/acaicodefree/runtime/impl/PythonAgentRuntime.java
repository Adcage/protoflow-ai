package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.adcage.acaicodefree.runtime.PythonAgentEvent;
import com.adcage.acaicodefree.runtime.PythonAgentEventMapper;
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
@Component
public class PythonAgentRuntime implements CodeGenerationRuntime {

    private static final String NAME = "python-agent";

    @Value("${agent.python.base-url:http://localhost:9000}")
    private String pythonBaseUrl;

    @Resource
    private WorkspaceProperties workspaceProperties;

    @Resource
    private PythonAgentEventMapper pythonAgentEventMapper;

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
                                    PythonAgentEvent event = objectMapper.readValue(line, PythonAgentEvent.class);
                                    sink.next(pythonAgentEventMapper.mapToStreamMessage(event));
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
        body.put("workspacePath", resolveWorkspacePath(request.getAgentRunId()));
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
}
