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
import com.adcage.acaicodefree.ai.AiCodeGenTypeRoutingService;
import com.adcage.acaicodefree.ai.AiCodeGenTypeRoutingServiceFactory;
import com.adcage.acaicodefree.config.properties.ScreenshotProperties;
import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.core.build.VueProjectBuildService;
import com.adcage.acaicodefree.core.handler.StreamHandlerExecutor;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.model.dto.app.AppAddRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.dto.app.AppQueryRequest;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.ChatSession;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.app.AppVO;
import com.adcage.acaicodefree.model.vo.chat.ChatHistoryVO;
import com.adcage.acaicodefree.model.vo.chat.ChatSessionVO;
import com.adcage.acaicodefree.model.vo.chat.ToolEventVO;
import com.adcage.acaicodefree.model.vo.user.UserVO;
import com.mybatisflex.core.paginate.Page;
import com.adcage.acaicodefree.service.UserService;
import com.adcage.acaicodefree.service.ScreenshotService;
import com.adcage.acaicodefree.workflow.config.WorkflowProperties;
import com.adcage.acaicodefree.workflow.service.WorkflowCodeGeneratorService;
import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.spring.service.impl.ServiceImpl;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.service.AppService;
import jakarta.annotation.Resource;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/**
 * 应用 服务层实现。
 *
 * @author adcage
 */
@Service
public class AppServiceImpl extends ServiceImpl<AppMapper, App> implements AppService {

    private static final Logger log = LoggerFactory.getLogger(AppServiceImpl.class);

    private final ExecutorService screenshotTaskExecutor = Executors.newSingleThreadExecutor(
            Thread.ofVirtual().name("screenshot-task-", 0).factory());

    private final Map<Long, Map<String, Object>> coverTaskStateMap = new ConcurrentHashMap<>();

    @Resource
    private UserService userService;

    @Resource
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    @Resource
    private ChatSessionMapper chatSessionMapper;

    @Resource
    private ChatHistoryMapper chatHistoryMapper;

    @Resource
    private StreamHandlerExecutor streamHandlerExecutor;

    @Resource
    private VueProjectBuildService vueProjectBuildService;

    @Resource
    private AiCodeGenTypeRoutingServiceFactory aiCodeGenTypeRoutingServiceFactory;

    @Resource
    private ScreenshotService screenshotService;

    @Resource
    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @Resource
    private WorkflowProperties workflowProperties;

    @Resource
    private ScreenshotProperties screenshotProperties;

    @Value("${server.port:8700}")
    private String serverPort;

