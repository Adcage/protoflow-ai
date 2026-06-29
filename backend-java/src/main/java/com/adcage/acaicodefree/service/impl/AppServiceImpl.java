package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.ObjUtil;
import cn.hutool.core.util.RandomUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.core.artifact.ArtifactManifestReader;
import com.adcage.acaicodefree.core.build.VueProjectBuildService;
import com.adcage.acaicodefree.core.build.VueProjectBuildService.BuildResult;
import com.adcage.acaicodefree.core.generation.ActiveGeneration;
import com.adcage.acaicodefree.core.generation.ActiveGenerationManager;
import com.adcage.acaicodefree.core.handler.StreamHandlerExecutor;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.AgentRunMapper;
import com.adcage.acaicodefree.mapper.AppCategoryMapper;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.model.dto.app.AppAddRequest;
import com.adcage.acaicodefree.model.dto.app.MarketplaceQueryRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatAttachmentInfo;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.dto.app.AppQueryRequest;
import com.adcage.acaicodefree.model.entity.AgentRun;
import com.adcage.acaicodefree.model.entity.AppCategory;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.ChatSession;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.app.AppVO;
import com.adcage.acaicodefree.model.vo.app.ArtifactManifestVO;
import com.adcage.acaicodefree.model.vo.app.MarketplaceAppVO;
import com.adcage.acaicodefree.model.vo.chat.ChatHistoryVO;
import com.adcage.acaicodefree.model.vo.chat.ChatSessionVO;
import com.adcage.acaicodefree.model.vo.chat.ToolEventVO;
import com.adcage.acaicodefree.model.vo.user.UserVO;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntimeRouter;
import com.adcage.acaicodefree.service.AgentRunService;
import com.mybatisflex.core.paginate.Page;
import com.adcage.acaicodefree.service.UserService;
import com.adcage.acaicodefree.service.ScreenshotService;
import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.spring.service.impl.ServiceImpl;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.service.AppService;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Collectors;

/**
 * 应用 服务层实现。
 *
 * @author adcage
 */
@Service
public class AppServiceImpl extends ServiceImpl<AppMapper, App> implements AppService {

    private static final Logger log = LoggerFactory.getLogger(AppServiceImpl.class);

    private static final List<String> ALLOWED_CATEGORIES = List.of("工具", "游戏", "社交", "教育", "商业", "创意");

    private static final Set<String> FORK_EXCLUDED_DIRS = Set.of(
            "node_modules", ".git", "dist", "build", "target", ".mvn", ".idea", ".vscode", ".cache");

    private static final Set<String> FORK_EXCLUDED_FILE_NAMES = Set.of(".ds_store", ".env");

    private static final Set<String> FORK_EXCLUDED_FILE_EXTENSIONS = Set.of(".log", ".tmp", ".cache");

    @Resource
    private UserService userService;

    @Resource
    private ChatSessionMapper chatSessionMapper;

    @Resource
    private ChatHistoryMapper chatHistoryMapper;

    @Resource
    private StreamHandlerExecutor streamHandlerExecutor;

    @Resource
    private VueProjectBuildService vueProjectBuildService;

    @Resource
    private ScreenshotService screenshotService;

    @Resource
    private ActiveGenerationManager activeGenerationManager;

    @Resource
    private CodeGenerationRuntimeRouter codeGenerationRuntimeRouter;

    @Resource
    private AgentRunService agentRunService;

    @Resource
    private WorkspaceProperties workspaceProperties;

    @Resource
    private ArtifactManifestReader artifactManifestReader;

    @Resource
    private AppCategoryMapper appCategoryMapper;

    @Resource
    private AgentRunMapper agentRunMapper;

    @Value("${server.port:8700}")
    private String serverPort;

    @Value("${server.servlet.context-path:/api}")
    private String contextPath;

    @Value("${langchain4j.open-ai.chat-model.model-name:}")
    private String defaultModelName;

