package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.PythonAgentEventMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.test.StepVerifier;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

class PythonAgentRuntimeTest {

    private HttpServer server;
    private int port;
    private volatile String capturedRequestBody;

    @BeforeEach
    void setUp() throws Exception {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        port = server.getAddress().getPort();
        server.createContext("/agent/code-generation/stream", exchange -> {
            capturedRequestBody = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            String response = """
                    event: ai_response
                    data: {"agentRunId":"1","seq":1,"eventType":"ai_response","data":{"text":"hello"}}

                    event: done
                    data: {"agentRunId":"1","seq":2,"eventType":"done","data":{"message":"completed"}}

                    """;
            exchange.getResponseHeaders().set("Content-Type", "text/event-stream");
            exchange.sendResponseHeaders(200, response.getBytes(StandardCharsets.UTF_8).length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes(StandardCharsets.UTF_8));
            }
        });
        server.start();
    }

    @AfterEach
    void tearDown() {
        server.stop(0);
    }

    @Test
    void stream_shouldReadPythonSseAndMapEvents() {
        PythonAgentRuntime runtime = new PythonAgentRuntime();
        WorkspaceProperties workspaceProperties = new WorkspaceProperties();
        ReflectionTestUtils.setField(runtime, "pythonBaseUrl", "http://localhost:" + port);
        ReflectionTestUtils.setField(runtime, "workspaceProperties", workspaceProperties);
        ReflectionTestUtils.setField(runtime, "pythonAgentEventMapper", new PythonAgentEventMapper());

        CodeGenerationRequest request = CodeGenerationRequest.builder()
                .agentRunId(1L)
                .appId(2L)
                .sessionId(3L)
                .loginUser(User.builder().id(4L).build())
                .app(App.builder().codeGenType("vue_project").build())
                .message("build app")
                .modelConfigId(10L)
                .configVersion(3)
                .workspacePath("/custom/workspace/source")
                .build();

        StepVerifier.create(runtime.stream(request))
                .assertNext(chunk -> Assertions.assertTrue(chunk.contains("hello")))
                .assertNext(chunk -> Assertions.assertTrue(chunk.contains("completed")))
                .verifyComplete();

        Assertions.assertNotNull(capturedRequestBody, "Request body should have been captured");
        ObjectMapper mapper = new ObjectMapper();
        JsonNode body = Assertions.assertDoesNotThrow(() -> mapper.readTree(capturedRequestBody));
        Assertions.assertEquals(10, body.get("modelConfigId").asInt());
        Assertions.assertEquals(3, body.get("configVersion").asInt());
        Assertions.assertEquals("/custom/workspace/source", body.get("workspacePath").asText());
    }
}
