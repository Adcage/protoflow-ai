package com.adcage.acaicodefree.core.handler;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.ai.tools.BaseTool;
import com.adcage.acaicodefree.ai.tools.ToolManager;
import com.adcage.acaicodefree.ai.model.message.StreamMessageTypeEnum;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

import java.util.HashSet;
import java.util.Set;

@Component
public class JsonMessageStreamHandler {

    @Resource
    private ToolManager toolManager;

    public Flux<String> handle(Flux<String> stream, StringBuilder readableOutput) {
        Set<String> printedToolRequestIds = new HashSet<>();
        return stream.flatMap(chunk -> {
            if (StrUtil.isBlank(chunk)) {
                return Flux.empty();
            }
            JSONObject jsonObject;
            try {
                jsonObject = JSONUtil.parseObj(chunk);
            } catch (Exception e) {
                readableOutput.append(chunk);
                return Flux.just(chunk);
            }
            String type = jsonObject.getStr("type");
            if (StreamMessageTypeEnum.AI_RESPONSE.getValue().equals(type)) {
                String data = jsonObject.getStr("data", "");
                readableOutput.append(data);
                return Flux.just(chunk);
            }
            if (StreamMessageTypeEnum.TOOL_REQUEST.getValue().equals(type)) {
                String id = jsonObject.getStr("id", "");
                if (!printedToolRequestIds.add(id)) {
                    return Flux.empty();
                }
                String toolName = jsonObject.getStr("name", "");
                JSONObject arguments = parseArguments(jsonObject.getStr("arguments", ""));
                String requestText = buildToolRequestText(toolName, arguments);
                if (StrUtil.isNotBlank(requestText)) {
                    readableOutput.append("\n[工具调用] ").append(requestText).append('\n');
                }
                return Flux.just(chunk);
            }
            if (StreamMessageTypeEnum.TOOL_EXECUTED.getValue().equals(type)) {
                String toolName = jsonObject.getStr("name", "");
                String result = jsonObject.getStr("result", "");
                JSONObject arguments = parseArguments(jsonObject.getStr("arguments", ""));
                String executedText = buildToolExecutedText(toolName, arguments, result);
                if (StrUtil.isNotBlank(executedText)) {
                    readableOutput.append("\n[工具完成] ").append(executedText).append('\n');
                }
                return Flux.just(chunk);
            }
            if ("workflow_event".equals(type)) {
                return Flux.just(chunk);
            }
            readableOutput.append(chunk);
            return Flux.just(chunk);
        });
    }

    private JSONObject parseArguments(String argumentsText) {
        if (StrUtil.isBlank(argumentsText)) {
            return new JSONObject();
        }
        try {
            return JSONUtil.parseObj(argumentsText);
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    private String buildToolRequestText(String toolName, JSONObject arguments) {
        BaseTool tool = toolManager == null ? null : toolManager.getTool(toolName);
        if (tool != null) {
            return StrUtil.nullToEmpty(tool.generateToolRequestResponse(arguments));
        }
        String path = extractPath(arguments);
        if (StrUtil.isNotBlank(path)) {
            return "准备处理文件 " + path;
        }
        return StrUtil.isBlank(toolName) ? "正在执行工具" : "正在执行工具 " + toolName;
    }

    private String buildToolExecutedText(String toolName, JSONObject arguments, String result) {
        BaseTool tool = toolManager == null ? null : toolManager.getTool(toolName);
        if (tool != null) {
            return StrUtil.nullToEmpty(tool.generateToolExecutedResult(arguments, result));
        }
        String path = extractPath(arguments);
        if (StrUtil.isNotBlank(path)) {
            return "已处理文件 " + path;
        }
        if (StrUtil.isNotBlank(result)) {
            return result;
        }
        return StrUtil.isBlank(toolName) ? "工具执行成功" : "工具执行成功 " + toolName;
    }

    private String extractPath(JSONObject arguments) {
        if (arguments == null || arguments.isEmpty()) {
            return "";
        }
        String relativeFilePath = arguments.getStr("relativeFilePath", "");
        if (StrUtil.isNotBlank(relativeFilePath)) {
            return relativeFilePath;
        }
        return arguments.getStr("relativeDirPath", "");
    }

}
