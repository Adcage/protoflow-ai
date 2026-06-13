package com.adcage.acaicodefree.grpc.server;

import com.adcage.acaicodefree.grpc.common.CodeGenType;
import com.adcage.acaicodefree.grpc.platform.*;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ModelConfig;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.vo.chat.ChatHistoryVO;
import com.adcage.acaicodefree.core.build.VueProjectBuildService;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.AppVersionService;
import com.adcage.acaicodefree.service.ModelConfigService;
import com.adcage.acaicodefree.service.UserService;
import io.grpc.stub.StreamObserver;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.server.service.GrpcService;
import jakarta.annotation.Resource;

import com.mybatisflex.core.paginate.Page;

@Slf4j
@GrpcService
public class GrpcPlatformService extends PlatformServiceGrpc.PlatformServiceImplBase {

    @Resource
    private ModelConfigService modelConfigService;
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

    @Override
    public void getModelConfig(GetModelConfigRequest request, StreamObserver<GetModelConfigResponse> responseObserver) {
        try {
            long configId = request.getModelConfigId();
            ModelConfig modelConfig = configId > 0 ? modelConfigService.getById(configId) : null;
            if (modelConfig == null) {
                modelConfig = modelConfigService.getServerDefaultConfig();
            }
            if (modelConfig == null) {
                responseObserver.onNext(GetModelConfigResponse.newBuilder()
                        .setProvider("")
                        .setModelName("")
                        .setBaseUrl("")
                        .setApiKey("")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            if (modelConfig.getEnabled() == null || modelConfig.getEnabled() != 1) {
                responseObserver.onNext(GetModelConfigResponse.newBuilder()
                        .setProvider("")
                        .setModelName("")
                        .setBaseUrl("")
                        .setApiKey("")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            if (modelConfig.getConfigVersion() != null && request.getConfigVersion() > 0
                    && !modelConfig.getConfigVersion().equals(request.getConfigVersion())) {
                responseObserver.onNext(GetModelConfigResponse.newBuilder()
                        .setProvider("")
                        .setModelName("")
                        .setBaseUrl("")
                        .setApiKey("")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            responseObserver.onNext(GetModelConfigResponse.newBuilder()
                    .setProvider(modelConfig.getProvider() != null ? modelConfig.getProvider() : "")
                    .setModelName(modelConfig.getModelName() != null ? modelConfig.getModelName() : "")
                    .setBaseUrl(modelConfig.getBaseUrl() != null ? modelConfig.getBaseUrl() : "")
                    .setApiKey(modelConfig.getApiKeyCipher() != null ? modelConfig.getApiKeyCipher() : "")
                    .build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            log.error("gRPC getModelConfig failed", e);
            responseObserver.onNext(GetModelConfigResponse.newBuilder()
                    .setProvider("")
                    .setModelName("")
                    .setBaseUrl("")
                    .setApiKey("")
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
            if (request.getSuccess()) {
                agentRunService.completeAgentRun(
                        request.getAgentRunId(),
                        request.getWorkspacePath(),
                        request.getLatencyMs()
                );
            } else {
                agentRunService.failAgentRun(
                        request.getAgentRunId(),
                        request.getErrorMessage()
                );
            }
            responseObserver.onNext(CompleteAgentRunResponse.newBuilder().setOk(true).build());
            responseObserver.onCompleted();
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
            ChatHistoryQueryRequest query = new ChatHistoryQueryRequest();
            query.setSessionId(request.getSessionId());
            query.setPageSize(request.getLimit() > 0 ? request.getLimit() : 50);
            query.setPageNum(1);
            User adminUser = new User();
            adminUser.setId(0L);
            adminUser.setUserRole("admin");
            Page<ChatHistoryVO> page = appService.listChatHistoryByPage(query, adminUser);
            GetChatHistoryResponse.Builder builder = GetChatHistoryResponse.newBuilder();
            for (ChatHistoryVO record : page.getRecords()) {
                ChatHistoryEntry entry = ChatHistoryEntry.newBuilder()
                        .setId(record.getId() != null ? record.getId() : 0L)
                        .setRole(record.getMessageType() != null ? record.getMessageType() : "")
                        .setContent(record.getMessage() != null ? record.getMessage() : "")
                        .setCreatedAt(record.getCreateTime() != null
                                ? record.getCreateTime().atZone(java.time.ZoneId.systemDefault()).toEpochSecond()
                                : 0L)
                        .build();
                builder.addEntries(entry);
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

    private CodeGenType mapJavaCodeGenType(String javaType) {
        if (javaType == null) return CodeGenType.VUE_PROJECT;
        CodeGenTypeEnum enumValue = CodeGenTypeEnum.getEnumByValue(javaType);
        if (enumValue == null) return CodeGenType.VUE_PROJECT;
        return switch (enumValue) {
            case SINGLE_FILE -> CodeGenType.SINGLE_FILE;
            case MULTI_FILE -> CodeGenType.MULTI_FILE;
            case VUE_PROJECT -> CodeGenType.VUE_PROJECT;
        };
    }
}
