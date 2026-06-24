package com.adcage.acaicodefree.grpc.client;

import com.adcage.acaicodefree.grpc.codegen.*;
import com.adcage.acaicodefree.grpc.common.*;
import com.adcage.acaicodefree.grpc.common.GenerationMode;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.StreamMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.StatusMessage;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import cn.hutool.json.JSONUtil;
import io.grpc.stub.StreamObserver;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class GrpcPythonAgentRuntime implements CodeGenerationRuntime {

    private static final String NAME = "python-agent";

    @GrpcClient("python-agent")
    private CodeGenerationServiceGrpc.CodeGenerationServiceStub codeGenServiceStub;

    @Value("${agent.grpc.stream-deadline-seconds:300}")
    private int streamDeadlineSeconds;

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public Flux<String> stream(CodeGenerationRequest request) {
        Sinks.Many<String> sink = Sinks.many().unicast().onBackpressureBuffer();

        com.adcage.acaicodefree.grpc.codegen.CodeGenerationRequest grpcRequest = buildGrpcRequest(request);

        prepareStreamGenerateStub().streamGenerate(grpcRequest, new StreamObserver<>() {
            @Override
            public void onNext(CodeGenerationEvent event) {
                String json = mapEventToStreamMessageJson(event);
                if (json != null) {
                    sink.tryEmitNext(json);
                }
            }

            @Override
            public void onError(Throwable t) {
                log.error("gRPC StreamGenerate error: {}", t.getMessage(), t);
                sink.tryEmitNext(JSONUtil.toJsonStr(new AiResponseMessage("生成失败：" + t.getMessage())));
                sink.tryEmitComplete();
            }

            @Override
            public void onCompleted() {
                sink.tryEmitComplete();
            }
        });

        return sink.asFlux();
    }

    CodeGenerationServiceGrpc.CodeGenerationServiceStub prepareStreamGenerateStub() {
        return codeGenServiceStub
                .withWaitForReady()
                .withDeadlineAfter(streamDeadlineSeconds, TimeUnit.SECONDS);
    }

    private com.adcage.acaicodefree.grpc.codegen.CodeGenerationRequest buildGrpcRequest(CodeGenerationRequest request) {
        com.adcage.acaicodefree.grpc.codegen.CodeGenerationRequest.Builder builder = com.adcage.acaicodefree.grpc.codegen.CodeGenerationRequest.newBuilder()
                .setAgentRunId(String.valueOf(request.getAgentRunId()))
                .setAppId(request.getAppId() != null ? request.getAppId() : 0L)
                .setSessionId(request.getSessionId() != null ? request.getSessionId() : 0L)
                .setUserId(request.getLoginUser() != null ? request.getLoginUser().getId() : 0L)
                .setPrompt(request.getMessage() != null ? request.getMessage() : "")
                .setWorkspacePath(request.getWorkspacePath() != null ? request.getWorkspacePath() : "")
                .setModelConfigId(request.getModelConfigId() != null ? request.getModelConfigId() : 0L)
                .setConfigVersion(request.getConfigVersion() != null ? request.getConfigVersion() : 0);

        if (request.getLoopStateJson() != null && !request.getLoopStateJson().isEmpty()) {
            builder.setLoopStateJson(request.getLoopStateJson());
        }

        // is_test: 从请求中获取（由 Java Service 层根据用户角色设置）
        if (request.getIsTest() != null && request.getIsTest()) {
            builder.setIsTest(true);
        }

        if (request.getCodeGenTypeEnum() != null) {
            builder.setCodeGenType(mapJavaCodeGenType(request.getCodeGenTypeEnum()));
        } else if (request.getApp() != null && request.getApp().getCodeGenType() != null) {
            builder.setCodeGenType(mapJavaCodeGenTypeStr(request.getApp().getCodeGenType()));
        }

        if (request.getGenerationMode() != null) {
            builder.setGenerationMode(mapGenerationMode(request.getGenerationMode()));
        } else if (request.getApp() != null && request.getApp().getGenerationMode() != null) {
            builder.setGenerationMode(mapGenerationMode(request.getApp().getGenerationMode()));
        }

        return builder.build();
    }

    private CodeGenType mapJavaCodeGenType(com.adcage.acaicodefree.model.enums.CodeGenTypeEnum type) {
        return switch (type) {
            case SINGLE_FILE -> CodeGenType.SINGLE_FILE;
            case MULTI_FILE -> CodeGenType.MULTI_FILE;
            case VUE_PROJECT -> CodeGenType.VUE_PROJECT;
        };
    }

    private CodeGenType mapJavaCodeGenTypeStr(String type) {
        if (type == null) return CodeGenType.VUE_PROJECT;
        return switch (type) {
            case "single_file" -> CodeGenType.SINGLE_FILE;
            case "multi-file" -> CodeGenType.MULTI_FILE;
            case "vue_project" -> CodeGenType.VUE_PROJECT;
            default -> CodeGenType.VUE_PROJECT;
        };
    }

    private GenerationMode mapGenerationMode(String mode) {
        if (mode == null || mode.isBlank()) return GenerationMode.APPLICATION;
        return switch (mode.toLowerCase()) {
            case "application" -> GenerationMode.APPLICATION;
            default -> GenerationMode.GENERATION_MODE_UNSPECIFIED;
        };
    }

    private String mapEventToStreamMessageJson(CodeGenerationEvent event) {
        switch (event.getEventType()) {
            case AI_RESPONSE:
                return JSONUtil.toJsonStr(new AiResponseMessage(event.getAiResponse().getText()));
            case TOOL_REQUEST:
                ToolRequestData req = event.getToolRequest();
                return JSONUtil.toJsonStr(new ToolRequestMessage(req.getId(), req.getName(), req.getArguments()));
            case TOOL_EXECUTED:
                ToolExecutedData exec = event.getToolExecuted();
                return JSONUtil.toJsonStr(new ToolExecutedMessage(exec.getId(), exec.getName(), exec.getArguments(), exec.getResult()));
            case ERROR:
                return JSONUtil.toJsonStr(new AiResponseMessage("生成失败：" + event.getError().getMessage()));
            case DONE:
                return JSONUtil.toJsonStr(new AiResponseMessage(event.getDone().getMessage()));
            case STATUS:
                return JSONUtil.toJsonStr(new StatusMessage(event.getStatus().getMessage()));
            case AGENT_START:
                return null;
            default:
                return null;
        }
    }
}
