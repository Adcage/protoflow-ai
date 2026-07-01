package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.grpc.codegen.CodeGenerationServiceGrpc;
import com.adcage.acaicodefree.grpc.codegen.EnhancePromptResponse;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PythonPromptEnhanceServiceImplTest {

    @Test
    void enhancePromptShouldSanitizeAuthenticationFailure() {
        PythonPromptEnhanceServiceImpl service = new PythonPromptEnhanceServiceImpl();
        CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub stub =
                mock(CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub.class);
        ReflectionTestUtils.setField(service, "codeGenBlockingStub", stub);
        ReflectionTestUtils.setField(service, "promptEnhanceDeadlineSeconds", 12);

        when(stub.withWaitForReady()).thenReturn(stub);
        when(stub.withDeadlineAfter(12, TimeUnit.SECONDS)).thenReturn(stub);
        when(stub.enhancePrompt(any())).thenReturn(
                EnhancePromptResponse.newBuilder()
                        .setSuccess(false)
                        .setErrorMessage("[63002] 提示词优化失败: Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key: sk-test-secret is invalid'}}")
                        .build()
        );

        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> service.enhancePrompt("做一个登录页", 1L)
        );

        assertEquals("轻量模型鉴权失败，请检查 AI_LIGHT_API_KEY、AI_LIGHT_BASE_URL 和 AI_LIGHT_MODEL 配置", exception.getMessage());
    }
}
