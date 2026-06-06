package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.PythonAgentEventMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.test.StepVerifier;

import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

class PythonAgentRuntimeContractTest {

    private HttpServer server;
    private int port;

    @BeforeEach
    void setUp() throws Exception {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        port = server.getAddress().getPort();
        server.createContext("/agent/code-generation/stream", exchange -> {
            String response = """
                    event: agent_start
                    data: {"agentRunId":"9","seq":1,"eventType":"agent_start","data":{"runtime":"python-langgraph-skeleton"}}

                    event: tool_request
                    data: {"agentRunId":"9","seq":2,"eventType":"tool_request","data":{"id":"tool-1","name":"write_file","arguments":{"path":"src/App.vue"}}}

                    event: tool_executed
                    data: {"agentRunId":"9","seq":3,"eventType":"tool_executed","data":{"id":"tool-1","name":"write_file","arguments":{"path":"src/App.vue"},"result":"写入成功: src/App.vue"}}

                    event: done
                    data: {"agentRunId":"9","seq":4,"eventType":"done","data":{"message":"completed"}}

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
    void stream_shouldHandlePythonProtocolEvents() {
        PythonAgentRuntime runtime = new PythonAgentRuntime();
        ReflectionTestUtils.setField(runtime, "pythonBaseUrl", "http://localhost:" + port);
        ReflectionTestUtils.setField(runtime, "workspaceProperties", new WorkspaceProperties());
        ReflectionTestUtils.setField(runtime, "pythonAgentEventMapper", new PythonAgentEventMapper());

        CodeGenerationRequest request = CodeGenerationRequest.builder()
                .agentRunId(9L)
                .appId(1L)
                .sessionId(2L)
                .loginUser(User.builder().id(3L).build())
                .app(App.builder().codeGenType("vue_project").build())
                .message("create app")
                .build();

        StepVerifier.create(runtime.stream(request))
                .expectNextCount(4)
                .verifyComplete();
    }
}
