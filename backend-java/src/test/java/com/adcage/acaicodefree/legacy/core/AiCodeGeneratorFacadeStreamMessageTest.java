package com.adcage.acaicodefree.legacy.core;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.legacy.ai.AiCodeGenServiceFactory;
import com.adcage.acaicodefree.legacy.ai.AiCodeGeneratorService;
import com.adcage.acaicodefree.legacy.ai.guardrail.PromptSafetyInputGuardrail;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.StreamMessageTypeEnum;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import dev.langchain4j.agent.tool.ToolExecutionRequest;
import dev.langchain4j.model.output.Response;
import dev.langchain4j.service.TokenStream;
import dev.langchain4j.service.tool.ToolExecution;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.MockitoAnnotations;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.function.Consumer;

import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiCodeGeneratorFacadeStreamMessageTest {

    @Mock
    private AiCodeGenServiceFactory aiCodeGenServiceFactory;

    @Mock
    private AiCodeGeneratorService aiCodeGeneratorService;

    @Mock
    private PromptSafetyInputGuardrail promptSafetyInputGuardrail;

    @InjectMocks
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    AiCodeGeneratorFacadeStreamMessageTest() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void shouldSerializeAiResponseMessage() {
        AiResponseMessage message = new AiResponseMessage("hello");
        String json = JSONUtil.toJsonStr(message);

        Assertions.assertEquals("ai_response", JSONUtil.parseObj(json).getStr("type"));
        Assertions.assertEquals("hello", JSONUtil.parseObj(json).getStr("data"));
    }

    @Test
    void shouldSerializeToolRequestMessage() {
        ToolRequestMessage message = new ToolRequestMessage("1", "writeFile", "{\"path\":\"src/main.js\"}");
        String json = JSONUtil.toJsonStr(message);

        Assertions.assertEquals(StreamMessageTypeEnum.TOOL_REQUEST.getValue(), JSONUtil.parseObj(json).getStr("type"));
        Assertions.assertEquals("writeFile", JSONUtil.parseObj(json).getStr("name"));
    }

    @Test
    void shouldSerializeToolExecutedMessage() {
        ToolExecutedMessage message = new ToolExecutedMessage("1", "writeFile", "{}", "ok");
        String json = JSONUtil.toJsonStr(message);

        Assertions.assertEquals(StreamMessageTypeEnum.TOOL_EXECUTED.getValue(), JSONUtil.parseObj(json).getStr("type"));
        Assertions.assertEquals("ok", JSONUtil.parseObj(json).getStr("result"));
    }

    @Test
    void facadeShouldRouteVueProjectToJsonMessageStream() {
        FakeTokenStream fakeTokenStream = new FakeTokenStream();
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.VUE_PROJECT))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.generateVueProjectCodeStream(1L, "生成按钮")).thenReturn(fakeTokenStream);

        Flux<String> resultFlux = aiCodeGeneratorFacade.generateAndSaveCodeStream("生成按钮", CodeGenTypeEnum.VUE_PROJECT, 1L);
        List<String> result = resultFlux.collectList().block();

        Assertions.assertNotNull(result);
        Assertions.assertTrue(result.stream().anyMatch(item -> item.contains("\"type\":\"ai_response\"")));
        Assertions.assertTrue(result.stream().anyMatch(item -> item.contains("\"type\":\"tool_request\"")));
        Assertions.assertTrue(result.stream().anyMatch(item -> item.contains("\"type\":\"tool_executed\"")));
        verify(aiCodeGeneratorService).generateVueProjectCodeStream(1L, "生成按钮");
    }

    @Test
    void facadeShouldRouteVisualEditPromptToVueModifyStream() {
        FakeTokenStream fakeTokenStream = new FakeTokenStream();
        String visualEditPrompt = "选中元素信息：\n- 标签：button\n\n修改需求：改成主按钮";
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.VUE_PROJECT))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.modifyVueProjectCodeStream(1L, visualEditPrompt)).thenReturn(fakeTokenStream);

        List<String> result = aiCodeGeneratorFacade.generateAndSaveCodeStream(visualEditPrompt, CodeGenTypeEnum.VUE_PROJECT, 1L)
                .collectList()
                .block();

        Assertions.assertNotNull(result);
        Assertions.assertTrue(result.stream().anyMatch(item -> item.contains("\"type\":\"tool_executed\"")));
        verify(aiCodeGeneratorService).modifyVueProjectCodeStream(1L, visualEditPrompt);
    }

    private static class FakeTokenStream implements TokenStream {

        private Consumer<String> onNext;
        private Consumer<ToolExecution> onToolExecuted;
        private Consumer<Response<dev.langchain4j.data.message.AiMessage>> onComplete;

        @Override
        public TokenStream onNext(Consumer<String> consumer) {
            this.onNext = consumer;
            return this;
        }

        @Override
        public TokenStream onRetrieved(Consumer<List<dev.langchain4j.rag.content.Content>> consumer) {
            return this;
        }

        @Override
        public TokenStream onToolExecuted(Consumer<ToolExecution> consumer) {
            this.onToolExecuted = consumer;
            return this;
        }

        @Override
        public TokenStream onComplete(Consumer<Response<dev.langchain4j.data.message.AiMessage>> consumer) {
            this.onComplete = consumer;
            return this;
        }

        @Override
        public TokenStream onError(Consumer<Throwable> consumer) {
            return this;
        }

        @Override
        public TokenStream ignoreErrors() {
            return this;
        }

        @Override
        public void start() {
            if (onNext != null) {
                onNext.accept("你好");
            }
            if (onToolExecuted != null) {
                ToolExecutionRequest request = ToolExecutionRequest.builder()
                        .id("tool-1")
                        .name("writeFile")
                        .arguments("{\"relativeFilePath\":\"src/main.js\"}")
                        .build();
                onToolExecuted.accept(ToolExecution.builder().request(request).result("文件写入成功：src/main.js").build());
            }
            if (onComplete != null) {
                onComplete.accept(Mockito.mock(Response.class));
            }
        }
    }
}
