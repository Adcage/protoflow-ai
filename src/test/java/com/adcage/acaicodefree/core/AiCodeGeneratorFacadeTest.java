package com.adcage.acaicodefree.core;

import com.adcage.acaicodefree.ai.AiCodeGenServiceFactory;
import com.adcage.acaicodefree.ai.AiCodeGeneratorService;
import com.adcage.acaicodefree.ai.guardrail.PromptSafetyInputGuardrail;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import dev.langchain4j.service.TokenStream;
import dev.langchain4j.service.tool.ToolExecution;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.util.List;
import java.util.function.Consumer;

import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiCodeGeneratorFacadeTest {

    @Mock
    private AiCodeGenServiceFactory aiCodeGenServiceFactory;

    @Mock
    private AiCodeGeneratorService aiCodeGeneratorService;

    @Mock
    private PromptSafetyInputGuardrail promptSafetyInputGuardrail;

    @InjectMocks
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    AiCodeGeneratorFacadeTest() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void shouldRouteSingleFileStreamWithAppId() {
        TokenStream tokenStream = new EmptyTokenStream();
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.SINGLE_FILE))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.generateSingleFileCodeStream(1L, "生成页面")).thenReturn(tokenStream);

        List<String> result = aiCodeGeneratorFacade.generateAndSaveCodeStream("生成页面", CodeGenTypeEnum.SINGLE_FILE, 1L)
                .collectList()
                .block();

        Assertions.assertNotNull(result);
        verify(aiCodeGeneratorService).generateSingleFileCodeStream(1L, "生成页面");
    }

    @Test
    void shouldRouteSingleFileModifyStreamWhenVisualEditPromptProvided() {
        String visualEditPrompt = "选中元素信息：\n- 标签：h1\n\n修改需求：改标题";
        TokenStream tokenStream = new EmptyTokenStream();
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.SINGLE_FILE))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.modifySingleFileCodeStream(1L, visualEditPrompt)).thenReturn(tokenStream);

        List<String> result = aiCodeGeneratorFacade.generateAndSaveCodeStream(visualEditPrompt, CodeGenTypeEnum.SINGLE_FILE, 1L)
                .collectList()
                .block();

        Assertions.assertNotNull(result);
        verify(aiCodeGeneratorService).modifySingleFileCodeStream(1L, visualEditPrompt);
    }

    @Test
    void shouldRouteVueProjectStreamToJsonMessageFlow() {
        TokenStream tokenStream = new EmptyTokenStream();
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.VUE_PROJECT))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.generateVueProjectCodeStream(1L, "生成工程")).thenReturn(tokenStream);

        List<String> result = aiCodeGeneratorFacade.generateAndSaveCodeStream("生成工程", CodeGenTypeEnum.VUE_PROJECT, 1L)
                .collectList()
                .block();

        Assertions.assertNotNull(result);
        Assertions.assertTrue(result.stream().anyMatch(item -> item.contains("ai_response")));
        verify(aiCodeGeneratorService).generateVueProjectCodeStream(1L, "生成工程");
    }

    @Test
    void shouldRouteVueProjectModifyStreamWhenVisualEditPromptProvided() {
        TokenStream tokenStream = new EmptyTokenStream();
        String visualEditPrompt = "选中元素信息：\n- 页面路径：/\n\n修改需求：改按钮圆角";
        when(aiCodeGenServiceFactory.getService(anyLong(), eq(CodeGenTypeEnum.VUE_PROJECT))).thenReturn(aiCodeGeneratorService);
        when(aiCodeGeneratorService.modifyVueProjectCodeStream(1L, visualEditPrompt)).thenReturn(tokenStream);

        List<String> result = aiCodeGeneratorFacade.generateAndSaveCodeStream(visualEditPrompt, CodeGenTypeEnum.VUE_PROJECT, 1L)
                .collectList()
                .block();

        Assertions.assertNotNull(result);
        verify(aiCodeGeneratorService).modifyVueProjectCodeStream(1L, visualEditPrompt);
    }

    private static class EmptyTokenStream implements TokenStream {

        private Consumer<String> onNext;
        private Consumer<dev.langchain4j.model.output.Response<dev.langchain4j.data.message.AiMessage>> onComplete;

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
            return this;
        }

        @Override
        public TokenStream onComplete(Consumer<dev.langchain4j.model.output.Response<dev.langchain4j.data.message.AiMessage>> consumer) {
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
                onNext.accept("hello");
            }
            if (onComplete != null) {
                onComplete.accept(null);
            }
        }
    }
}