    @Override
    public Long createApp(AppAddRequest appAddRequest, User loginUser) {
        ThrowUtils.throwIf(appAddRequest == null, ErrorCode.PARAMS_ERROR, "请求参数不能为空");
        ThrowUtils.throwIf(loginUser == null || loginUser.getId() == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        String initPrompt = StrUtil.trim(appAddRequest.getInitPrompt());
        ThrowUtils.throwIf(StrUtil.isBlank(initPrompt), ErrorCode.PARAMS_ERROR, "初始化 prompt 不能为空");
        CodeGenTypeEnum codeGenTypeEnum = resolveCodeGenType(appAddRequest.getCodeGenType(), initPrompt);
        App app = new App();
        app.setAppName(initPrompt.substring(0, Math.min(initPrompt.length(), 12)));//TODO 后续优化成AI生成应用名称
        app.setInitPrompt(initPrompt);
        app.setCodeGenType(codeGenTypeEnum.getValue());
        app.setGenerationMode(StrUtil.blankToDefault(appAddRequest.getGenerationMode(), "application"));
        app.setStyleTemplate(appAddRequest.getStyleTemplate());
        app.setUserId(loginUser.getId());
        app.setPriority(AppConstant.DEFAULT_APP_PRIORITY);
        // 设置测试应用标记
        app.setIsTestApp(Boolean.TRUE.equals(appAddRequest.getIsTestApp()) ? 1 : 0);
        boolean saveResult = this.save(app);
        ThrowUtils.throwIf(!saveResult, ErrorCode.OPERATION_ERROR, "创建应用失败");
        return app.getId();
    }

    @Override
    public void validApp(App app, boolean add) {
        if (app == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        String appName = app.getAppName();
        String initPrompt = app.getInitPrompt();

        // 创建时，参数不能为空
        if (add) {
            ThrowUtils.throwIf(StrUtil.isBlank(appName), ErrorCode.PARAMS_ERROR, "应用名称不能为空");
            ThrowUtils.throwIf(StrUtil.isBlank(initPrompt), ErrorCode.PARAMS_ERROR, "初始化提示词不能为空");
        }
        // 有参数则校验
        if (StrUtil.isNotBlank(appName) && appName.length() > 80) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "应用名称过长");
        }
        if (StrUtil.isNotBlank(initPrompt) && initPrompt.length() > 8192) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "初始化提示词过长");
        }
    }

    @Override
    public QueryWrapper getQueryWrapper(AppQueryRequest appQueryRequest) {
        if (appQueryRequest == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "请求参数为空");
        }
        Long id = appQueryRequest.getId();
        String appName = appQueryRequest.getAppName();
        String initPrompt = appQueryRequest.getInitPrompt();
        String codeGenType = appQueryRequest.getCodeGenType();
        String deployKey = appQueryRequest.getDeployKey();
        Integer priority = appQueryRequest.getPriority();
        Long userId = appQueryRequest.getUserId();
        String userName = appQueryRequest.getUserName();
        Boolean onlyFeatured = appQueryRequest.getOnlyFeatured();
        Boolean isTestApp = appQueryRequest.getIsTestApp();
        String sortField = appQueryRequest.getSortField();
        String sortOrder = appQueryRequest.getSortOrder();

        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("id", id)
                .eq("userId", userId)
                .eq("codeGenType", codeGenType)
                .eq("deployKey", deployKey)
                .eq("priority", priority)
                .like("appName", appName)
                .like("initPrompt", initPrompt);

        // 按用户名模糊搜索
        if (StrUtil.isNotBlank(userName)) {
            List<Long> userIds = userService.list(QueryWrapper.create().like("userName", userName))
                    .stream().map(User::getId).collect(Collectors.toList());
            if (CollUtil.isNotEmpty(userIds)) {
                queryWrapper.in("userId", userIds);
            } else {
                // 未匹配到用户，强行使结果为空
                queryWrapper.eq("id", -1L);
            }
        }

        // 测试应用过滤
        if (isTestApp != null) {
            queryWrapper.eq("isTestApp", isTestApp ? 1 : 0);
        }

        // 精选应用查询（优先级大于0）
        if (onlyFeatured != null && onlyFeatured) {
            queryWrapper.gt("priority", 0);
            // 精选应用按优先级降序排列
            queryWrapper.orderBy("priority", false);
        } else {
            // 普通排序
            queryWrapper.orderBy(sortField, "ascend".equals(sortOrder));
        }

        return queryWrapper;
    }

    @Override
    public AppVO getAppVO(App app) {
        if (app == null) {
            return null;
        }
        AppVO appVO = new AppVO();
        BeanUtil.copyProperties(app, appVO);
        Long userId = app.getUserId();
        if(userId != null){
            User user = userService.getById(userId);
            UserVO userVO = userService.getUserVO(user);
            appVO.setUser(userVO);
        }
        Map<String, Object> coverState = screenshotService.getCoverTaskState(app.getId());
        if (coverState != null && !coverState.isEmpty()) {
            appVO.setCoverTaskStatus((String) coverState.getOrDefault("status", ""));
            appVO.setCoverRetryCount((Integer) coverState.getOrDefault("retryCount", 0));
            appVO.setCoverErrorMessage((String) coverState.getOrDefault("errorMessage", ""));
        }
        enrichFromManifest(appVO, app);
        return appVO;
    }

    @Override
    public List<AppVO> getAppVOList(List<App> appList) {
        if (CollUtil.isEmpty(appList)) {
            return new ArrayList<>();
        }
        // 批量获取用户信息，避免 N+1 查询问题
        Set<Long> userIds = appList.stream()
                .map(App::getUserId)
                .collect(Collectors.toSet());
        Map<Long, UserVO> userVOMap = userService.listByIds(userIds).stream()
                .collect(Collectors.toMap(User::getId, userService::getUserVO));
        return appList.stream().map(app -> {
            AppVO appVO = getAppVO(app);
            UserVO userVO = userVOMap.get(app.getUserId());
            appVO.setUser(userVO);
            return appVO;
        }).collect(Collectors.toList());
    }

    @Override
    public Flux<String> chatToGenCode(Long appId, Long sessionId, String message, String displayMessage,
                                        List<ChatAttachmentInfo> attachments, User loginUser) {
        // 1. 参数校验
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 不能为空");
        ThrowUtils.throwIf(StrUtil.isBlank(message), ErrorCode.PARAMS_ERROR, "用户消息不能为空");
        String persistedUserMessage = StrUtil.blankToDefault(displayMessage, message);
        log.info("用户信息:{}", persistedUserMessage);
        // 2. 查询应用信息并校验权限
        App app = getAndCheckApp(appId, loginUser);
        // 3. 校验会话归属
        getAndCheckChatSession(sessionId, appId, loginUser);

        // 4. 获取应用的代码生成类型
        String codeGenTypeStr = app.getCodeGenType();
        CodeGenTypeEnum codeGenTypeEnum = CodeGenTypeEnum.getEnumByValue(codeGenTypeStr);
        if (codeGenTypeEnum == null) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "不支持的代码生成类型");
        }
        // 5. 通过 Runtime Router 选择运行时，并优先认领已有的暂停运行
        CodeGenerationRuntime runtime = codeGenerationRuntimeRouter.select();
        AgentRun resumedRun = agentRunService.claimLatestPausedRun(
                appId, sessionId, loginUser.getId());

        Long agentRunId;
        String loopStateJson;
        String workspacePath;

        if (resumedRun != null) {
            agentRunId = resumedRun.getId();
            loopStateJson = resumedRun.getLoopStateJson();
            workspacePath = StrUtil.blankToDefault(
                    resumedRun.getWorkspacePath(),
                    workspaceProperties.getAgentWorkspaceDir() + "/" +
                            getCodeGenOutputPrefix(codeGenTypeEnum) + "/" + appId
            );
            log.info("resuming paused agent_run, sessionId={}, agentRunId={}", sessionId, agentRunId);
        } else {
            if (agentRunService.hasRunningRun(appId, sessionId, loginUser.getId())) {
                log.warn("发现上一个 agent_run 未正常结束，自动标记为失败，sessionId={}", sessionId);
                agentRunService.failRunningRun(appId, sessionId, loginUser.getId(), "连接中断，用户重新提交");
                // 旧运行中断后，尝试为已有产物截图
                try {
                    screenshotService.triggerCoverGenerationIfNeeded(appId, null);
                } catch (Exception ex) {
                    log.warn("触发封面截图失败（不影响主流程）, appId={}", appId, ex);
                }
            }
            agentRunId = agentRunService.createAgentRun(
                    appId, sessionId, loginUser.getId(), runtime.getName()
            );
            loopStateJson = "";
            workspacePath = workspaceProperties.getAgentWorkspaceDir() + "/" +
                    getCodeGenOutputPrefix(codeGenTypeEnum) + "/" + appId;
            agentRunService.updateAgentRunWorkspacePath(agentRunId, workspacePath);
        }

        // 6. 运行准备完成后再保存用户消息；同步失败时事务会回滚 AgentRun 认领/创建
        String userMessageExtra = null;
        if (attachments != null && !attachments.isEmpty()) {
            userMessageExtra = JSONUtil.toJsonStr(Map.of("attachments", attachments));
        }
        saveHistoryMessage(sessionId, appId, loginUser.getId(), persistedUserMessage, "user", "success",
                app.getCodeGenType(), 0, userMessageExtra);
        updateSessionSummary(sessionId);

        CodeGenerationRequest runtimeRequest = CodeGenerationRequest.builder()
                .agentRunId(agentRunId)
                .appId(appId)
                .sessionId(sessionId)
                .message(message)
                .app(app)
                .loginUser(loginUser)
                .codeGenTypeEnum(codeGenTypeEnum)
                .generationMode(app.getGenerationMode())
                .workspacePath(workspacePath)
                .loopStateJson(loopStateJson)
                .isTest(UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole()))
                .attachments(attachments)
                .build();
        // 7. 获取源流并根据运行时类型决定是否需要流处理器
        StringBuilder readableAssistantMessageBuilder = new StringBuilder();
        AtomicReference<String> workflowCodeGenTypeRef = new AtomicReference<>();
        AtomicReference<String> workflowGeneratedDirRef = new AtomicReference<>();
        AtomicBoolean historySaved = new AtomicBoolean(false);
        long startTime = System.currentTimeMillis();

        // 7a. 注册活跃生成状态 + 完成回调
        // 内部订阅者（GrpcPythonAgentRuntime 中的 sink.asFlux().subscribe()）
        // 会在 gRPC onComplete/onError → sink.tryEmitComplete() 后触发此回调，
        // 确保 SSE 断开后 AI 回复仍能入库。
        ActiveGeneration activeGen = activeGenerationManager.register(sessionId, agentRunId);
        activeGen.setOnGenerationCompleted(finalText -> {
            log.info("[Handler] onGenerationCompleted fired, sessionId={}, agentRunId={}, historySaved={}, textLen={}",
                    sessionId, agentRunId, historySaved.get(), finalText != null ? finalText.length() : 0);
            if (historySaved.compareAndSet(false, true)) {
                int latencyMs = (int) (System.currentTimeMillis() - startTime);
                String msg = StrUtil.blankToDefault(finalText, "");
                saveHistoryMessage(sessionId, appId, loginUser.getId(), msg, "ai", "success", codeGenTypeStr, latencyMs, buildExtraJsonWithToolCalls(sessionId, "{\"completed_by\": \"handler\"}"));
                updateSessionSummary(sessionId);
                log.info("[Handler] Saved to DB, sessionId={}, length={}", sessionId, msg.length());
            } else {
                log.info("[Handler] CAS skipped (doOnComplete already saved), sessionId={}", sessionId);
            }
            activeGenerationManager.remove(sessionId);
            log.info("[Handler] Removed ActiveGeneration, sessionId={}", sessionId);
        });

        Flux<String> sourceStream = runtime.stream(runtimeRequest);
        Flux<String> handledStream = streamHandlerExecutor.handle(codeGenTypeEnum, sourceStream, readableAssistantMessageBuilder);
        return handledStream
                .doOnNext(chunk -> captureWorkflowCompletedEvent(chunk, workflowCodeGenTypeRef, workflowGeneratedDirRef))
                .doOnComplete(() -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    String aiMessage = readableAssistantMessageBuilder.toString();
                    String status = "success";
                    String extra = null;
                    String actualCodeGenTypeStr = StrUtil.blankToDefault(workflowCodeGenTypeRef.get(), codeGenTypeStr);
                    CodeGenTypeEnum actualCodeGenTypeEnum = CodeGenTypeEnum.getEnumByValue(actualCodeGenTypeStr);
                    if (actualCodeGenTypeEnum != null && !actualCodeGenTypeStr.equals(codeGenTypeStr)) {
                        App updateApp = new App();
                        updateApp.setId(appId);
                        updateApp.setCodeGenType(actualCodeGenTypeStr);
                        boolean updated = updateById(updateApp);
                        if (updated) {
                            app.setCodeGenType(actualCodeGenTypeStr);
                            log.info("Java-agent 工作流生成类型已同步, appId={}, from={}, to={}", appId, codeGenTypeStr, actualCodeGenTypeStr);
                        }
                    }
                    if (StrUtil.isBlank(aiMessage) && StrUtil.isNotBlank(workflowGeneratedDirRef.get())) {
                        aiMessage = "代码生成完成：已生成 " + actualCodeGenTypeStr + " 产物\n生成目录：" + workflowGeneratedDirRef.get();
                    }
                    if (actualCodeGenTypeEnum == CodeGenTypeEnum.VUE_PROJECT) {
                        try {
                            log.info("Vue 项目构建开始, appId={}, sessionId={}, workspacePath={}", appId, sessionId, workspacePath);
                            vueProjectBuildService.buildVueProject(appId, workspacePath);
                            aiMessage = aiMessage + "\n构建完成：已生成 dist 产物";
                            log.info("Vue 项目构建完成, appId={}, sessionId={}, latencyMs={}", appId, sessionId, latencyMs);
                        } catch (Exception e) {
                            status = "failed";
                            aiMessage = aiMessage + "\n构建失败：" + e.getMessage();
                            extra = JSONUtil.toJsonStr(Map.of(
                                    "buildError", e.getMessage(),
                                    "buildErrorType", e.getClass().getSimpleName()
                            ));
                            log.error("Vue 项目构建失败, appId={}, sessionId={}, codeGenType={}, userId={}, message={}",
                                    appId, sessionId, codeGenTypeStr, loginUser.getId(), message, e);
                        }
                    } else if (actualCodeGenTypeEnum == CodeGenTypeEnum.MULTI_FILE) {
                        Path multiFileProjectDir = AppConstant.getMultiFileOutputDir(appId);
                        if (workspacePath != null && !workspacePath.isBlank()) {
                            Path wsDir = Path.of(workspacePath).toAbsolutePath().normalize();
                            if (Files.exists(wsDir) && Files.exists(wsDir.resolve("package.json"))) {
                                multiFileProjectDir = wsDir;
                            }
                        }
                        if (Files.exists(multiFileProjectDir.resolve("package.json"))) {
                            try {
                                log.info("多文件模式检测到 package.json，触发构建, appId={}, sessionId={}, projectDir={}", appId, sessionId, multiFileProjectDir);
                                vueProjectBuildService.buildProject(multiFileProjectDir);
                                aiMessage = aiMessage + "\n构建完成：已生成 dist 产物";
                                log.info("多文件模式构建完成, appId={}, sessionId={}, latencyMs={}", appId, sessionId, latencyMs);
                            } catch (Exception e) {
                                status = "failed";
                                aiMessage = aiMessage + "\n构建失败：" + e.getMessage();
                                extra = JSONUtil.toJsonStr(Map.of(
                                        "buildError", e.getMessage(),
                                        "buildErrorType", e.getClass().getSimpleName()
                                ));
                                log.error("多文件模式构建失败, appId={}, sessionId={}, userId={}, message={}",
                                        appId, sessionId, loginUser.getId(), message, e);
                            }
                        }
                    }
                    // doOnComplete 正常保存（SSE 连接状态下）。
                    // 若 handler 已通过内部订阅者保存（SSE 断开后 gRPC 完成），CAS 跳过。
                    if (historySaved.compareAndSet(false, true)) {
                        log.info("[doOnComplete] Saving to DB, sessionId={}, status={}, textLen={}",
                                sessionId, status, aiMessage != null ? aiMessage.length() : 0);
                        saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", status, actualCodeGenTypeStr, latencyMs, buildExtraJsonWithToolCalls(sessionId, extra));
                        updateSessionSummary(sessionId);
                    } else {
                        log.info("[doOnComplete] CAS skipped (handler already saved), sessionId={}", sessionId);
                    }
                    // Agent 运行结束后触发封面截图（无论谁保存、何种方式完成）
                    try {
                        screenshotService.triggerCoverGenerationIfNeeded(appId, agentRunId);
                    } catch (Exception e) {
                        log.warn("触发封面截图失败（不影响主流程）, appId={}", appId, e);
                    }
                })
                .doOnError(error -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    Map<String, String> extraInfo = new HashMap<>();
                    extraInfo.put("error", error.getMessage());
                    extraInfo.put("errorType", error.getClass().getSimpleName());
                    String aiMessage = StrUtil.isBlank(readableAssistantMessageBuilder.toString())
                            ? "生成失败：" + error.getMessage()
                            : readableAssistantMessageBuilder.toString();
                    saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", "failed", codeGenTypeStr, latencyMs, buildExtraJsonWithToolCalls(sessionId, JSONUtil.toJsonStr(extraInfo)));
                    historySaved.set(true);
                    updateSessionSummary(sessionId);
                    // Agent 运行异常结束后也触发封面截图
                    try {
                        screenshotService.triggerCoverGenerationIfNeeded(appId, agentRunId);
                    } catch (Exception e) {
                        log.warn("触发封面截图失败（不影响主流程）, appId={}", appId, e);
                    }
                })
                .doFinally(signalType -> {
                    log.info("[doFinally] signalType={}, historySaved={}, sessionId={}",
                            signalType, historySaved.get(), sessionId);
                    if (historySaved.get()) {
                        activeGenerationManager.remove(sessionId);
                        log.info("[doFinally] Removed ActiveGeneration, sessionId={}", sessionId);
                    }
                });
    }

    @Override
    public Long createChatSession(Long appId, User loginUser) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        App app = getAndCheckApp(appId, loginUser);
        long sessionCount = chatSessionMapper.selectCountByQuery(QueryWrapper.create()
                .eq("appId", appId)
                .eq("userId", loginUser.getId()));
        String sessionTitle = "新会话 " + (sessionCount + 1);
        String resolvedModelName = resolveModelName();
        ChatSession chatSession = ChatSession.builder()
                .appId(appId)
                .userId(loginUser.getId())
                .title(sessionTitle)
                .messageCount(0)
                .modelName(resolvedModelName)
                .lastMessageTime(LocalDateTime.now())
                .build();
        int insertResult = chatSessionMapper.insert(chatSession);
        ThrowUtils.throwIf(insertResult <= 0 || chatSession.getId() == null, ErrorCode.OPERATION_ERROR, "创建会话失败");
        return chatSession.getId();
    }

    private void captureWorkflowCompletedEvent(String chunk,
                                               AtomicReference<String> codeGenTypeRef,
                                               AtomicReference<String> generatedDirRef) {
        if (StrUtil.isBlank(chunk)) {
            return;
        }
        try {
            JSONObject jsonObject = JSONUtil.parseObj(chunk);
            if (!"workflow_event".equals(jsonObject.getStr("type"))
                    || !"workflow_completed".equals(jsonObject.getStr("event"))) {
                return;
            }
            JSONObject data = jsonObject.getJSONObject("data");
            if (data == null) {
                return;
            }
            String codeGenType = data.getStr("codeGenType", "");
            String generatedCodeDir = data.getStr("generatedCodeDir", "");
            if (StrUtil.isNotBlank(codeGenType)) {
                codeGenTypeRef.set(codeGenType);
            }
            if (StrUtil.isNotBlank(generatedCodeDir)) {
                generatedDirRef.set(generatedCodeDir);
            }
        } catch (Exception ignored) {
            // 非工作流事件无需影响主生成流程。
        }
    }

    @Override
    public List<ChatSessionVO> listChatSession(Long appId, User loginUser) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        getAndCheckApp(appId, loginUser);
        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("appId", appId)
                .eq("userId", loginUser.getId())
                .orderBy("updateTime", false);
        return chatSessionMapper.selectListByQuery(queryWrapper).stream()
                .map(session -> {
                    ChatSessionVO chatSessionVO = new ChatSessionVO();
                    BeanUtil.copyProperties(session, chatSessionVO);
                    return chatSessionVO;
                })
                .collect(Collectors.toList());
    }

    @Override
    public Page<ChatHistoryVO> listChatHistoryByPage(ChatHistoryQueryRequest chatHistoryQueryRequest, User loginUser) {
        ThrowUtils.throwIf(chatHistoryQueryRequest == null, ErrorCode.PARAMS_ERROR);
        Long appId = chatHistoryQueryRequest.getAppId();
        Long sessionId = chatHistoryQueryRequest.getSessionId();
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 不能为空");
        int pageNum = Math.max(chatHistoryQueryRequest.getPageNum(), 1);
        int pageSize = Math.min(Math.max(chatHistoryQueryRequest.getPageSize(), 1), 50);
        getAndCheckApp(appId, loginUser);
        getAndCheckChatSession(sessionId, appId, loginUser);
        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("sessionId", sessionId)
                .eq("appId", appId)
                .eq("userId", loginUser.getId())
                .orderBy("seqNo", true);
        Page<ChatHistory> chatHistoryPage = chatHistoryMapper.paginate(
                Page.of(pageNum, pageSize), queryWrapper);
        List<ChatHistoryVO> records = chatHistoryPage.getRecords().stream().map(history -> {
            ChatHistoryVO chatHistoryVO = new ChatHistoryVO();
            BeanUtil.copyProperties(history, chatHistoryVO);
            chatHistoryVO.setToolEvents(extractToolEvents(history));
            chatHistoryVO.setAttachments(extractAttachments(history));
            return chatHistoryVO;
        }).collect(Collectors.toList());
        Page<ChatHistoryVO> resultPage = new Page<>(pageNum, pageSize, chatHistoryPage.getTotalRow());
        resultPage.setRecords(records);
        return resultPage;
    }

    @Override
    public void renameChatSession(Long sessionId, String title, User loginUser) {
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        ThrowUtils.throwIf(StrUtil.isBlank(title), ErrorCode.PARAMS_ERROR, "会话标题不能为空");
        ThrowUtils.throwIf(title.length() > 200, ErrorCode.PARAMS_ERROR, "会话标题过长");
        ChatSession chatSession = chatSessionMapper.selectOneById(sessionId);
        ThrowUtils.throwIf(chatSession == null, ErrorCode.NOT_FOUND_ERROR, "会话不存在");
        if (!chatSession.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限操作该会话");
        }
        chatSession.setTitle(title);
        int updateResult = chatSessionMapper.update(chatSession);
        ThrowUtils.throwIf(updateResult <= 0, ErrorCode.OPERATION_ERROR, "重命名会话失败");
    }

    @Override
    public void deleteChatSession(Long sessionId, User loginUser) {
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        ChatSession chatSession = chatSessionMapper.selectOneById(sessionId);
        ThrowUtils.throwIf(chatSession == null, ErrorCode.NOT_FOUND_ERROR, "会话不存在");
        if (!chatSession.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限操作该会话");
        }
        int deleteResult = chatSessionMapper.deleteById(sessionId);
        ThrowUtils.throwIf(deleteResult <= 0, ErrorCode.OPERATION_ERROR, "删除会话失败");
    }

    @Override
    public String deployApp(Long appId, User loginUser) {
        // 1. 参数校验
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(loginUser == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        // 2. 查询应用信息
        App app = this.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        // 3. 验证用户是否有权限部署该应用，仅本人可以部署
        if (!app.getUserId().equals(loginUser.getId())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限部署该应用");
        }
        // 4. 检查是否已有 deployKey
        String deployKey = app.getDeployKey();
        if (StrUtil.isBlank(deployKey)) {
            deployKey = generateUniqueDeployKey();
        }
        // 5. 获取代码生成类型，构建源目录路径
        String codeGenType = app.getCodeGenType();
        File sourceDir;
        if (CodeGenTypeEnum.VUE_PROJECT.getValue().equals(codeGenType)) {
            Path workspaceDir = Path.of(workspaceProperties.getAgentWorkspaceDir()).toAbsolutePath().normalize();
            Path vueProjectPath = workspaceDir.resolve(AppConstant.VUE_PROJECT_OUTPUT_PREFIX).resolve(String.valueOf(appId));
            Path distPath = vueProjectPath.resolve(AppConstant.DIST_DIR_NAME);
            if (!Files.exists(distPath) || !Files.isDirectory(distPath)) {
                distPath = AppConstant.getVueProjectOutputDir(appId).resolve(AppConstant.DIST_DIR_NAME);
            }
            if (!Files.exists(distPath) || !Files.isDirectory(distPath)) {
                BuildResult buildResult = vueProjectBuildService.buildVueProject(appId, null);
                distPath = buildResult.distPath();
            }
            sourceDir = distPath.toFile();
        } else {
            Path workspaceDir = Path.of(workspaceProperties.getAgentWorkspaceDir()).toAbsolutePath().normalize();
            Path sourcePath = workspaceDir.resolve(getCodeGenOutputPrefix(CodeGenTypeEnum.getEnumByValue(codeGenType))).resolve(String.valueOf(appId));
            if (!Files.exists(sourcePath)) {
                String sourceDirName = codeGenType + "_" + appId;
                sourcePath = Path.of(AppConstant.CODE_OUTPUT_ROOT_DIR).resolve(sourceDirName);
            }
            sourceDir = sourcePath.toFile();
        }
        // 6. 检查源目录是否存在
        if (!sourceDir.exists() || !sourceDir.isDirectory()) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "应用代码不存在，请先生成代码");
        }
        // 7. 复制文件到部署目录
        String deployDirPath = AppConstant.CODE_DEPLOY_ROOT_DIR + File.separator + deployKey;
        try {
            FileUtil.copyContent(sourceDir, new File(deployDirPath), true);
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "部署失败：" + e.getMessage());
        }
        // 8. 更新应用的 deployKey 和部署时间
        App updateApp = new App();
        updateApp.setId(appId);
        updateApp.setDeployKey(deployKey);
        updateApp.setDeployedTime(LocalDateTime.now());
        boolean updateResult = this.updateById(updateApp);
        ThrowUtils.throwIf(!updateResult, ErrorCode.OPERATION_ERROR, "更新应用部署信息失败");
        screenshotService.triggerCoverGenerationIfNeeded(appId, null);
        // 9. 返回可访问的 URL
        return buildDeployUrl(deployKey);
    }

    @Override
    @Cacheable(cacheNames = "good_app_page", key = "T(com.adcage.acaicodefree.utils.CacheKeyUtils).generateKey('good_app_page', #pageNum, #pageSize, #appQueryRequest.priority)")
    public Page<App> listGoodAppPage(long pageNum, long pageSize, AppQueryRequest appQueryRequest) {
        QueryWrapper queryWrapper = getQueryWrapper(appQueryRequest);
        return page(Page.of(pageNum, pageSize), queryWrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean publishApp(Long appId, List<String> categories, User loginUser) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(loginUser == null || loginUser.getId() == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        App app = this.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        ThrowUtils.throwIf(!app.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR, "无权限操作该应用");
        // 校验分类
        if (CollUtil.isNotEmpty(categories)) {
            for (String category : categories) {
                ThrowUtils.throwIf(!ALLOWED_CATEGORIES.contains(category), ErrorCode.PARAMS_ERROR,
                        "不支持的分类：" + category);
            }
        }
        // 更新为公开
        App updateApp = new App();
        updateApp.setId(appId);
        updateApp.setIsPublic(1);
        boolean updated = this.updateById(updateApp);
        ThrowUtils.throwIf(!updated, ErrorCode.OPERATION_ERROR, "发布应用失败");
        // 处理分类：先删除旧分类，再批量插入新分类
        appCategoryMapper.deleteByQuery(QueryWrapper.create().eq("appId", appId));
        if (CollUtil.isNotEmpty(categories)) {
            for (String category : categories) {
                AppCategory appCategory = AppCategory.builder()
                        .appId(appId)
                        .category(category)
                        .build();
                appCategoryMapper.insert(appCategory);
            }
        }
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean unpublishApp(Long appId, User loginUser) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(loginUser == null || loginUser.getId() == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        App app = this.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        ThrowUtils.throwIf(!app.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR, "无权限操作该应用");
        // 更新为不公开
        App updateApp = new App();
        updateApp.setId(appId);
        updateApp.setIsPublic(0);
        boolean updated = this.updateById(updateApp);
        ThrowUtils.throwIf(!updated, ErrorCode.OPERATION_ERROR, "取消发布应用失败");
        // 清理分类
        appCategoryMapper.deleteByQuery(QueryWrapper.create().eq("appId", appId));
        return true;
    }

    @Override
    public List<String> listCategories() {
        return ALLOWED_CATEGORIES;
    }

    @Override
    public Page<MarketplaceAppVO> listMarketplaceAppVOByPage(MarketplaceQueryRequest request) {
        ThrowUtils.throwIf(request == null, ErrorCode.PARAMS_ERROR, "请求参数不能为空");
        int pageNum = Math.max(request.getPageNum(), 1);
        int pageSize = Math.min(Math.max(request.getPageSize(), 1), 50);
        String category = request.getCategory();
        String sortField = request.getSortField();

        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("isPublic", 1);

        // 分类筛选
        if (StrUtil.isNotBlank(category)) {
            List<AppCategory> appCategories = appCategoryMapper.selectListByQuery(
                    QueryWrapper.create().eq("category", category));
            if (CollUtil.isEmpty(appCategories)) {
                // 无匹配分类，返回空页
                return new Page<>(pageNum, pageSize, 0);
            }
            List<Long> appIds = appCategories.stream()
                    .map(AppCategory::getAppId)
                    .distinct()
                    .collect(Collectors.toList());
            queryWrapper.in("id", appIds);
        }

        // 排序
        if ("popular".equals(sortField)) {
            queryWrapper.orderBy("forkCount", false);
            queryWrapper.orderBy("createTime", false);
        } else {
            queryWrapper.orderBy("createTime", false);
        }

        Page<App> appPage = page(Page.of(pageNum, pageSize), queryWrapper);
        List<MarketplaceAppVO> records = appPage.getRecords().stream().map(app -> {
            MarketplaceAppVO vo = new MarketplaceAppVO();
            vo.setId(app.getId());
            vo.setAppName(app.getAppName());
            vo.setCover(app.getCover());
            vo.setInitPrompt(app.getInitPrompt());
            vo.setCodeGenType(app.getCodeGenType());
            vo.setForkCount(app.getForkCount());
            vo.setCreateTime(app.getCreateTime());
            // 查询分类
            List<AppCategory> appCategories = appCategoryMapper.selectListByQuery(
                    QueryWrapper.create().eq("appId", app.getId()));
            vo.setCategories(appCategories.stream()
                    .map(AppCategory::getCategory)
                    .collect(Collectors.toList()));
            // 查询用户
            if (app.getUserId() != null) {
                User user = userService.getById(app.getUserId());
                vo.setUser(userService.getUserVO(user));
            }
            return vo;
        }).collect(Collectors.toList());

        Page<MarketplaceAppVO> resultPage = new Page<>(pageNum, pageSize, appPage.getTotalRow());
        resultPage.setRecords(records);
        return resultPage;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long forkApp(Long appId, User loginUser) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(loginUser == null || loginUser.getId() == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        // 1. 查源 App
        App sourceApp = this.getById(appId);
        ThrowUtils.throwIf(sourceApp == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        ThrowUtils.throwIf(sourceApp.getIsPublic() == null || sourceApp.getIsPublic() != 1,
                ErrorCode.NO_AUTH_ERROR, "该应用未公开，无法 Fork");
        // 2. 查源 App 最近 completed 的 AgentRun
        AgentRun latestRun = agentRunMapper.selectOneByQuery(
                QueryWrapper.create()
                        .eq("appId", appId)
                        .eq("status", "completed")
                        .orderBy("createTime", false)
                        .limit(1));
        // 3. 检查工作区目录是否存在
        CodeGenTypeEnum codeGenTypeEnum = CodeGenTypeEnum.getEnumByValue(sourceApp.getCodeGenType());
        String workspacePath = workspaceProperties.getAgentWorkspaceDir() + "/" +
                getCodeGenOutputPrefix(codeGenTypeEnum != null ? codeGenTypeEnum : CodeGenTypeEnum.SINGLE_FILE) + "/" + appId;
        Path sourceWorkspacePath = Path.of(workspacePath).toAbsolutePath().normalize();
        ThrowUtils.throwIf(!Files.exists(sourceWorkspacePath), ErrorCode.NOT_FOUND_ERROR, "源应用工作区不存在，资源丢失");
        // 4. 创建新 App 记录
        App newApp = new App();
        newApp.setAppName(sourceApp.getAppName() + " [副本]");
        newApp.setInitPrompt(sourceApp.getInitPrompt());
        newApp.setCodeGenType(sourceApp.getCodeGenType());
        newApp.setGenerationMode(sourceApp.getGenerationMode());
        newApp.setStyleTemplate(sourceApp.getStyleTemplate());
        newApp.setUserId(loginUser.getId());
        newApp.setIsPublic(0);
        newApp.setForkCount(0);
        newApp.setSourceAppId(appId);
        newApp.setPriority(AppConstant.DEFAULT_APP_PRIORITY);
        boolean saveResult = this.save(newApp);
        ThrowUtils.throwIf(!saveResult, ErrorCode.OPERATION_ERROR, "Fork 应用失败");
        // 5. 复制工作区文件到新目录
        String newWorkspacePath = workspaceProperties.getAgentWorkspaceDir() + "/" +
                getCodeGenOutputPrefix(codeGenTypeEnum != null ? codeGenTypeEnum : CodeGenTypeEnum.SINGLE_FILE) + "/" + newApp.getId();
        Path targetPath = Path.of(newWorkspacePath).toAbsolutePath().normalize();
        try {
            copyWorkspaceDir(sourceWorkspacePath, targetPath);
        } catch (IOException e) {
            log.error("Fork 工作区复制失败, sourceAppId={}, newAppId={}", appId, newApp.getId(), e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "Fork 工作区复制失败：" + e.getMessage());
        }
        // 6. 更新源 App forkCount
        App updateSourceApp = new App();
        updateSourceApp.setId(appId);
        updateSourceApp.setForkCount((sourceApp.getForkCount() != null ? sourceApp.getForkCount() : 0) + 1);
        this.updateById(updateSourceApp);
        // 7. 返回新应用 ID
        return newApp.getId();
    }

    private void enrichFromManifest(AppVO appVO, App app) {
        if (app.getId() == null || app.getCodeGenType() == null) {
            return;
        }
        try {
            Path workspaceRoot = resolveAppWorkspaceRoot(app);
            if (workspaceRoot != null) {
                ArtifactManifestVO manifest = artifactManifestReader.readManifest(workspaceRoot);
                if (manifest != null) {
                    appVO.setArtifactFormat(manifest.getArtifactFormat());
                } else {
                    appVO.setArtifactFormat(mapCodeGenTypeToArtifactFormat(app.getCodeGenType()));
                }
            }
        } catch (Exception e) {
            log.debug("Manifest读取失败，跳过, appId={}", app.getId(), e);
        }
        appVO.setPreviewUrl(screenshotService.computePreviewUrl(app));
    }

    private Path resolveAppWorkspaceRoot(App app) {
        String codeGenType = app.getCodeGenType();
        CodeGenTypeEnum codeGenTypeEnum = CodeGenTypeEnum.getEnumByValue(codeGenType);
        if (codeGenTypeEnum == null) {
            return null;
        }
        Path workspaceDir = Path.of(workspaceProperties.getAgentWorkspaceDir()).toAbsolutePath().normalize();
        Path appDir = workspaceDir.resolve(getCodeGenOutputPrefix(codeGenTypeEnum)).resolve(String.valueOf(app.getId()));
        if (!Files.exists(appDir)) {
            return null;
        }
        return appDir;
    }

    private CodeGenTypeEnum resolveCodeGenType(String requestCodeGenType, String initPrompt) {
        if (StrUtil.isNotBlank(requestCodeGenType)) {
            CodeGenTypeEnum codeGenTypeEnum = parseCodeGenType(requestCodeGenType);
            ThrowUtils.throwIf(codeGenTypeEnum == null, ErrorCode.PARAMS_ERROR, "代码生成类型错误");
            return codeGenTypeEnum;
        }
        return CodeGenTypeEnum.SINGLE_FILE;
    }

    private CodeGenTypeEnum parseCodeGenType(String valueOrName) {
        CodeGenTypeEnum byValue = CodeGenTypeEnum.getEnumByValue(valueOrName);
        if (byValue != null) {
            return byValue;
        }
        if (ObjUtil.isEmpty(valueOrName)) {
            return null;
        }
        try {
            return CodeGenTypeEnum.valueOf(valueOrName.trim().toUpperCase());
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private void copyWorkspaceDir(Path source, Path target) throws IOException {
        Files.walkFileTree(source, new SimpleFileVisitor<Path>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                String dirName = dir.getFileName().toString().toLowerCase();
                if (FORK_EXCLUDED_DIRS.contains(dirName)) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                Path targetDir = target.resolve(source.relativize(dir));
                try {
                    Files.createDirectories(targetDir);
                } catch (IOException e) {
                    throw new RuntimeException("创建目录失败：" + targetDir, e);
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                String fileName = file.getFileName().toString().toLowerCase();
                if (FORK_EXCLUDED_FILE_NAMES.contains(fileName)) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                for (String ext : FORK_EXCLUDED_FILE_EXTENSIONS) {
                    if (fileName.endsWith(ext)) {
                        return FileVisitResult.SKIP_SUBTREE;
                    }
                }
                Path targetFile = target.resolve(source.relativize(file));
                Files.copy(file, targetFile, StandardCopyOption.REPLACE_EXISTING);
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private String buildDeployUrl(String deployKey) {
        String baseHost = AppConstant.CODE_DEPLOY_HOST;
        if (!baseHost.matches("^https?://[^/:]+(:\\d+)?$")) {
            return String.format("%s/%s/index.html", baseHost, deployKey);
        }
        String normalizedContextPath = contextPath == null || contextPath.isBlank() ? "" : contextPath;
        if (!normalizedContextPath.startsWith("/")) {
            normalizedContextPath = "/" + normalizedContextPath;
        }
        if (normalizedContextPath.endsWith("/")) {
            normalizedContextPath = normalizedContextPath.substring(0, normalizedContextPath.length() - 1);
        }
        String hostWithPort = baseHost.contains("://") && baseHost.matches("^https?://[^/:]+:\\d+$")
                ? baseHost
                : baseHost + ":" + serverPort;
        return String.format("%s%s/static/%s/index.html", hostWithPort, normalizedContextPath, deployKey);
    }

    private String mapCodeGenTypeToArtifactFormat(String codeGenType) {
        return switch (codeGenType) {
            case "multi-file" -> "web_multi_file";
            case "single_file" -> "web_single_file";
            case "vue_project" -> "vue_project";
            default -> null;
        };
    }

    private App getAndCheckApp(Long appId, User loginUser) {
        ThrowUtils.throwIf(loginUser == null || loginUser.getId() == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        App app = this.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        if (!app.getUserId().equals(loginUser.getId())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限访问该应用");
        }
        return app;
    }

    private ChatSession getAndCheckChatSession(Long sessionId, Long appId, User loginUser) {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("id", sessionId)
                .eq("appId", appId)
                .eq("userId", loginUser.getId());
        ChatSession chatSession = chatSessionMapper.selectOneByQuery(queryWrapper);
        ThrowUtils.throwIf(chatSession == null, ErrorCode.NOT_FOUND_ERROR, "会话不存在");
        return chatSession;
    }

    private void saveHistoryMessage(Long sessionId, Long appId, Long userId, String message,
                                    String messageType, String status, String modelName,
                                    Integer latencyMs, String extra) {
        ChatHistory chatHistory = ChatHistory.builder()
                .sessionId(sessionId)
                .seqNo(getNextSeqNo(sessionId))
                .message(StrUtil.blankToDefault(message, ""))
                .messageType(messageType)
                .status(status)
                .appId(appId)
                .userId(userId)
                .modelName(modelName)
                .latencyMs(latencyMs)
                .extra(extra)
                .build();
        int insertResult = chatHistoryMapper.insert(chatHistory);
        ThrowUtils.throwIf(insertResult <= 0, ErrorCode.OPERATION_ERROR, "保存聊天记录失败");
    }

    private Integer getNextSeqNo(Long sessionId) {
        QueryWrapper maxQuery = QueryWrapper.create()
                .eq("sessionId", sessionId)
                .select("MAX(seqNo) as seqNo");
        ChatHistory maxRecord = chatHistoryMapper.selectOneByQuery(maxQuery);
        if (maxRecord == null || maxRecord.getSeqNo() == null) {
            return 1;
        }
        return maxRecord.getSeqNo() + 1;
    }

    private void updateSessionSummary(Long sessionId) {
        ChatSession chatSession = chatSessionMapper.selectOneByQuery(QueryWrapper.create().eq("id", sessionId));
        if (chatSession == null) {
            return;
        }
        long count = chatHistoryMapper.selectCountByQuery(QueryWrapper.create().eq("sessionId", sessionId));
        chatSession.setMessageCount((int) count);
        chatSession.setLastMessageTime(LocalDateTime.now());
        chatSessionMapper.update(chatSession);
    }

    private List<ToolEventVO> extractToolEvents(ChatHistory history) {
        if (history == null) {
            return new ArrayList<>();
        }
        List<ToolEventVO> toolEvents = extractToolEventsFromExtra(history.getExtra());
        if (CollUtil.isNotEmpty(toolEvents)) {
            return toolEvents;
        }
        return extractToolEventsFromMessage(history.getMessage());
    }

    private List<ChatAttachmentInfo> extractAttachments(ChatHistory history) {
        if (history == null || StrUtil.isBlank(history.getExtra())) {
            return null;
        }
        try {
            JSONObject extraJson = JSONUtil.parseObj(history.getExtra());
            JSONArray attachmentsArray = extraJson.getJSONArray("attachments");
            if (attachmentsArray == null || attachmentsArray.isEmpty()) {
                return null;
            }
            List<ChatAttachmentInfo> attachments = new ArrayList<>();
            for (Object item : attachmentsArray) {
                if (!(item instanceof JSONObject attObj)) {
                    continue;
                }
                ChatAttachmentInfo info = new ChatAttachmentInfo();
                info.setId(attObj.getStr("id"));
                info.setFileName(attObj.getStr("fileName"));
                info.setFileSize(attObj.getLong("fileSize"));
                info.setMimeType(attObj.getStr("mimeType"));
                info.setStorageType(attObj.getStr("storageType"));
                info.setStoragePath(attObj.getStr("storagePath"));
                info.setUrl(attObj.getStr("url"));
                attachments.add(info);
            }
            return attachments;
        } catch (Exception e) {
            log.warn("解析 chat_history.extra 附件数据失败, id={}", history.getId(), e);
            return null;
        }
    }

    private List<ToolEventVO> extractToolEventsFromExtra(String extra) {
        if (StrUtil.isBlank(extra)) {
            return new ArrayList<>();
        }
        try {
            JSONObject extraJson = JSONUtil.parseObj(extra);
            // 优先新格式 toolCalls，兼容旧格式 toolEvents
            JSONArray toolEventArray = extraJson.getJSONArray("toolCalls");
            if (toolEventArray == null || toolEventArray.isEmpty()) {
                toolEventArray = extraJson.getJSONArray("toolEvents");
            }
            if (toolEventArray == null || toolEventArray.isEmpty()) {
                return new ArrayList<>();
            }
            List<ToolEventVO> toolEvents = new ArrayList<>();
            for (Object item : toolEventArray) {
                if (!(item instanceof JSONObject eventObj)) {
                    continue;
                }
                String type = normalizeToolEventType(eventObj.getStr("type"));
                // 新格式用 name 作为 text，旧格式直接用 text
                String text = eventObj.getStr("text");
                if (StrUtil.isBlank(text)) {
                    text = eventObj.getStr("name", "");
                }
                if (StrUtil.isNotBlank(type) && StrUtil.isNotBlank(text)) {
                    toolEvents.add(new ToolEventVO(type, text));
                }
            }
            return toolEvents;
        } catch (Exception ignored) {
            return new ArrayList<>();
        }
    }

    private List<ToolEventVO> extractToolEventsFromMessage(String message) {
        if (StrUtil.isBlank(message)) {
            return new ArrayList<>();
        }
        List<ToolEventVO> toolEvents = new ArrayList<>();
        String[] lines = message.split("\\n");
        for (String line : lines) {
            String trimmedLine = StrUtil.trim(line);
            if (StrUtil.isBlank(trimmedLine)) {
                continue;
            }
            if (trimmedLine.startsWith("[工具调用]")) {
                String text = StrUtil.trim(trimmedLine.substring("[工具调用]".length()));
                if (StrUtil.isNotBlank(text)) {
                    toolEvents.add(new ToolEventVO("request", text));
                }
                continue;
            }
            if (trimmedLine.startsWith("[工具完成]")) {
                String text = StrUtil.trim(trimmedLine.substring("[工具完成]".length()));
                if (StrUtil.isNotBlank(text)) {
                    toolEvents.add(new ToolEventVO("executed", text));
                }
                continue;
            }
            if (trimmedLine.startsWith("准备写入文件")) {
                toolEvents.add(new ToolEventVO("request", trimmedLine));
                continue;
            }
            if (trimmedLine.startsWith("已写入文件")) {
                toolEvents.add(new ToolEventVO("executed", trimmedLine));
            }
        }
        return toolEvents;
    }

    private String normalizeToolEventType(String type) {
        if (StrUtil.isBlank(type)) {
            return "";
        }
        if ("request".equals(type) || "executed".equals(type)) {
            return type;
        }
        return "";
    }

    private String generateUniqueDeployKey() {
        for (int attempt = 0; attempt < 10; attempt++) {
            String key = RandomUtil.randomString(12);
            long exists = count(QueryWrapper.create().eq("deployKey", key));
            if (exists == 0) {
                return key;
            }
            log.warn("deployKey 碰撞，重试, attempt={}", attempt + 1);
        }
        throw new BusinessException(ErrorCode.SYSTEM_ERROR, "生成部署标识失败，请重试");
    }

    private String resolveModelName() {
        return StrUtil.blankToDefault(defaultModelName, "");
    }

    private String getCodeGenOutputPrefix(CodeGenTypeEnum codeGenType) {
        return switch (codeGenType) {
            case SINGLE_FILE -> AppConstant.SINGLE_FILE_OUTPUT_PREFIX;
            case MULTI_FILE -> AppConstant.MULTI_FILE_OUTPUT_PREFIX;
            case VUE_PROJECT -> AppConstant.VUE_PROJECT_OUTPUT_PREFIX;
        };
    }

    /** 构造入库 extra JSON：合并已有 extra + toolCalls。 */
    private String buildExtraJsonWithToolCalls(Long sessionId, String existingExtra) {
        ActiveGeneration activeGen = activeGenerationManager.get(sessionId);
        if (activeGen == null || activeGen.getToolCalls().isEmpty()) {
            return existingExtra;
        }
        JSONObject extraJson;
        if (StrUtil.isNotBlank(existingExtra)) {
            try {
                extraJson = JSONUtil.parseObj(existingExtra);
            } catch (Exception e) {
                extraJson = new JSONObject();
            }
        } else {
            extraJson = new JSONObject();
        }
        extraJson.put("toolCalls", new JSONArray(activeGen.getToolCalls()));
        return extraJson.toString();
    }

}