    @Value("${server.servlet.context-path:/api}")
    private String contextPath;

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
        app.setUserId(loginUser.getId());
        app.setPriority(AppConstant.DEFAULT_APP_PRIORITY);
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
        appendCoverTaskState(appVO, app.getId());
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
    public Flux<String> chatToGenCode(Long appId, Long sessionId, String message, User loginUser) {
        // 1. 参数校验
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 不能为空");
        ThrowUtils.throwIf(StrUtil.isBlank(message), ErrorCode.PARAMS_ERROR, "用户消息不能为空");
        log.info("用户信息:{}",message);
        // 2. 查询应用信息并校验权限
        App app = getAndCheckApp(appId, loginUser);
        // 3. 校验会话归属
        getAndCheckChatSession(sessionId, appId, loginUser);
        // 4. 保存用户消息
        saveHistoryMessage(sessionId, appId, loginUser.getId(), message, "user", "success", app.getCodeGenType(), 0, null);
        updateSessionSummary(sessionId);
        // 5. 获取应用的代码生成类型
        String codeGenTypeStr = app.getCodeGenType();
        CodeGenTypeEnum codeGenTypeEnum = CodeGenTypeEnum.getEnumByValue(codeGenTypeStr);
        if (codeGenTypeEnum == null) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "不支持的代码生成类型");
        }
        if (workflowProperties.useWorkflow()) {
            return handleWorkflowChat(appId, sessionId, message, loginUser, app, codeGenTypeStr);
        }
        // 6. 调用 AI 生成代码并在流完成后落库 AI 消息
        StringBuilder readableAssistantMessageBuilder = new StringBuilder();
        long startTime = System.currentTimeMillis();
        Flux<String> sourceStream = aiCodeGeneratorFacade.generateAndSaveCodeStream(message, codeGenTypeEnum, appId);
        Flux<String> handledStream = streamHandlerExecutor.handle(codeGenTypeEnum, sourceStream, readableAssistantMessageBuilder);
        return handledStream
                .doOnComplete(() -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    String aiMessage = readableAssistantMessageBuilder.toString();
                    String status = "success";
                    String extra = null;
                    if (codeGenTypeEnum == CodeGenTypeEnum.VUE_PROJECT) {
                        try {
                            log.info("Vue 项目构建开始, appId={}, sessionId={}", appId, sessionId);
                            vueProjectBuildService.buildVueProject(appId);
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
                    }
                    saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", status, codeGenTypeStr, latencyMs, extra);
                    updateSessionSummary(sessionId);
                })
                .doOnError(error -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    Map<String, String> extraInfo = new HashMap<>();
                    extraInfo.put("error", error.getMessage());
                    extraInfo.put("errorType", error.getClass().getSimpleName());
                    log.error("代码生成流程异常, appId={}, sessionId={}, codeGenType={}, userId={}, message={}",
                            appId, sessionId, codeGenTypeStr, loginUser.getId(), message, error);
                    String aiMessage = StrUtil.isBlank(readableAssistantMessageBuilder.toString())
                            ? "生成失败：" + error.getMessage()
                            : readableAssistantMessageBuilder.toString();
                    saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", "failed", codeGenTypeStr, latencyMs, JSONUtil.toJsonStr(extraInfo));
                    updateSessionSummary(sessionId);
                });
    }

    private Flux<String> handleWorkflowChat(Long appId, Long sessionId, String message, User loginUser, App app, String codeGenTypeStr) {
        StringBuilder readableAssistantMessageBuilder = new StringBuilder();
        long startTime = System.currentTimeMillis();
        return workflowCodeGeneratorService.executeWorkflowWithFlux(appId, message)
                .doOnNext(chunk -> readableAssistantMessageBuilder.append(chunk).append('\n'))
                .doOnComplete(() -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    String aiMessage = readableAssistantMessageBuilder.toString();
                    saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", "success", codeGenTypeStr, latencyMs, null);
                    updateSessionSummary(sessionId);
                })
                .doOnError(error -> {
                    int latencyMs = (int) (System.currentTimeMillis() - startTime);
                    Map<String, String> extraInfo = new HashMap<>();
                    extraInfo.put("error", error.getMessage());
                    extraInfo.put("errorType", error.getClass().getSimpleName());
                    log.error("工作流代码生成流程异常, appId={}, sessionId={}, codeGenType={}, userId={}, message={}",
                            appId, sessionId, codeGenTypeStr, loginUser.getId(), message, error);
                    String aiMessage = StrUtil.isBlank(readableAssistantMessageBuilder.toString())
                            ? "生成失败：" + error.getMessage()
                            : readableAssistantMessageBuilder.toString();
                    saveHistoryMessage(sessionId, appId, loginUser.getId(), aiMessage, "ai", "failed", codeGenTypeStr, latencyMs, JSONUtil.toJsonStr(extraInfo));
                    updateSessionSummary(sessionId);
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
        ChatSession chatSession = ChatSession.builder()
                .appId(appId)
                .userId(loginUser.getId())
                .title(sessionTitle)
                .messageCount(0)
                .modelName(app.getCodeGenType())
                .lastMessageTime(LocalDateTime.now())
                .build();
        int insertResult = chatSessionMapper.insert(chatSession);
        ThrowUtils.throwIf(insertResult <= 0 || chatSession.getId() == null, ErrorCode.OPERATION_ERROR, "创建会话失败");
        return chatSession.getId();
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
        List<ChatHistory> allHistoryList = chatHistoryMapper.selectListByQuery(queryWrapper);
        int fromIndex = (pageNum - 1) * pageSize;
        if (fromIndex >= allHistoryList.size()) {
            return new Page<>(pageNum, pageSize, allHistoryList.size());
        }
        int toIndex = Math.min(fromIndex + pageSize, allHistoryList.size());
        List<ChatHistory> pageHistoryList = allHistoryList.subList(fromIndex, toIndex);
        List<ChatHistoryVO> records = pageHistoryList.stream().map(history -> {
            ChatHistoryVO chatHistoryVO = new ChatHistoryVO();
            BeanUtil.copyProperties(history, chatHistoryVO);
            chatHistoryVO.setToolEvents(extractToolEvents(history));
            return chatHistoryVO;
        }).collect(Collectors.toList());
        Page<ChatHistoryVO> resultPage = new Page<>(pageNum, pageSize, allHistoryList.size());
        resultPage.setRecords(records);
        return resultPage;
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
        // 没有则生成 6 位 deployKey（大小写字母 + 数字）
        if (StrUtil.isBlank(deployKey)) {
            deployKey = RandomUtil.randomString(6);
        }
        // 5. 获取代码生成类型，构建源目录路径
        String codeGenType = app.getCodeGenType();
        File sourceDir;
        if (CodeGenTypeEnum.VUE_PROJECT.getValue().equals(codeGenType)) {
            Path vueProjectPath = AppConstant.getVueProjectOutputDir(appId);
            Path distPath = vueProjectPath.resolve(AppConstant.DIST_DIR_NAME);
            if (!Files.exists(distPath) || !Files.isDirectory(distPath)) {
                distPath = vueProjectBuildService.buildVueProject(appId).distPath();
            }
            sourceDir = distPath.toFile();
        } else {
            String sourceDirName = codeGenType + "_" + appId;
            String sourceDirPath = AppConstant.CODE_OUTPUT_ROOT_DIR + File.separator + sourceDirName;
            sourceDir = new File(sourceDirPath);
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
        triggerCoverGenerationAsync(appId, deployKey, app.getCover());
        // 9. 返回可访问的 URL
        return buildDeployUrl(deployKey);
    }

    @Override
    @Cacheable(cacheNames = "good_app_page", key = "T(com.adcage.acaicodefree.utils.CacheKeyUtils).generateKey('good_app_page', #pageNum, #pageSize, #appQueryRequest.priority)")
    public Page<App> listGoodAppPage(long pageNum, long pageSize, AppQueryRequest appQueryRequest) {
        QueryWrapper queryWrapper = getQueryWrapper(appQueryRequest);
        return page(Page.of(pageNum, pageSize), queryWrapper);
    }

    @PreDestroy
    public void destroyScreenshotExecutor() {
        screenshotTaskExecutor.shutdown();
    }

    private void triggerCoverGenerationAsync(Long appId, String deployKey, String existingCover) {
        if (StrUtil.isNotBlank(existingCover)) {
            updateCoverTaskState(appId, "SKIPPED", 0, null);
            log.info("应用已有封面，跳过自动截图, appId={}", appId);
            return;
        }
        updateCoverTaskState(appId, "PENDING", 0, null);
        screenshotTaskExecutor.submit(() -> {
            int maxRetries = screenshotProperties.getMaxRetries() == null ? 3 : Math.max(screenshotProperties.getMaxRetries(), 1);
            long retryDelayMillis = screenshotProperties.getRetryDelayMillis() == null ? 3000L : Math.max(screenshotProperties.getRetryDelayMillis(), 0L);
            String deployUrl = buildDeployUrl(deployKey);
            for (int attempt = 1; attempt <= maxRetries; attempt++) {
                updateCoverTaskState(appId, "RUNNING", attempt, null);
                try {
                    String coverUrl = screenshotService.generateAndUploadCover(appId, deployUrl);
                    if (StrUtil.isBlank(coverUrl)) {
                        updateCoverTaskState(appId, "FAILED", attempt, "封面地址为空");
                        continue;
                    }
                    App updateApp = new App();
                    updateApp.setId(appId);
                    updateApp.setCover(coverUrl);
                    boolean updated = this.updateById(updateApp);
                    if (!updated) {
                        updateCoverTaskState(appId, "FAILED", attempt, "封面地址回写失败");
                        log.warn("封面地址回写失败, appId={}, coverUrl={}", appId, coverUrl);
                        continue;
                    }
                    updateCoverTaskState(appId, "SUCCESS", attempt, null);
                    return;
                } catch (Exception e) {
                    updateCoverTaskState(appId, "FAILED", attempt, e.getMessage());
                    log.error("异步生成封面失败, appId={}, attempt={}", appId, attempt, e);
                    if (attempt < maxRetries && retryDelayMillis > 0) {
                        try {
                            Thread.sleep(retryDelayMillis);
                        } catch (InterruptedException interruptedException) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                    }
                }
            }
        });
    }

    private void appendCoverTaskState(AppVO appVO, Long appId) {
        if (appId == null) {
            return;
        }
        Map<String, Object> state = coverTaskStateMap.get(appId);
        if (state == null || state.isEmpty()) {
            return;
        }
        appVO.setCoverTaskStatus((String) state.getOrDefault("status", ""));
        appVO.setCoverRetryCount((Integer) state.getOrDefault("retryCount", 0));
        appVO.setCoverErrorMessage((String) state.getOrDefault("errorMessage", ""));
    }

    private void updateCoverTaskState(Long appId, String status, Integer retryCount, String errorMessage) {
        Map<String, Object> state = new HashMap<>();
        state.put("status", status);
        state.put("retryCount", retryCount == null ? 0 : retryCount);
        state.put("errorMessage", StrUtil.blankToDefault(errorMessage, ""));
        state.put("updatedTime", LocalDateTime.now());
        coverTaskStateMap.put(appId, state);
    }

    private CodeGenTypeEnum resolveCodeGenType(String requestCodeGenType, String initPrompt) {
        if (StrUtil.isNotBlank(requestCodeGenType)) {
            CodeGenTypeEnum codeGenTypeEnum = parseCodeGenType(requestCodeGenType);
            ThrowUtils.throwIf(codeGenTypeEnum == null, ErrorCode.PARAMS_ERROR, "代码生成类型错误");
            return codeGenTypeEnum;
        }
        try {
            AiCodeGenTypeRoutingService routingService = aiCodeGenTypeRoutingServiceFactory.createService();
            CodeGenTypeEnum routed = routingService.routeCodeGenType(initPrompt);
            if (routed != null) {
                return routed;
            }
        } catch (Exception e) {
            log.warn("AI 路由失败，将使用兜底模式, prompt={}", initPrompt, e);
        }
        return CodeGenTypeEnum.MULTI_FILE;
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
                .inputTokens(0)
                .outputTokens(0)
                .latencyMs(latencyMs)
                .extra(extra)
                .build();
        int insertResult = chatHistoryMapper.insert(chatHistory);
        ThrowUtils.throwIf(insertResult <= 0, ErrorCode.OPERATION_ERROR, "保存聊天记录失败");
    }

    private Integer getNextSeqNo(Long sessionId) {
        long count = chatHistoryMapper.selectCountByQuery(QueryWrapper.create().eq("sessionId", sessionId));
        return (int) (count + 1);
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

    private List<ToolEventVO> extractToolEventsFromExtra(String extra) {
        if (StrUtil.isBlank(extra)) {
            return new ArrayList<>();
        }
        try {
            JSONObject extraJson = JSONUtil.parseObj(extra);
            JSONArray toolEventArray = extraJson.getJSONArray("toolEvents");
            if (toolEventArray == null || toolEventArray.isEmpty()) {
                return new ArrayList<>();
            }
            List<ToolEventVO> toolEvents = new ArrayList<>();
            for (Object item : toolEventArray) {
                if (!(item instanceof JSONObject eventObj)) {
                    continue;
                }
                String type = normalizeToolEventType(eventObj.getStr("type"));
                String text = eventObj.getStr("text", "");
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

}
