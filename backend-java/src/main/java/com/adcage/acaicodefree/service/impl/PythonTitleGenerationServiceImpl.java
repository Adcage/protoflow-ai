package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.grpc.codegen.CodeGenerationServiceGrpc;
import com.adcage.acaicodefree.grpc.codegen.GenerateAppTitleRequest;
import com.adcage.acaicodefree.grpc.codegen.GenerateSessionTitleRequest;
import com.adcage.acaicodefree.grpc.codegen.GenerateTitleResponse;
import com.adcage.acaicodefree.service.PythonTitleGenerationService;
import com.adcage.acaicodefree.utils.AiServiceErrorSanitizer;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

@Service
@Slf4j
public class PythonTitleGenerationServiceImpl implements PythonTitleGenerationService {

    @GrpcClient("python-agent")
    private CodeGenerationServiceGrpc.CodeGenerationServiceBlockingStub codeGenBlockingStub;

    @Value("${agent.grpc.prompt-enhance-deadline-seconds:30}")
    private int titleDeadlineSeconds;

    @Override
    public String generateAppTitle(String initPrompt, Long userId) {
        ThrowUtils.throwIf(StrUtil.isBlank(initPrompt), ErrorCode.PARAMS_ERROR, "初始化提示词不能为空");
        validateUser(userId);

        GenerateAppTitleRequest grpcRequest = GenerateAppTitleRequest.newBuilder()
                .setInitPrompt(initPrompt)
                .setModelConfigId(0L)
                .setConfigVersion(0)
                .build();
        return executeTitleCall(
                () -> codeGenBlockingStub
                        .withWaitForReady()
                        .withDeadlineAfter(titleDeadlineSeconds, TimeUnit.SECONDS)
                        .generateAppTitle(grpcRequest),
                "generateAppTitle",
                userId
        );
    }

    @Override
    public String generateSessionTitle(String appName, String appInitPrompt, String firstUserMessage, Long userId) {
        ThrowUtils.throwIf(StrUtil.isBlank(firstUserMessage), ErrorCode.PARAMS_ERROR, "会话消息不能为空");
        validateUser(userId);

        GenerateSessionTitleRequest grpcRequest = GenerateSessionTitleRequest.newBuilder()
                .setAppName(StrUtil.blankToDefault(appName, ""))
                .setAppInitPrompt(StrUtil.blankToDefault(appInitPrompt, ""))
                .setFirstUserMessage(firstUserMessage)
                .setModelConfigId(0L)
                .setConfigVersion(0)
                .build();
        return executeTitleCall(
                () -> codeGenBlockingStub
                        .withWaitForReady()
                        .withDeadlineAfter(titleDeadlineSeconds, TimeUnit.SECONDS)
                        .generateSessionTitle(grpcRequest),
                "generateSessionTitle",
                userId
        );
    }

    private void validateUser(Long userId) {
        ThrowUtils.throwIf(userId == null || userId <= 0, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
    }

    private String executeTitleCall(TitleCall titleCall, String action, Long userId) {
        try {
            GenerateTitleResponse response = titleCall.execute();
            if (response.getSuccess() && StrUtil.isNotBlank(response.getTitle())) {
                return response.getTitle();
            }
            String errorMessage = StrUtil.blankToDefault(response.getErrorMessage(), "Python 未返回有效标题");
            throw new BusinessException(
                    ErrorCode.OPERATION_ERROR,
                    AiServiceErrorSanitizer.sanitizeLightweightError(errorMessage, "轻量标题生成服务暂时不可用")
            );
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("gRPC {} 调用失败, userId={}", action, userId, e);
            throw new BusinessException(
                    ErrorCode.SYSTEM_ERROR,
                    AiServiceErrorSanitizer.sanitizeLightweightError(e.getMessage(), "轻量标题生成服务暂时不可用")
            );
        }
    }

    @FunctionalInterface
    private interface TitleCall {
        GenerateTitleResponse execute();
    }
}
