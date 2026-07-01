package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.grpc.codegen.CodeGenerationServiceGrpc;
import com.adcage.acaicodefree.grpc.codegen.EnhancePromptRequest;
import com.adcage.acaicodefree.grpc.codegen.EnhancePromptResponse;
import com.adcage.acaicodefree.service.PythonPromptEnhanceService;
import com.adcage.acaicodefree.utils.AiServiceErrorSanitizer;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Service
@Slf4j
public class PythonPromptEnhanceServiceImpl implements PythonPromptEnhanceService {

    @GrpcClient("python-agent")
    private CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub codeGenBlockingStub;

    @Value("${agent.grpc.prompt-enhance-deadline-seconds:30}")
    private int promptEnhanceDeadlineSeconds;

    @Override
    public String enhancePrompt(String prompt, Long userId) {
        ThrowUtils.throwIf(StrUtil.isBlank(prompt), ErrorCode.PARAMS_ERROR, "提示词不能为空");
        ThrowUtils.throwIf(userId == null || userId <= 0, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");

        EnhancePromptRequest grpcRequest = EnhancePromptRequest.newBuilder()
                .setPrompt(prompt)
                .setModelConfigId(0L)
                .setConfigVersion(0)
                .build();

        try {
            EnhancePromptResponse response = codeGenBlockingStub
                    .withWaitForReady()
                    .withDeadlineAfter(promptEnhanceDeadlineSeconds, TimeUnit.SECONDS)
                    .enhancePrompt(grpcRequest);
            if (response.getSuccess() && StrUtil.isNotBlank(response.getEnhancedPrompt())) {
                return response.getEnhancedPrompt();
            }
            String errorMessage = StrUtil.blankToDefault(response.getErrorMessage(), "Python 未返回有效提示词增强结果");
            throw new BusinessException(
                    ErrorCode.OPERATION_ERROR,
                    AiServiceErrorSanitizer.sanitizeLightweightError(errorMessage, "提示词优化服务暂时不可用")
            );
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("gRPC enhancePrompt 调用失败, userId={}", userId, e);
            throw new BusinessException(
                    ErrorCode.SYSTEM_ERROR,
                    AiServiceErrorSanitizer.sanitizeLightweightError(e.getMessage(), "提示词优化服务暂时不可用")
            );
        }
    }
}
