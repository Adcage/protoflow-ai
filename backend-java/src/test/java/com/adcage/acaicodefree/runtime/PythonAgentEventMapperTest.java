package com.adcage.acaicodefree.runtime;

import cn.hutool.json.JSONUtil;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;

import java.util.Map;

class PythonAgentEventMapperTest {

    private final PythonAgentEventMapper mapper = new PythonAgentEventMapper();

    @Test
    void map_shouldConvertAiResponse() {
        PythonAgentEvent event = PythonAgentEvent.builder()
                .agentRunId("1")
                .seq(1L)
                .eventType("ai_response")
                .data(Map.of("text", "hello"))
                .build();

        String result = mapper.mapToStreamMessage(event);

        Assertions.assertTrue(JSONUtil.parseObj(result).getStr("type").contains("ai_response"));
        Assertions.assertTrue(result.contains("hello"));
    }

    @Test
    void map_shouldConvertToolRequest() {
        PythonAgentEvent event = PythonAgentEvent.builder()
                .agentRunId("1")
                .seq(2L)
                .eventType("tool_request")
                .data(Map.of("id", "tool-1", "name", "write_file", "arguments", "{\"path\":\"src/App.vue\"}"))
                .build();

        String result = mapper.mapToStreamMessage(event);

        Assertions.assertTrue(result.contains("tool_request"));
        Assertions.assertTrue(result.contains("write_file"));
    }
}
