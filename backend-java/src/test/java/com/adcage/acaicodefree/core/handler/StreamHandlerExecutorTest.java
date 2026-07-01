package com.adcage.acaicodefree.core.handler;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;

class StreamHandlerExecutorTest {

    @Test
    void jsonHandlerShouldKeepPlainTextChunks() {
        StreamHandlerExecutor executor = createExecutor();
        StringBuilder readable = new StringBuilder();

        executor.handle(CodeGenTypeEnum.SINGLE_FILE, Flux.just("a", "b"), readable).collectList().block();

        Assertions.assertEquals("ab", readable.toString());
    }

    @Test
    void shouldRouteVueProjectToJsonHandler() {
        StreamHandlerExecutor executor = createExecutor();
        StringBuilder readable = new StringBuilder();

        executor.handle(CodeGenTypeEnum.VUE_PROJECT, Flux.just("{\"type\":\"ai_response\",\"data\":\"ok\"}"), readable)
                .collectList()
                .block();

        Assertions.assertEquals("ok", readable.toString());
    }

    @Test
    void shouldRouteMultiFileToJsonHandlerForToolEvents() {
        StreamHandlerExecutor executor = createExecutor();
        StringBuilder readable = new StringBuilder();

        var chunks = executor.handle(CodeGenTypeEnum.MULTI_FILE, Flux.just(
                        "{\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":\"{\\\"relativeFilePath\\\":\\\"index.html\\\"}\",\"type\":\"tool_request\"}",
                        "{\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":\"{\\\"relativeFilePath\\\":\\\"index.html\\\"}\",\"result\":\"文件写入成功：index.html\",\"type\":\"tool_executed\"}"
                ), readable)
                .collectList()
                .block();

        Assertions.assertNotNull(chunks);
        Assertions.assertEquals(2, chunks.size());
        Assertions.assertEquals("", readable.toString());
        Assertions.assertTrue(chunks.get(0).contains("\"type\":\"tool_request\""));
        Assertions.assertTrue(chunks.get(1).contains("\"type\":\"tool_executed\""));
    }

    @Test
    void shouldRouteSingleFileToJsonHandlerForToolEvents() {
        StreamHandlerExecutor executor = createExecutor();
        StringBuilder readable = new StringBuilder();

        var chunks = executor.handle(CodeGenTypeEnum.SINGLE_FILE, Flux.just(
                        "{\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":\"{\\\"relativeFilePath\\\":\\\"index.html\\\"}\",\"type\":\"tool_request\"}",
                        "{\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":\"{\\\"relativeFilePath\\\":\\\"index.html\\\"}\",\"result\":\"文件写入成功：index.html\",\"type\":\"tool_executed\"}"
                ), readable)
                .collectList()
                .block();

        Assertions.assertNotNull(chunks);
        Assertions.assertEquals(2, chunks.size());
        Assertions.assertEquals("", readable.toString());
        Assertions.assertTrue(chunks.get(0).contains("\"type\":\"tool_request\""));
        Assertions.assertTrue(chunks.get(1).contains("\"type\":\"tool_executed\""));
    }

    private StreamHandlerExecutor createExecutor() {
        StreamHandlerExecutor executor = new StreamHandlerExecutor();
        ReflectionTestUtils.setField(executor, "simpleTextStreamHandler", new SimpleTextStreamHandler());
        ReflectionTestUtils.setField(executor, "jsonMessageStreamHandler", new JsonMessageStreamHandler());
        return executor;
    }
}
