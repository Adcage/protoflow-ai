package com.adcage.acaicodefree.core.handler;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.service.FileOperationService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;

import java.util.List;

class JsonMessageStreamHandlerTest {

    @Test
    void jsonMessageHandlerShouldAppendAiResponseText() {
        JsonMessageStreamHandler handler = createHandler();
        StringBuilder readable = new StringBuilder();

        List<String> output = handler.handle(Flux.just(
                JSONUtil.toJsonStr(new AiResponseMessage("你好")),
                JSONUtil.toJsonStr(new AiResponseMessage("世界"))
        ), readable).collectList().block();

        Assertions.assertEquals("你好世界", readable.toString());
        Assertions.assertNotNull(output);
        Assertions.assertEquals(2, output.size());
    }

    @Test
    void jsonMessageHandlerShouldShowToolRequestOnlyOncePerId() {
        JsonMessageStreamHandler handler = createHandler();
        StringBuilder readable = new StringBuilder();

        String repeatedRequest = JSONUtil.toJsonStr(new ToolRequestMessage("t1", "writeFile", "{}"));
        List<String> output = handler.handle(Flux.just(repeatedRequest, repeatedRequest), readable).collectList().block();

        Assertions.assertNotNull(output);
        Assertions.assertEquals(1, output.size());
    }

    @Test
    void jsonMessageHandlerShouldUseToolExecutedAsFinalTrustedFileEvent() {
        JsonMessageStreamHandler handler = createHandler();
        StringBuilder readable = new StringBuilder();

        List<String> output = handler.handle(Flux.just(
                JSONUtil.toJsonStr(new ToolRequestMessage("t1", "writeFile", "{\"relativeFilePath\":\"src/main.js\"}")),
                JSONUtil.toJsonStr(new ToolExecutedMessage("t1", "writeFile", "{\"relativeFilePath\":\"src/main.js\"}", "文件写入成功：src/main.js"))
        ), readable).collectList().block();

        Assertions.assertNotNull(output);
        Assertions.assertEquals(2, output.size());
        Assertions.assertTrue(readable.toString().contains("[工具完成] 已写入文件 src/main.js"));
    }

    @Test
    void jsonMessageHandlerShouldForwardAskUserToolRequestAsIs() {
        JsonMessageStreamHandler handler = createHandler();
        StringBuilder readable = new StringBuilder();

        String askUserArgs = "{\"protocolVersion\":1,\"questionSetId\":\"qs_discover_direction_abc\"," +
                "\"stage\":\"discover_direction\",\"questions\":[" +
                "{\"id\":\"q1\",\"prompt\":\"应用方向？\",\"inputType\":\"single_select\"," +
                "\"required\":true,\"options\":[{\"id\":\"a\",\"label\":\"A\"}]}]}";

        List<String> output = handler.handle(Flux.just(
                JSONUtil.toJsonStr(new ToolRequestMessage("qs_discover_direction_abc", "ask_user", askUserArgs))
        ), readable).collectList().block();

        Assertions.assertNotNull(output);
        Assertions.assertEquals(1, output.size());
        // arguments 必须原样透传：questionSetId、protocolVersion、questions 都保留
        Assertions.assertTrue(output.get(0).contains("\"name\":\"ask_user\""));
        Assertions.assertTrue(output.get(0).contains("\"id\":\"qs_discover_direction_abc\""));
        Assertions.assertTrue(output.get(0).contains("\"protocolVersion\":1"));
        Assertions.assertTrue(output.get(0).contains("\"questionSetId\":\"qs_discover_direction_abc\""));
        Assertions.assertTrue(output.get(0).contains("\"id\":\"q1\""));
    }

    @Test
    void jsonMessageHandlerShouldNotProduceAiResponseForAskUserToolExecuted() {
        JsonMessageStreamHandler handler = createHandler();
        StringBuilder readable = new StringBuilder();

        List<String> output = handler.handle(Flux.just(
                JSONUtil.toJsonStr(new ToolExecutedMessage(
                        "qs_abc", "ask_user", "{}", "已向用户提问"))
        ), readable).collectList().block();

        Assertions.assertNotNull(output);
        // ask_user 的 TOOL_EXECUTED 不能再被识别为 AI_RESPONSE 气泡
        Assertions.assertFalse(readable.toString().contains("已向用户提问"),
                "ask_user TOOL_EXECUTED 不应在 readable 中产生新气泡");
    }

    private JsonMessageStreamHandler createHandler() {
        JsonMessageStreamHandler handler = new JsonMessageStreamHandler();
        FileOperationService fileOperationService = new FileOperationService();
        ReflectionTestUtils.setField(handler, "fileOperationService", fileOperationService);
        return handler;
    }
}
