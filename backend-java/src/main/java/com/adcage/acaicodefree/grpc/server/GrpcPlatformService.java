package com.adcage.acaicodefree.grpc.server;

import java.util.ArrayList;
import java.util.List;

import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.config.properties.RuntimeModelProperties;
import com.adcage.acaicodefree.core.build.VueProjectBuildService;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.grpc.common.CodeGenType;
import com.adcage.acaicodefree.grpc.platform.*;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.model.entity.AgentRun;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.runtime.RuntimeModelBundle;
import com.adcage.acaicodefree.model.runtime.RuntimeModelConfig;
import com.adcage.acaicodefree.model.runtime.RuntimeModelRole;
import com.adcage.acaicodefree.model.runtime.RuntimeModelUrlNormalizer;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.AppVersionService;
import com.adcage.acaicodefree.service.ScreenshotService;
import com.adcage.acaicodefree.service.UserService;

import io.grpc.stub.StreamObserver;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.server.service.GrpcService;
import org.springframework.beans.factory.annotation.Value;

@Slf4j
@GrpcService
public class GrpcPlatformService extends PlatformServiceGrpc.PlatformServiceImplBase {

    @Value("${langchain4j.open-ai.chat-model.base-url:}")
    private String defaultBaseUrl;

    @Value("${langchain4j.open-ai.chat-model.api-key:}")
    private String defaultApiKey;

    @Value("${langchain4j.open-ai.chat-model.model-name:}")
    private String defaultModelName;

    @Resource
    private RuntimeModelProperties runtimeModelProperties;

    @Resource
    private AgentRunService agentRunService;
    @Resource
    private AppVersionService appVersionService;
    @Resource
    private AppService appService;
    @Resource
    private UserService userService;
    @Resource
    private VueProjectBuildService vueProjectBuildService;
    @Resource
    private ChatHistoryMapper chatHistoryMapper;
    @Resource
    private ScreenshotService screenshotService;

