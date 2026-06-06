package com.adcage.acaicodefree.runtime;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public class PythonAgentEventMapper {

    public String mapToStreamMessage(PythonAgentEvent event) {
        Map<String, Object> data = event.getData();
        return switch (event.getEventType()) {
            case "ai_response" -> JSONUtil.toJsonStr(new AiResponseMessage(String.valueOf(data.getOrDefault("text", ""))));
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
