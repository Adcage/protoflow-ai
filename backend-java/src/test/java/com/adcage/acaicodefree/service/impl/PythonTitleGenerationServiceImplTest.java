package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.grpc.codegen.CodeGenerationServiceGrpc;
import com.adcage.acaicodefree.grpc.codegen.GenerateTitleResponse;
import com.adcage.acaicodefree.exception.BusinessException;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PythonTitleGenerationServiceImplTest {

    @Test
    void generateAppTitleShouldDelegateToGrpcStub() {
        PythonTitleGenerationServiceImpl service = new PythonTitleGenerationServiceImpl();
        CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub stub =
                mock(CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub.class);
        ReflectionTestUtils.setField(service, "codeGenBlockingStub", stub);
        ReflectionTestUtils.setField(service, "titleDeadlineSeconds", 12);

        when(stub.withWaitForReady()).thenReturn(stub);
        when(stub.withDeadlineAfter(12, TimeUnit.SECONDS)).thenReturn(stub);
        when(stub.generateAppTitle(any())).thenReturn(
                GenerateTitleResponse.newBuilder().setSuccess(true).setTitle("智能排班助手").build()
        );

        String title = service.generateAppTitle("请帮我做一个排班系统", 1L);

        assertEquals("智能排班助手", title);
        var inOrder = inOrder(stub);
        inOrder.verify(stub).withWaitForReady();
        inOrder.verify(stub).withDeadlineAfter(12, TimeUnit.SECONDS);
        inOrder.verify(stub).generateAppTitle(any());
    }

    @Test
    void generateSessionTitleShouldDelegateToGrpcStub() {
        PythonTitleGenerationServiceImpl service = new PythonTitleGenerationServiceImpl();
        CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub stub =
                mock(CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub.class);
        ReflectionTestUtils.setField(service, "codeGenBlockingStub", stub);
        ReflectionTestUtils.setField(service, "titleDeadlineSeconds", 8);

        when(stub.withWaitForReady()).thenReturn(stub);
        when(stub.withDeadlineAfter(8, TimeUnit.SECONDS)).thenReturn(stub);
        when(stub.generateSessionTitle(any())).thenReturn(
                GenerateTitleResponse.newBuilder().setSuccess(true).setTitle("登录页视觉优化").build()
        );

        String title = service.generateSessionTitle("后台管理系统", "请做一个后台", "请先优化登录页", 1L);

        assertEquals("登录页视觉优化", title);
        var inOrder = inOrder(stub);
        inOrder.verify(stub).withWaitForReady();
        inOrder.verify(stub).withDeadlineAfter(8, TimeUnit.SECONDS);
        inOrder.verify(stub).generateSessionTitle(any());
    }

    @Test
    void generateAppTitleShouldSanitizeMissingConfigFailure() {
        PythonTitleGenerationServiceImpl service = new PythonTitleGenerationServiceImpl();
        CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub stub =
                mock(CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub.class);
        ReflectionTestUtils.setField(service, "codeGenBlockingStub", stub);
        ReflectionTestUtils.setField(service, "titleDeadlineSeconds", 8);

        when(stub.withWaitForReady()).thenReturn(stub);
        when(stub.withDeadlineAfter(8, TimeUnit.SECONDS)).thenReturn(stub);
        when(stub.generateAppTitle(any())).thenReturn(
                GenerateTitleResponse.newBuilder()
                        .setSuccess(false)
                        .setErrorMessage("[64003] 模型 API Key 不能为空")
                        .build()
        );

        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> service.generateAppTitle("请帮我做一个排班系统", 1L)
        );

        assertEquals(
                "轻量模型配置不完整，请检查 AI_LIGHT_BASE_URL、AI_LIGHT_API_KEY、AI_LIGHT_MODEL 和 provider 配置",
                exception.getMessage()
        );
    }
}