    @Override
    public void resolveRuntimeModelBundle(ResolveRuntimeModelBundleRequest request,
                                          StreamObserver<ResolveRuntimeModelBundleResponse> responseObserver) {
        try {
            RuntimeModelConfig primaryConfig = resolvePrimaryRuntimeModelConfig();
            if (primaryConfig == null) {
                log.warn("系统运行时模型配置不完整，无法解析模型包");
                responseObserver.onNext(ResolveRuntimeModelBundleResponse.newBuilder()
                        .setSuccess(false)
                        .setErrorMessage("系统模型配置未设置，请在 application-local.yml 或 application.yml 中配置 app.ai.runtime-models.primary 或 langchain4j.open-ai.chat-model")
                        .build());
                responseObserver.onCompleted();
                return;
            }

            List<RuntimeModelConfig> configs = new ArrayList<>();
            for (RuntimeModelRole role : RuntimeModelRole.values()) {
                RuntimeModelConfig resolved = resolveRuntimeModelConfig(role, primaryConfig);
                if (resolved != null) {
                    configs.add(resolved);
                }
            }

            RuntimeModelBundle bundle = RuntimeModelBundle.builder()
                    .success(true)
                    .errorMessage("")
                    .configs(configs)
                    .policyVersion("v1")
                    .billingContext("")
                    .build();

            ResolveRuntimeModelBundleResponse.Builder builder = ResolveRuntimeModelBundleResponse.newBuilder()
                    .setSuccess(bundle.isSuccess())
                    .setPolicyVersion(bundle.getPolicyVersion() != null ? bundle.getPolicyVersion() : "")
                    .setBillingContext(bundle.getBillingContext() != null ? bundle.getBillingContext() : "");

            if (bundle.getErrorMessage() != null) {
                builder.setErrorMessage(bundle.getErrorMessage());
            }

            if (bundle.getConfigs() != null) {
                for (RuntimeModelConfig config : bundle.getConfigs()) {
                    builder.addConfigs(com.adcage.acaicodefree.grpc.platform.RuntimeModelConfig.newBuilder()
                            .setRole(config.getRole() != null ? config.getRole() : "")
                            .setModelConfigId(config.getModelConfigId() != null ? config.getModelConfigId() : 0L)
                            .setConfigVersion(config.getConfigVersion() != null ? config.getConfigVersion() : 0)
                            .setProvider(config.getProvider() != null ? config.getProvider() : "")
                            .setModelName(config.getModelName() != null ? config.getModelName() : "")
                            .setBaseUrl(config.getBaseUrl() != null ? config.getBaseUrl() : "")
                            .setApiKey(config.getApiKey() != null ? config.getApiKey() : "")
                            .setSource(config.getSource() != null ? config.getSource() : "")
                            .setBillingMode(config.getBillingMode() != null ? config.getBillingMode() : "")
                            .build());
                }
            }

            responseObserver.onNext(builder.build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC resolveRuntimeModelBundle failed", e);
            responseObserver.onNext(ResolveRuntimeModelBundleResponse.newBuilder()
                    .setSuccess(false)
                    .setErrorMessage(e.getMessage() != null ? e.getMessage() : "unknown error")
                    .build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void buildVueProject(BuildVueProjectRequest request, StreamObserver<BuildVueProjectResponse> responseObserver) {
        try {
            var result = vueProjectBuildService.buildVueProject(request.getAppId());
            BuildVueProjectResponse.Builder builder = BuildVueProjectResponse.newBuilder()
                    .setSuccess(true)
                    .setDistPath(result.distPath() != null ? result.distPath().toString() : "")
                    .setInstallLog(result.installLog() != null ? result.installLog() : "")
                    .setBuildLog(result.buildLog() != null ? result.buildLog() : "");
            responseObserver.onNext(builder.build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC buildVueProject failed", e);
            responseObserver.onNext(BuildVueProjectResponse.newBuilder()
                    .setSuccess(false)
                    .setErrorMessage(e.getMessage() != null ? e.getMessage() : "unknown error")
                    .build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void deployApp(DeployAppRequest request, StreamObserver<DeployAppResponse> responseObserver) {
        try {
            User user = userService.getById(request.getUserId());
            if (user == null) {
                responseObserver.onNext(DeployAppResponse.newBuilder()
                        .setSuccess(false)
                        .setErrorMessage("User not found: " + request.getUserId())
                        .build());
                responseObserver.onCompleted();
                return;
            }
            String url = appService.deployApp(request.getAppId(), user);
            responseObserver.onNext(DeployAppResponse.newBuilder()
                    .setSuccess(true)
                    .setUrl(url != null ? url : "")
                    .build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC deployApp failed", e);
            responseObserver.onNext(DeployAppResponse.newBuilder()
                    .setSuccess(false)
                    .setErrorMessage(e.getMessage() != null ? e.getMessage() : "unknown error")
                    .build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void completeAgentRun(CompleteAgentRunRequest request, StreamObserver<CompleteAgentRunResponse> responseObserver) {
        try {
            long agentRunId = request.getAgentRunId();
            String loopStateJson = request.getLoopStateJson();
            Long appId = null;

            if (!loopStateJson.isEmpty()) {
                agentRunService.pauseAgentRun(agentRunId, loopStateJson);
            } else if (request.getSuccess()) {
                agentRunService.completeAgentRun(
                        agentRunId,
                        request.getWorkspacePath(),
                        request.getLatencyMs(),
                        (int) request.getTotalInputTokens(),
                        (int) request.getTotalOutputTokens(),
                        (int) request.getTotalCacheReadTokens(),
                        (int) request.getTotalCacheCreationTokens()
                );
            } else {
                agentRunService.failAgentRun(
                        agentRunId,
                        request.getErrorMessage()
                );
            }

            // 获取 AgentRun 实体（含 sessionId、appId、userId）
            AgentRun agentRun = agentRunService.getById(agentRunId);

            // 保存 AI 回复到 chat_history（单路径：由 Python 端在 complete_agent_run 中传入）
            // waiting_for_user 是暂停而非失败，AI 消息（含 AskUser 提问表单）仍需保存
            // 注意：AskUser 触发时 ai_message 可能为空（模型只返回了 tool_calls），
            // 但提问表单数据在 ai_extra.toolCalls 中，仍需落库供前端还原
            String aiMessage = request.getAiMessage();
            String aiStatus = StrUtil.blankToDefault(request.getAiStatus(), "success");
            String aiExtra = normalizeChatHistoryExtra(request.getAiExtra());
            boolean hasContent = StrUtil.isNotBlank(aiMessage) || StrUtil.isNotBlank(aiExtra);
            boolean shouldSaveChatHistory = agentRun != null
                    && hasContent
                    && (request.getSuccess() || "waiting_for_user".equals(aiStatus));
            // [DEBUG] 调试日志：打印 completeAgentRun 的关键参数和判断结果
            log.info("[DEBUG] completeAgentRun | agentRunId={} success={} aiStatus={} "
                    + "aiMessage_len={} aiExtra_len={} hasContent={} shouldSaveChatHistory={} "
                    + "loopStateJson_len={}",
                    agentRunId, request.getSuccess(), aiStatus,
                    aiMessage == null ? -1 : aiMessage.length(),
                    aiExtra == null ? -1 : aiExtra.length(),
                    hasContent, shouldSaveChatHistory,
                    loopStateJson.length());
            if (shouldSaveChatHistory) {
                try {
                    Long sessionId = agentRun.getSessionId();
                    appId = agentRun.getAppId();
                    Long userId = agentRun.getUserId();
                    int latencyMs = request.getLatencyMs();

                    // 获取 seqNo
                    com.mybatisflex.core.query.QueryWrapper maxQuery = com.mybatisflex.core.query.QueryWrapper.create()
                            .eq("sessionId", sessionId)
                            .select("MAX(seqNo) as seqNo");
                    ChatHistory maxRecord = chatHistoryMapper.selectOneByQuery(maxQuery);
                    int seqNo = (maxRecord == null || maxRecord.getSeqNo() == null) ? 1 : maxRecord.getSeqNo() + 1;

                    // 查询应用获取 codeGenType 作为 modelName 字段
                    String modelName = "";
                    if (appId != null) {
                        App app = appService.getById(appId);
                        if (app != null) {
                            modelName = StrUtil.blankToDefault(app.getCodeGenType(), "");
                        }
                    }

                    ChatHistory chatHistory = ChatHistory.builder()
                            .sessionId(sessionId)
                            .seqNo(seqNo)
                            .message(StrUtil.blankToDefault(aiMessage, ""))
                            .messageType("ai")
                            .status(aiStatus)
                            .appId(appId)
                            .userId(userId)
                            .modelName(modelName)
                            .latencyMs(latencyMs)
                            .extra(aiExtra)
                            .build();
                    chatHistoryMapper.insert(chatHistory);
                    log.info("[completeAgentRun] Saved AI chat_history, sessionId={}, agentRunId={}, textLen={}",
                            sessionId, agentRunId, aiMessage.length());
                } catch (Exception e) {
                    log.error("[completeAgentRun] Failed to save AI chat_history, agentRunId={}", agentRunId, e);
                }
            }

            if (agentRun != null) {
                appId = agentRun.getAppId();
            }

            responseObserver.onNext(CompleteAgentRunResponse.newBuilder().setOk(true).build());
            responseObserver.onCompleted();

            // 在响应发送后异步触发封面截图（finally 式）
            if (appId != null) {
                try {
                    screenshotService.triggerCoverGenerationIfNeeded(appId, agentRunId);
                } catch (Exception e) {
                    log.warn("触发封面截图失败（不影响主流程）, appId={}, agentRunId={}", appId, agentRunId, e);
                }
            }
        } catch (Exception e) {
            log.error("gRPC completeAgentRun failed", e);
            responseObserver.onNext(CompleteAgentRunResponse.newBuilder().setOk(false).build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void createAppVersion(CreateAppVersionRequest request, StreamObserver<CreateAppVersionResponse> responseObserver) {
        try {
            Long versionId = appVersionService.createAppVersion(
                    request.getAppId(),
                    request.getAgentRunId(),
                    request.getSourcePath(),
                    request.getBuildPath()
            );
            responseObserver.onNext(CreateAppVersionResponse.newBuilder()
                    .setVersionId(versionId != null ? versionId : 0L)
                    .build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC createAppVersion failed", e);
            responseObserver.onNext(CreateAppVersionResponse.newBuilder().setVersionId(0L).build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void getChatHistory(GetChatHistoryRequest request, StreamObserver<GetChatHistoryResponse> responseObserver) {
        try {
            long sessionId = request.getSessionId();
            int limit = request.getLimit() > 0 ? request.getLimit() : 50;
            // gRPC 内部调用已有 x-internal-secret 认证，无需用户级权限校验
            // 直接通过 Mapper 查询，绕过 listChatHistoryByPage 的 getAndCheckApp 权限检查
            com.mybatisflex.core.query.QueryWrapper queryWrapper = com.mybatisflex.core.query.QueryWrapper.create()
                    .eq("sessionId", sessionId)
                    .orderBy("seqNo", true)
                    .limit(limit);
            List<ChatHistory> historyList = chatHistoryMapper.selectListByQuery(queryWrapper);
            GetChatHistoryResponse.Builder builder = GetChatHistoryResponse.newBuilder();
            for (ChatHistory record : historyList) {
                ChatHistoryEntry.Builder entryBuilder = ChatHistoryEntry.newBuilder()
                        .setId(record.getId() != null ? record.getId() : 0L)
                        .setRole(record.getMessageType() != null ? record.getMessageType() : "")
                        .setContent(record.getMessage() != null ? record.getMessage() : "")
                        .setCreatedAt(record.getCreateTime() != null
                                ? record.getCreateTime().atZone(java.time.ZoneId.systemDefault()).toEpochSecond()
                                : 0L);
                // 从 extra JSON 中提取附件元数据
                String extra = record.getExtra();
                if (extra != null && !extra.isBlank() && extra.contains("attachments")) {
                    try {
                        cn.hutool.json.JSONObject extraJson = JSONUtil.parseObj(extra);
                        if (extraJson.containsKey("attachments")) {
                            entryBuilder.setAttachmentsJson(extraJson.getJSONArray("attachments").toString());
                        }
                    } catch (Exception e) {
                        log.warn("解析 chat_history.extra 附件数据失败, id={}", record.getId(), e);
                    }
                }
                builder.addEntries(entryBuilder.build());
            }
            responseObserver.onNext(builder.build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC getChatHistory failed", e);
            responseObserver.onNext(GetChatHistoryResponse.newBuilder().build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void updateAppCodeGenType(UpdateAppCodeGenTypeRequest request, StreamObserver<UpdateAppCodeGenTypeResponse> responseObserver) {
        try {
            App app = appService.getById(request.getAppId());
            if (app == null) {
                responseObserver.onNext(UpdateAppCodeGenTypeResponse.newBuilder().setOk(false).build());
                responseObserver.onCompleted();
                return;
            }
            CodeGenTypeEnum enumValue = mapCodeGenType(request.getCodeGenType());
            if (enumValue == null) {
                responseObserver.onNext(UpdateAppCodeGenTypeResponse.newBuilder().setOk(false).build());
                responseObserver.onCompleted();
                return;
            }
            app.setCodeGenType(enumValue.getValue());
            appService.updateById(app);
            responseObserver.onNext(UpdateAppCodeGenTypeResponse.newBuilder().setOk(true).build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC updateAppCodeGenType failed", e);
            responseObserver.onNext(UpdateAppCodeGenTypeResponse.newBuilder().setOk(false).build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void getAppDetail(GetAppDetailRequest request, StreamObserver<GetAppDetailResponse> responseObserver) {
        try {
            App app = appService.getById(request.getAppId());
            if (app == null) {
                responseObserver.onNext(GetAppDetailResponse.newBuilder()
                        .setId(0L)
                        .setName("")
                        .setDescription("")
                        .setCodeGenType(CodeGenType.CODE_GEN_TYPE_UNSPECIFIED)
                        .setUserId(0L)
                        .setCreatedAt("")
                        .setUpdatedAt("")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            responseObserver.onNext(GetAppDetailResponse.newBuilder()
                    .setId(app.getId() != null ? app.getId() : 0L)
                    .setName(app.getAppName() != null ? app.getAppName() : "")
                    .setDescription(app.getInitPrompt() != null ? app.getInitPrompt() : "")
                    .setCodeGenType(mapJavaCodeGenType(app.getCodeGenType()))
                    .setUserId(app.getUserId() != null ? app.getUserId() : 0L)
                    .setCreatedAt(app.getCreateTime() != null ? app.getCreateTime().toString() : "")
                    .setUpdatedAt(app.getUpdateTime() != null ? app.getUpdateTime().toString() : "")
                    .build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC getAppDetail failed", e);
            responseObserver.onNext(GetAppDetailResponse.newBuilder()
                    .setId(0L)
                    .setName("")
                    .setDescription("")
                    .setCodeGenType(CodeGenType.CODE_GEN_TYPE_UNSPECIFIED)
                    .setUserId(0L)
                    .setCreatedAt("")
                    .setUpdatedAt("")
                    .build());
            responseObserver.onCompleted();
        }
    }

    @Override
    public void getUserInfo(GetUserInfoRequest request, StreamObserver<GetUserInfoResponse> responseObserver) {
        try {
            User user = userService.getById(request.getUserId());
            if (user == null) {
                responseObserver.onNext(GetUserInfoResponse.newBuilder()
                        .setId(0L)
                        .setUserName("")
                        .setUserAvatar("")
                        .setUserRole("")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            responseObserver.onNext(GetUserInfoResponse.newBuilder()
                    .setId(user.getId() != null ? user.getId() : 0L)
                    .setUserName(user.getUserName() != null ? user.getUserName() : "")
                    .setUserAvatar(user.getUserAvatar() != null ? user.getUserAvatar() : "")
                    .setUserRole(user.getUserRole() != null ? user.getUserRole() : "")
                    .build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC getUserInfo failed", e);
            responseObserver.onNext(GetUserInfoResponse.newBuilder()
                    .setId(0L)
                    .setUserName("")
                    .setUserAvatar("")
                    .setUserRole("")
                    .build());
            responseObserver.onCompleted();
        }
    }

    private CodeGenTypeEnum mapCodeGenType(CodeGenType grpcType) {
        return switch (grpcType) {
            case SINGLE_FILE -> CodeGenTypeEnum.SINGLE_FILE;
            case MULTI_FILE -> CodeGenTypeEnum.MULTI_FILE;
            case VUE_PROJECT -> CodeGenTypeEnum.VUE_PROJECT;
            default -> null;
        };
    }

    private String mapGrpcCodeGenTypeToString(CodeGenType grpcType) {
        return switch (grpcType) {
            case SINGLE_FILE -> "single_file";
            case MULTI_FILE -> "multi-file";
            case VUE_PROJECT -> "vue_project";
            default -> "single_file";
        };
    }

    private CodeGenType mapJavaCodeGenType(String javaType) {
        if (javaType == null) return CodeGenType.SINGLE_FILE;
        CodeGenTypeEnum enumValue = CodeGenTypeEnum.getEnumByValue(javaType);
        if (enumValue == null) return CodeGenType.SINGLE_FILE;
        return switch (enumValue) {
            case SINGLE_FILE -> CodeGenType.SINGLE_FILE;
            case MULTI_FILE -> CodeGenType.MULTI_FILE;
            case VUE_PROJECT -> CodeGenType.VUE_PROJECT;
        };
    }

    private RuntimeModelConfig resolvePrimaryRuntimeModelConfig() {
        RuntimeModelProperties.ModelConfig primary = runtimeModelProperties.getPrimary();
        String resolvedBaseUrl = pickBaseUrl(primary.getBaseUrl(), defaultBaseUrl, RuntimeModelRole.PRIMARY);
        return buildRuntimeModelConfig(
                RuntimeModelRole.PRIMARY,
                firstNonBlank(primary.getProvider(), "openai"),
                resolvedBaseUrl,
                firstNonBlank(primary.getApiKey(), defaultApiKey),
                firstNonBlank(primary.getModelName(), defaultModelName),
                hasConfiguredValue(primary) ? "APP_AI_RUNTIME_MODELS" : "LANGCHAIN4J_DEFAULT",
                "SYSTEM_FREE_FALLBACK"
        );
    }

    private RuntimeModelConfig resolveRuntimeModelConfig(RuntimeModelRole role, RuntimeModelConfig primaryConfig) {
        return switch (role) {
            case LIGHT -> resolveRoleWithFallback(role, runtimeModelProperties.getLight(), primaryConfig);
            case PRIMARY -> primaryConfig;
            case CRITIC -> resolveRoleWithFallback(role, runtimeModelProperties.getCritic(), primaryConfig);
            case REPAIR -> resolveRoleWithFallback(role, runtimeModelProperties.getRepair(), primaryConfig);
        };
    }

    private RuntimeModelConfig resolveRoleWithFallback(RuntimeModelRole role,
                                                       RuntimeModelProperties.ModelConfig roleConfig,
                                                       RuntimeModelConfig fallbackConfig) {
        if (fallbackConfig == null) {
            return null;
        }
        // 判断角色配置是否提供了 apiKey：如果 apiKey 为空，说明该角色未独立配置凭据，
        // 应整体 fallback 到 primary（baseUrl + apiKey + modelName 一起回退），
        // 避免 baseUrl 和 apiKey 来自不同服务商导致认证失败
        boolean hasOwnApiKey = StrUtil.isNotBlank(roleConfig.getApiKey());
        String resolvedBaseUrl = hasOwnApiKey
                ? pickBaseUrl(roleConfig.getBaseUrl(), fallbackConfig.getBaseUrl(), role)
                : fallbackConfig.getBaseUrl();
        String resolvedApiKey = firstNonBlank(roleConfig.getApiKey(), fallbackConfig.getApiKey());
        String resolvedModelName = hasOwnApiKey
                ? firstNonBlank(roleConfig.getModelName(), fallbackConfig.getModelName())
                : fallbackConfig.getModelName();
        return buildRuntimeModelConfig(
                role,
                firstNonBlank(roleConfig.getProvider(), fallbackConfig.getProvider(), "openai"),
                resolvedBaseUrl,
                resolvedApiKey,
                resolvedModelName,
                hasConfiguredValue(roleConfig) ? "APP_AI_RUNTIME_MODELS" : fallbackConfig.getSource(),
                fallbackConfig.getBillingMode()
        );
    }

    private RuntimeModelConfig buildRuntimeModelConfig(RuntimeModelRole role,
                                                       String provider,
                                                       String baseUrl,
                                                       String apiKey,
                                                       String modelName,
                                                       String source,
                                                       String billingMode) {
        if (StrUtil.hasBlank(baseUrl, apiKey, modelName)) {
            return null;
        }
        if (!RuntimeModelUrlNormalizer.isSupportedHttpUrl(baseUrl)) {
            log.warn("运行时模型 baseUrl 非法，已跳过该角色配置, role={}, baseUrl={}", role.getValue(), baseUrl);
            return null;
        }
        String normalizedBaseUrl = RuntimeModelUrlNormalizer.normalize(baseUrl);
        return RuntimeModelConfig.builder()
                .role(role.getValue())
                .modelConfigId(0L)
                .configVersion(0)
                .provider(StrUtil.blankToDefault(provider, "openai"))
                .modelName(modelName)
                .baseUrl(normalizedBaseUrl)
                .apiKey(apiKey)
                .source(StrUtil.blankToDefault(source, "SYSTEM"))
                .billingMode(StrUtil.blankToDefault(billingMode, "SYSTEM_FREE_FALLBACK"))
                .build();
    }

    private boolean hasConfiguredValue(RuntimeModelProperties.ModelConfig modelConfig) {
        return modelConfig != null && StrUtil.isNotBlank(
                firstNonBlank(modelConfig.getProvider(), modelConfig.getBaseUrl(), modelConfig.getApiKey(), modelConfig.getModelName())
        );
    }

    private String pickBaseUrl(String preferredBaseUrl, String fallbackBaseUrl, RuntimeModelRole role) {
        if (StrUtil.isNotBlank(preferredBaseUrl)) {
            if (RuntimeModelUrlNormalizer.isSupportedHttpUrl(preferredBaseUrl)) {
                return preferredBaseUrl;
            }
            log.warn("运行时模型 baseUrl 非法，已回退到备用配置, role={}, baseUrl={}", role.getValue(), preferredBaseUrl);
        }
        return fallbackBaseUrl;
    }

    private String firstNonBlank(String... values) {
        if (values == null) {
            return "";
        }
        for (String value : values) {
            if (StrUtil.isNotBlank(value)) {
                return value;
            }
        }
        return "";
    }

    private String normalizeChatHistoryExtra(String extra) {
        if (StrUtil.isBlank(extra)) {
            return null;
        }
        String trimmed = extra.trim();
        try {
            JSONUtil.parse(trimmed);
            return trimmed;
        } catch (Exception e) {
            log.warn("chat_history.extra 不是合法 JSON，已忽略该字段, extra={}", trimmed, e);
            return null;
        }
    }
}
