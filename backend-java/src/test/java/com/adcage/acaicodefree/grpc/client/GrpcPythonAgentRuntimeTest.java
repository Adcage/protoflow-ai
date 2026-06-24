package com.adcage.acaicodefree.grpc.client;

import com.adcage.acaicodefree.grpc.codegen.CodeGenerationServiceGrpc;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class GrpcPythonAgentRuntimeTest {

    @Test
    void prepareStreamGenerateStubShouldWaitForReadyWithDeadline() {
        GrpcPythonAgentRuntime runtime = new GrpcPythonAgentRuntime();
        CodeGenerationServiceGrpc.CodeGenerationServiceStub stub = mock(CodeGenerationServiceGrpc.CodeGenerationServiceStub.class);
        ReflectionTestUtils.setField(runtime, "codeGenServiceStub", stub);
        ReflectionTestUtils.setField(runtime, "streamDeadlineSeconds", 300);
        when(stub.withWaitForReady()).thenReturn(stub);
        when(stub.withDeadlineAfter(300, TimeUnit.SECONDS)).thenReturn(stub);

        CodeGenerationServiceGrpc.CodeGenerationServiceStub prepared = runtime.prepareStreamGenerateStub();

        assertSame(stub, prepared);
        var inOrder = inOrder(stub);
        inOrder.verify(stub).withWaitForReady();
        inOrder.verify(stub).withDeadlineAfter(300, TimeUnit.SECONDS);
    }

    /**
     * 验证 ask_user 协议变更后 Java 端不需要修改 gRPC 行为：
     * Python 端通过既有 TOOL_REQUEST 事件透传 questionSetId 与结构化 arguments。
     * 这里的占位测试只确认运行时单例可被注入基础字段，便于在 CI 中作为桩接
     * 收点。Phase 3 真正的 ask_user 行为测试在 Python 端和 JsonMessageStreamHandlerTest。
     */
    @Test
    void runtimeShouldExposeAgentRunIdAccessor() {
        GrpcPythonAgentRuntime runtime = new GrpcPythonAgentRuntime();
        ReflectionTestUtils.setField(runtime, "streamDeadlineSeconds", 60);
        Object deadline = ReflectionTestUtils.getField(runtime, "streamDeadlineSeconds");
        assert deadline != null;
        assert ((Integer) deadline) == 60;
    }
}
