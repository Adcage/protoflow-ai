package com.adcage.acaicodefree.grpc.client;

import com.adcage.acaicodefree.core.generation.ActiveGeneration;
import com.adcage.acaicodefree.core.generation.ActiveGenerationManager;
import com.adcage.acaicodefree.grpc.codegen.*;
import com.adcage.acaicodefree.grpc.common.*;
import com.adcage.acaicodefree.grpc.common.GenerationMode;
import com.adcage.acaicodefree.ai.model.message.AgentStartMessage;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.StreamMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.StatusMessage;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import cn.hutool.json.JSONUtil;
import io.grpc.stub.StreamObserver;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;
import reactor.core.publisher.Sinks.EmitResult;

import java.util.Map;
import java.util.concurrent.TimeUnit;

import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class GrpcPythonAgentRuntime implements CodeGenerationRuntime {

    private static final String NAME = "python-agent";

    @GrpcClient("python-agent")
    private CodeGenerationServiceGrpc.CodeGenerationServiceStub codeGenServiceStub;

    @Resource
    private ActiveGenerationManager activeGenerationManager;

    @Value("${agent.grpc.stream-deadline-seconds:300}")
    private int streamDeadlineSeconds;

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public Flux<String> stream(CodeGenerationRequest request) {
        // multicast: 允许内部监听器和 SSE 订阅者互不影响
        Sinks.Many<String> sink = Sinks.many().multicast().directBestEffort();

        com.adcage.acaicodefree.grpc.codegen.CodeGenerationRequest grpcRequest = buildGrpcRequest(request);

        // 注册内存中的活跃生成状态（computeIfAbsent，不会覆盖 AppServiceImpl 已注册的 handler）
        ActiveGeneration activeGen = activeGenerationManager.register(
                request.getSessionId(), request.getAgentRunId()
        );
        // 存储 Sink 供 SSE 重连端点取用
        activeGen.setSink(sink);

        // ── 内部订阅者：保证 Sink 始终有 >= 1 个订阅者 ──
        // 即使 SSE 断开（订阅者 B 被移除），此订阅者仍存在。
        // 确保 tryEmitComplete() 不因 FAIL_ZERO_SUBSCRIBER 而静默失败。
        // onComplete 时触发 AppServiceImpl 注册的 handler 完成入库。
        sink.asFlux().subscribe(
                null,  // onNext: no-op（StreamObserver.onNext 中已更新 activeGen）
                error -> {
                    log.error("[Stream] Internal subscriber error: {}, sessionId={}, textLen={}",
                            error.getMessage(), request.getSessionId(), activeGen.getText().length(), error);
                    activeGen.setCompleted(true);
                    activeGen.fireGenerationCompleted(activeGen.getText());
                },
                () -> {
                    log.info("[Stream] Internal subscriber onComplete, sessionId={}, agentRunId={}, textLen={}",
                            request.getSessionId(), request.getAgentRunId(), activeGen.getText().length());
                    activeGen.fireGenerationCompleted(activeGen.getText());
                }
        );

        prepareStreamGenerateStub().streamGenerate(grpcRequest, new StreamObserver<>() {
            @Override
            public void onNext(CodeGenerationEvent event) {
                // 累积 AI 文本（始终执行，无论是否有 SSE 订阅者）
                if (event.getEventType() == com.adcage.acaicodefree.grpc.common.EventType.AI_RESPONSE) {
                    String text = event.getAiResponse().getText();
                    if (text != null) {
                        activeGen.appendText(text);
                    }
                }

                // 采集工具调用事件 → 入库到 extra.toolCalls
                if (event.getEventType() == com.adcage.acaicodefree.grpc.common.EventType.TOOL_REQUEST) {
                    ToolRequestData req = event.getToolRequest();
                    activeGen.addToolCall(Map.of(
                            "type", "request",
                            "id", req.getId(),
                            "name", req.getName(),
                            "arguments", req.getArguments(),
                            "agentName", event.getAgentName()
                    ));
                }
                if (event.getEventType() == com.adcage.acaicodefree.grpc.common.EventType.TOOL_EXECUTED) {
                    ToolExecutedData exec = event.getToolExecuted();
                    activeGen.addToolCall(Map.of(
                            "type", "executed",
                            "id", exec.getId(),
                            "name", exec.getName(),
                            "arguments", exec.getArguments(),
                            "result", exec.getResult(),
                            "agentName", event.getAgentName()
                    ));
                }

                String json = mapEventToStreamMessageJson(event);
                if (json != null) {
                    EmitResult result = sink.tryEmitNext(json);
                    if (result != EmitResult.OK) {
                        log.warn("[Stream] tryEmitNext failed: result={}, sessionId={}, jsonLen={}",
                                result, request.getSessionId(), json.length());
                    }
                }
            }

            @Override
            public void onError(Throwable t) {
                log.error("[Stream] gRPC StreamGenerate error: {}, sessionId={}, textLen={}",
                        t.getMessage(), request.getSessionId(), activeGen.getText().length(), t);
                activeGen.setCompleted(true);
                sink.tryEmitNext(JSONUtil.toJsonStr(new AiResponseMessage("生成失败：" + t.getMessage(), "")));
                sink.tryEmitComplete();
            }

            @Override
            public void onCompleted() {
                log.info("[Stream] gRPC StreamGenerate onCompleted, sessionId={}, agentRunId={}, textLen={}",
                        request.getSessionId(), request.getAgentRunId(), activeGen.getText().length());
                activeGen.setCompleted(true);
                EmitResult result = sink.tryEmitComplete();
                log.info("[Stream] tryEmitComplete result={}, sessionId={}", result, request.getSessionId());
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
                .setWorkspacePath(request.getWorkspacePath() != null ? request.getWorkspacePath() : "");

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

        // runtime_options_json: Playground 模式传递工具勾选列表等运行时选项
        if (request.getRuntimeOptionsJson() != null && !request.getRuntimeOptionsJson().isEmpty()) {
            builder.setRuntimeOptionsJson(request.getRuntimeOptionsJson());
        }

        // 映射附件列表
        if (request.getAttachments() != null && !request.getAttachments().isEmpty()) {
            for (var att : request.getAttachments()) {
                builder.addAttachments(com.adcage.acaicodefree.grpc.common.AttachmentInfo.newBuilder()
                        .setId(att.getId() != null ? att.getId() : "")
                        .setFileName(att.getFileName() != null ? att.getFileName() : "")
                        .setFileSize(att.getFileSize() != null ? att.getFileSize() : 0L)
                        .setMimeType(att.getMimeType() != null ? att.getMimeType() : "")
                        .setStorageType(att.getStorageType() != null ? att.getStorageType() : "")
                        .setStoragePath(att.getStoragePath() != null ? att.getStoragePath() : "")
                        .setUrl(att.getUrl() != null ? att.getUrl() : "")
                        .build());
            }
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
        if (type == null) return CodeGenType.SINGLE_FILE;
        return switch (type) {
            case "single_file" -> CodeGenType.SINGLE_FILE;
            case "multi-file" -> CodeGenType.MULTI_FILE;
            case "vue_project" -> CodeGenType.VUE_PROJECT;
            default -> CodeGenType.SINGLE_FILE;
        };
    }

    private GenerationMode mapGenerationMode(String mode) {
        if (mode == null || mode.isBlank()) return GenerationMode.APPLICATION;
        return switch (mode.toLowerCase()) {
            case "application" -> GenerationMode.APPLICATION;
            case "test_playground" -> GenerationMode.TEST_PLAYGROUND;
            default -> GenerationMode.GENERATION_MODE_UNSPECIFIED;
        };
    }

    private String mapEventToStreamMessageJson(CodeGenerationEvent event) {
        String agentName = event.getAgentName();
        switch (event.getEventType()) {
            case AI_RESPONSE:
                return JSONUtil.toJsonStr(new AiResponseMessage(event.getAiResponse().getText(), agentName));
            case TOOL_REQUEST:
                ToolRequestData req = event.getToolRequest();
                return JSONUtil.toJsonStr(new ToolRequestMessage(req.getId(), req.getName(), req.getArguments(), agentName));
            case TOOL_EXECUTED:
                ToolExecutedData exec = event.getToolExecuted();
                return JSONUtil.toJsonStr(new ToolExecutedMessage(exec.getId(), exec.getName(), exec.getArguments(), exec.getResult(), agentName));
            case ERROR:
                return JSONUtil.toJsonStr(new AiResponseMessage("生成失败：" + event.getError().getMessage(), agentName));
            case DONE:
                return JSONUtil.toJsonStr(new AiResponseMessage(event.getDone().getMessage(), agentName));
            case STATUS:
                return JSONUtil.toJsonStr(new StatusMessage(event.getStatus().getMessage(), agentName));
            case AGENT_START:
                return JSONUtil.toJsonStr(new AgentStartMessage(event.getAgentName()));
            default:
                return null;
        }
    }
}
