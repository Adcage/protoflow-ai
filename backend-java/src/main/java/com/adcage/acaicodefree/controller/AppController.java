package com.adcage.acaicodefree.controller;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.annotation.AuthCheck;
import com.adcage.acaicodefree.common.BaseResponse;
import com.adcage.acaicodefree.common.DeleteRequest;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.common.ResultUtils;
import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.model.dto.app.AppAddRequest;
import com.adcage.acaicodefree.model.dto.app.AppEditRequest;
import com.adcage.acaicodefree.model.dto.app.AppQueryRequest;
import com.adcage.acaicodefree.model.dto.app.AppAdminUpdateRequest;
import com.adcage.acaicodefree.model.dto.app.AppDeployRequest;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.dto.chat.ChatCodeGenRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatSessionCreateRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatSessionRenameRequest;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.dto.app.MarketplaceQueryRequest;
import com.adcage.acaicodefree.model.vo.app.AppVO;
import com.adcage.acaicodefree.model.vo.app.MarketplaceAppVO;
import com.adcage.acaicodefree.model.vo.chat.ChatHistoryVO;
import com.adcage.acaicodefree.model.vo.chat.ChatSessionVO;
import com.adcage.acaicodefree.core.generation.ActiveGeneration;
import com.adcage.acaicodefree.core.generation.ActiveGenerationManager;
import com.adcage.acaicodefree.ratelimit.annotation.RateLimit;
import com.adcage.acaicodefree.ratelimit.enums.RateLimitType;
import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.PythonPromptEnhanceService;
import com.adcage.acaicodefree.service.ProjectDownloadService;
import com.adcage.acaicodefree.service.UserService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

import java.util.List;
import java.util.Map;
import java.nio.file.Path;

/**
 * 应用 控制层。
 *
 * @author adcage
 */
@RestController
@RequestMapping("/app")
@Slf4j
public class AppController {

    @Resource
    private AppService appService;

    @Resource
    private UserService userService;

    @Resource
    private ProjectDownloadService projectDownloadService;

    @Resource
    private ActiveGenerationManager activeGenerationManager;

    @Resource
    private PythonPromptEnhanceService pythonPromptEnhanceService;

    /**
     * 创建应用
     *
     * @param appAddRequest 创建应用请求
     * @param request       请求
     * @return 应用 id
     */
    @PostMapping("/add")
    public BaseResponse<Long> addApp(@RequestBody AppAddRequest appAddRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(appAddRequest == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(appAddRequest.getInitPrompt()), ErrorCode.PARAMS_ERROR, "初始化 prompt 不能为空");
        // 获取当前登录用户
        User loginUser = userService.getLoginUser(request);
        Long appId = appService.createApp(appAddRequest, loginUser);
        return ResultUtils.success(appId);
    }

    /**
     * 管理员创建测试应用
     *
     * @param appAddRequest 创建应用请求
     * @param request       请求
     * @return 应用 id
     */
    @PostMapping("/add/test")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Long> addTestApp(@RequestBody AppAddRequest appAddRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(appAddRequest == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(StrUtil.isBlank(appAddRequest.getInitPrompt()), ErrorCode.PARAMS_ERROR, "初始化 prompt 不能为空");
        // 强制标记为测试应用
        appAddRequest.setIsTestApp(true);
        User loginUser = userService.getLoginUser(request);
        Long appId = appService.createApp(appAddRequest, loginUser);
        return ResultUtils.success(appId);
    }

    /**
     * 优化提示词
     *
     * @param body 请求体，包含 prompt 字段
     * @param request 请求
     * @return 优化后的提示词
     */
    @PostMapping("/enhance-prompt")
    public BaseResponse<String> enhancePrompt(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String prompt = body != null ? body.get("prompt") : null;
        ThrowUtils.throwIf(StrUtil.isBlank(prompt), ErrorCode.PARAMS_ERROR, "提示词不能为空");
        User loginUser = userService.getLoginUser(request);
        log.info("优化提示词, userId={}, promptLength={}", loginUser.getId(), prompt.length());
        return ResultUtils.success(pythonPromptEnhanceService.enhancePrompt(prompt, loginUser.getId()));
    }

    /**
     * 下载应用源码 ZIP
     */
    @GetMapping("/download/{appId}")
    public void downloadAppProject(@PathVariable Long appId, HttpServletRequest request, HttpServletResponse response) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 无效");
        User loginUser = userService.getLoginUser(request);
        App app = appService.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        ThrowUtils.throwIf(!app.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR, "仅允许下载本人应用源码");
        String codeGenType = app.getCodeGenType();
        Path sourceDir;
        if (CodeGenTypeEnum.VUE_PROJECT.getValue().equals(codeGenType)) {
            sourceDir = AppConstant.getVueProjectOutputDir(appId);
        } else {
            sourceDir = AppConstant.getCodeOutputRootPath().resolve(codeGenType + "_" + appId);
        }
        String fileName = "app-" + appId + ".zip";
        projectDownloadService.writeProjectZipToResponse(sourceDir, fileName, response);
    }

    /**
     * 删除应用（用户删除自己的应用）
     *
     * @param deleteRequest 删除请求
     * @param request       请求
     * @return 是否成功
     */
    @PostMapping("/delete")
    public BaseResponse<Boolean> deleteApp(@RequestBody DeleteRequest deleteRequest, HttpServletRequest request) {
        if (deleteRequest == null || deleteRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
                
        User loginUser = userService.getLoginUser(request);
        long id = deleteRequest.getId();
        // 判断是否存在
        App oldApp = appService.getById(id);
        ThrowUtils.throwIf(oldApp == null, ErrorCode.NOT_FOUND_ERROR);
        // 仅本人可以删除
        if (!oldApp.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR);
        }
        boolean result = appService.removeById(id);
        return ResultUtils.success(result);
    }

    /**
     * 编辑应用（用户编辑自己的应用）
     *
     * @param appEditRequest 编辑请求
     * @param request        请求
     * @return 是否成功
     */
    @PostMapping("/edit")
    public BaseResponse<Boolean> editApp(@RequestBody AppEditRequest appEditRequest, HttpServletRequest request) {
        if (appEditRequest == null || appEditRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        long id = appEditRequest.getId();
        // 判断是否存在
        App oldApp = appService.getById(id);
        ThrowUtils.throwIf(oldApp == null, ErrorCode.NOT_FOUND_ERROR);
        // 仅本人可以编辑
        if (!oldApp.getUserId().equals(loginUser.getId())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR);
        }
        App app = new App();
        BeanUtil.copyProperties(appEditRequest, app);
        // 校验
        appService.validApp(app, false);
        boolean result = appService.updateById(app);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR);
        return ResultUtils.success(true);
    }

    /**
     * 根据 id 获取应用（封装类）
     *
     * @param id 应用id
     * @return AppVO
     */
    @GetMapping("/get/vo")
    public BaseResponse<AppVO> getAppVOById(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        App app = appService.getById(id);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(appService.getAppVO(app));
    }

    /**
     * 分页获取当前用户创建的应用列表
     *
     * @param appQueryRequest 查询请求
     * @param request         请求
     * @return 应用分页列表
     */
    @PostMapping("/my/list/page/vo")
    public BaseResponse<Page<AppVO>> listMyAppVOByPage(@RequestBody AppQueryRequest appQueryRequest,
            HttpServletRequest request) {
        ThrowUtils.throwIf(appQueryRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        // 限制查询自己的应用
        appQueryRequest.setUserId(loginUser.getId());
        long pageNum = appQueryRequest.getPageNum();
        long pageSize = appQueryRequest.getPageSize();
        // 限制爬虫
        ThrowUtils.throwIf(pageSize > 20, ErrorCode.PARAMS_ERROR,"禁止查询这么多数据");
        Page<App> appPage = appService.page(Page.of(pageNum, pageSize),
                appService.getQueryWrapper(appQueryRequest));
        Page<AppVO> appVOPage = new Page<>(pageNum, pageSize, appPage.getTotalRow());
        List<AppVO> appVOList = appService.getAppVOList(appPage.getRecords());
        appVOPage.setRecords(appVOList);
        return ResultUtils.success(appVOPage);
    }

    /**
     * 分页获取精选应用列表
     *
     * @param appQueryRequest 查询请求
     * @return 精选应用列表
     */
    @PostMapping("/good/list/page/vo")
    public BaseResponse<Page<AppVO>> listGoodAppVOByPage(@RequestBody AppQueryRequest appQueryRequest) {
        ThrowUtils.throwIf(appQueryRequest == null, ErrorCode.PARAMS_ERROR);
        // 限制每页最多 20 个
        long pageSize = appQueryRequest.getPageSize();
        ThrowUtils.throwIf(pageSize > 20, ErrorCode.PARAMS_ERROR, "每页最多查询 20 个应用");
        long pageNum = appQueryRequest.getPageNum();
        // 只查询精选的应用
        appQueryRequest.setPriority(AppConstant.GOOD_APP_PRIORITY);
        // 分页查询（走缓存）
        Page<App> appPage = appService.listGoodAppPage(pageNum, pageSize, appQueryRequest);
        // 数据封装
        Page<AppVO> appVOPage = new Page<>(pageNum, pageSize, appPage.getTotalRow());
        List<AppVO> appVOList = appService.getAppVOList(appPage.getRecords());
        appVOPage.setRecords(appVOList);
        return ResultUtils.success(appVOPage);
    }

    /**
     * 对话生成代码（流式返回SSE）
     * @param chatCodeGenRequest 请求体
     * @param request 请求
     * @return 生成结果流
     */
    @RateLimit(type = RateLimitType.USER, rate = 5, intervalSeconds = 60, message = "AI 对话请求过于频繁，请稍后再试")
    @PostMapping(value = "/chat/gen/code/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> chatToGenCode(@RequestBody ChatCodeGenRequest chatCodeGenRequest,
                                                       HttpServletRequest request) {
        Long appId = chatCodeGenRequest.getAppId();
        Long sessionId = chatCodeGenRequest.getSessionId();
        String rawMessage = chatCodeGenRequest.getMessage();
        boolean hasAttachments = chatCodeGenRequest.getAttachments() != null && !chatCodeGenRequest.getAttachments().isEmpty();
        String message = StrUtil.isBlank(rawMessage) && hasAttachments ? "[附件消息]" : rawMessage;
        String displayMessage = StrUtil.blankToDefault(
                chatCodeGenRequest.getDisplayMessage(),
                message
        );
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 无效");
        ThrowUtils.throwIf(StrUtil.isBlank(message) && !hasAttachments, ErrorCode.PARAMS_ERROR, "用户消息不能为空");
        // 获取当前登录用户
        User loginUser = userService.getLoginUser(request);
        Long finalSessionId = sessionId;
        if (finalSessionId == null || finalSessionId <= 0) {
            finalSessionId = appService.createChatSession(appId, loginUser);
        }
        final Long resolvedSessionId = finalSessionId;
        Flux<String> stringFlux = appService.chatToGenCode(
                appId,
                resolvedSessionId,
                message,
                displayMessage,
                chatCodeGenRequest.getAttachments(),
                loginUser
        );
        Map<String, Object> metaData = Map.of("sessionId", resolvedSessionId);
        String metaJson = JSONUtil.toJsonStr(metaData);
        ServerSentEvent<String> metaEvent = ServerSentEvent.<String>builder()
                .event("meta")
                .data(metaJson)
                .build();
        ServerSentEvent<String> doneEvent = ServerSentEvent.<String>builder()
                .event("done")
                .data("")
                .build();
        return Flux.just(metaEvent)
                .concatWith(stringFlux.map(chunk -> {
                    Map<String, String> data = Map.of("d", chunk);
                    String jsonData = JSONUtil.toJsonStr(data);
                    return ServerSentEvent.<String>builder()
                            .data(jsonData)
                            .build();
                }))
                .concatWith(Mono.just(doneEvent))
                .onErrorResume(error -> {
                    log.error("SSE 代码生成失败, appId={}, sessionId={}, userId={}, message={}",
                            appId, resolvedSessionId, loginUser.getId(), message, error);
                    int errorCode;
                    String errorMsg;
                    if (error instanceof BusinessException be) {
                        errorCode = be.getCode();
                        errorMsg = be.getMessage();
                    } else {
                        errorCode = ErrorCode.SYSTEM_ERROR.getCode();
                        errorMsg = "生成失败：" + StrUtil.nullToDefault(error.getMessage(), "未知错误");
                    }
                    Map<String, Object> errorData = Map.of("code", errorCode, "message", errorMsg);
                    ServerSentEvent<String> errorEvent = ServerSentEvent.<String>builder()
                            .event("business-error")
                            .data(JSONUtil.toJsonStr(errorData))
                            .build();
                    return Flux.just(errorEvent);
                });
    }

    /**
     * 重连活跃生成（SSE 续流）
     * 用户断线后重入页面时，通过此端点重新订阅 Sink 收后续实时事件。
     */
    @PostMapping(value = "/chat/gen/code/stream/resume", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> resumeGeneration(@RequestBody Map<String, Object> body,
                                                          HttpServletRequest request) {
        if (body == null || body.get("sessionId") == null) {
            ThrowUtils.throwIf(true, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        }
        Long sessionId = Long.parseLong(body.get("sessionId").toString());
        ThrowUtils.throwIf(sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        User loginUser = userService.getLoginUser(request);
        ThrowUtils.throwIf(loginUser == null, ErrorCode.NOT_LOGIN_ERROR, "用户未登录");
        log.info("[Resume] resumeGeneration called, sessionId={}, userId={}", sessionId, loginUser.getId());

        ActiveGeneration gen = activeGenerationManager.get(sessionId);
        log.info("[Resume] activeGeneration found={}, completed={}, textLen={}",
                gen != null, gen != null && gen.isCompleted(), gen != null ? gen.getText().length() : -1);

        if (gen == null || gen.isCompleted()) {
            log.info("[Resume] No active generation, returning 404 to frontend, sessionId={}", sessionId);
            Map<String, Object> err = Map.of("code", 404, "message", "没有活跃的生成任务");
            return Flux.just(ServerSentEvent.<String>builder()
                    .event("business-error")
                    .data(JSONUtil.toJsonStr(err))
                    .build());
        }

        Sinks.Many<String> sink = gen.getSink();
        if (sink == null) {
            log.warn("[Resume] Sink is null for active generation, sessionId={}", sessionId);
            Map<String, Object> err = Map.of("code", 500, "message", "生成 Sink 不可用");
            return Flux.just(ServerSentEvent.<String>builder()
                    .event("business-error")
                    .data(JSONUtil.toJsonStr(err))
                    .build());
        }

        log.info("[Resume] Sink acquired, subscribing for sessionId={}, agentRunId={}", sessionId, gen.getAgentRunId());

        // meta 事件携带 agentRunId
        Map<String, Object> metaData = Map.of("sessionId", sessionId, "resumed", true);
        ServerSentEvent<String> metaEvent = ServerSentEvent.<String>builder()
                .event("meta")
                .data(JSONUtil.toJsonStr(metaData))
                .build();

        ServerSentEvent<String> doneEvent = ServerSentEvent.<String>builder()
                .event("done")
                .data("")
                .build();

        // 从 Sink 订阅后续事件流
        Flux<String> eventFlux = sink.asFlux();

        return Flux.just(metaEvent)
                .concatWith(eventFlux.map(chunk -> {
                    Map<String, String> data = Map.of("d", chunk);
                    return ServerSentEvent.<String>builder()
                            .data(JSONUtil.toJsonStr(data))
                            .build();
                }))
                .concatWith(Mono.just(doneEvent))
                .onErrorResume(error -> {
                    log.error("Resume SSE error, sessionId={}", sessionId, error);
                    Map<String, Object> errorData = Map.of("code", 500, "message", "重连失败：" + error.getMessage());
                    return Flux.just(ServerSentEvent.<String>builder()
                            .event("business-error")
                            .data(JSONUtil.toJsonStr(errorData))
                            .build());
                });
    }

    /**
     * 创建会话
     *
     * @param chatSessionCreateRequest 创建会话请求
     * @param request 请求
     * @return 会话 id
     */
    @PostMapping("/chat/session/create")
    public BaseResponse<Long> createChatSession(@RequestBody ChatSessionCreateRequest chatSessionCreateRequest,
                                                HttpServletRequest request) {
        ThrowUtils.throwIf(chatSessionCreateRequest == null, ErrorCode.PARAMS_ERROR);
        Long appId = chatSessionCreateRequest.getAppId();
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 无效");
        User loginUser = userService.getLoginUser(request);
        Long sessionId = appService.createChatSession(appId, loginUser);
        return ResultUtils.success(sessionId);
    }

    /**
     * 查询应用下会话列表
     *
     * @param appId 应用 id
     * @param request 请求
     * @return 会话列表
     */
    @GetMapping("/chat/session/list")
    public BaseResponse<List<ChatSessionVO>> listChatSession(@RequestParam Long appId, HttpServletRequest request) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 无效");
        User loginUser = userService.getLoginUser(request);
        List<ChatSessionVO> chatSessionVOList = appService.listChatSession(appId, loginUser);
        return ResultUtils.success(chatSessionVOList);
    }

    /**
     * 查询会话是否有活跃生成（前端重连用）
     *
     * @param sessionId 会话 ID
     * @return 活跃生成状态和累积文本
     */
    @GetMapping("/chat/gen/active")
    public BaseResponse<Map<String, Object>> getActiveGeneration(@RequestParam Long sessionId) {
        ActiveGeneration gen = activeGenerationManager.get(sessionId);
        if (gen == null) {
            log.info("[Active] No active generation for sessionId={}", sessionId);
            return ResultUtils.success(Map.of("active", false));
        }
        log.info("[Active] sessionId={}, active={}, completed={}, textLen={}, agentRunId={}",
                sessionId, !gen.isCompleted(), gen.isCompleted(), gen.getText().length(), gen.getAgentRunId());
        return ResultUtils.success(Map.of(
                "active", !gen.isCompleted(),
                "agentRunId", gen.getAgentRunId(),
                "text", gen.getText()
        ));
    }

    /**
     * 重命名会话
     *
     * @param renameRequest 重命名请求
     * @param request       请求
     * @return 是否成功
     */
    @PostMapping("/chat/session/rename")
    public BaseResponse<Boolean> renameSession(@RequestBody ChatSessionRenameRequest renameRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(renameRequest == null, ErrorCode.PARAMS_ERROR);
        ThrowUtils.throwIf(renameRequest.getSessionId() == null || renameRequest.getSessionId() <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        ThrowUtils.throwIf(StrUtil.isBlank(renameRequest.getTitle()), ErrorCode.PARAMS_ERROR, "会话标题不能为空");
        User loginUser = userService.getLoginUser(request);
        appService.renameChatSession(renameRequest.getSessionId(), renameRequest.getTitle(), loginUser);
        return ResultUtils.success(true);
    }

    /**
     * 删除会话
     *
     * @param deleteRequest 删除请求
     * @param request       请求
     * @return 是否成功
     */
    @PostMapping("/chat/session/delete")
    public BaseResponse<Boolean> deleteSession(@RequestBody DeleteRequest deleteRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(deleteRequest == null || deleteRequest.getId() <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 无效");
        User loginUser = userService.getLoginUser(request);
        appService.deleteChatSession(deleteRequest.getId(), loginUser);
        return ResultUtils.success(true);
    }

    /**
     * 分页查询会话消息
     *
     * @param chatHistoryQueryRequest 查询参数
     * @param request 请求
     * @return 消息分页数据
     */
    @PostMapping("/chat/history/page")
    public BaseResponse<Page<ChatHistoryVO>> listChatHistoryByPage(@RequestBody ChatHistoryQueryRequest chatHistoryQueryRequest,
                                                                    HttpServletRequest request) {
        ThrowUtils.throwIf(chatHistoryQueryRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        Page<ChatHistoryVO> chatHistoryVOPage = appService.listChatHistoryByPage(chatHistoryQueryRequest, loginUser);
        return ResultUtils.success(chatHistoryVOPage);
    }

    /**
     * 应用部署
     *
     * @param appDeployRequest 部署请求
     * @param request          请求
     * @return 部署 URL
     */
    @PostMapping("/deploy")
    public BaseResponse<String> deployApp(@RequestBody AppDeployRequest appDeployRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(appDeployRequest == null, ErrorCode.PARAMS_ERROR);
        Long appId = appDeployRequest.getAppId();
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        // 获取当前登录用户
        User loginUser = userService.getLoginUser(request);
        // 调用服务部署应用
        String deployUrl = appService.deployApp(appId, loginUser);
        return ResultUtils.success(deployUrl);
    }


    // region 管理员接口

    /**
     * 更新应用（管理员）
     *
     * @param appUpdateRequest 更新请求
     * @return 是否成功
     */
    @PostMapping("/update")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Boolean> updateApp(@RequestBody AppAdminUpdateRequest appUpdateRequest) {
        if (appUpdateRequest == null || appUpdateRequest.getId() == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        App app = new App();
        BeanUtil.copyProperties(appUpdateRequest, app);
        // 校验
        appService.validApp(app, false);
        boolean result = appService.updateById(app);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR);
        return ResultUtils.success(true);
    }

    /**
     * 删除应用（管理员）
     *
     * @param deleteRequest 删除请求
     * @return 是否成功
     */
    @PostMapping("/delete/admin")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Boolean> deleteAppByAdmin(@RequestBody DeleteRequest deleteRequest) {
        if (deleteRequest == null || deleteRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        boolean result = appService.removeById(deleteRequest.getId());
        return ResultUtils.success(result);
    }

    /**
     * 根据 id 获取应用详情（管理员）
     *
     * @param id 应用id
     * @return App
     */
    @GetMapping("/get")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<App> getAppById(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        App app = appService.getById(id);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(app);
    }

    /**
     * 根据 id 获取应用详情（管理员-封装类）
     *
     * @param id 应用id
     * @return AppVO
     */
    @GetMapping("/admin/get/vo")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<AppVO> getAppVOByIdByAdmin(long id) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        App app = appService.getById(id);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR);
        return ResultUtils.success(appService.getAppVO(app));
    }

    /**
     * 分页获取应用列表（管理员）
     *
     * @param appQueryRequest 查询请求
     * @return 应用列表
     */
    @PostMapping("/admin/list/page/vo")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Page<AppVO>> listAppVOByPageByAdmin(@RequestBody AppQueryRequest appQueryRequest) {
        ThrowUtils.throwIf(appQueryRequest == null, ErrorCode.PARAMS_ERROR);
        long pageNum = appQueryRequest.getPageNum();
        long pageSize = appQueryRequest.getPageSize();
        QueryWrapper queryWrapper = appService.getQueryWrapper(appQueryRequest);
        Page<App> appPage = appService.page(Page.of(pageNum, pageSize), queryWrapper);
        // 数据封装
        Page<AppVO> appVOPage = new Page<>(pageNum, pageSize, appPage.getTotalRow());
        List<AppVO> appVOList = appService.getAppVOList(appPage.getRecords());
        appVOPage.setRecords(appVOList);
        return ResultUtils.success(appVOPage);
    }

    /**
     * 分页获取应用列表（管理员）
     *
     * @param appQueryRequest 查询请求
     * @return 应用分页列表
     */
    @PostMapping("/list/page")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Page<App>> listAppByPage(@RequestBody AppQueryRequest appQueryRequest) {
        ThrowUtils.throwIf(appQueryRequest == null, ErrorCode.PARAMS_ERROR);
        long pageNum = appQueryRequest.getPageNum();
        long pageSize = appQueryRequest.getPageSize();
        Page<App> appPage = appService.page(Page.of(pageNum, pageSize),
                appService.getQueryWrapper(appQueryRequest));
        return ResultUtils.success(appPage);
    }

    // endregion

    // region 探索广场

    @PostMapping("/publish")
    public BaseResponse<Boolean> publishApp(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        Long appId = Long.parseLong(body.get("appId").toString());
        @SuppressWarnings("unchecked")
        List<String> categories = body.get("categories") != null ? (List<String>) body.get("categories") : List.of();
        User loginUser = userService.getLoginUser(request);
        return ResultUtils.success(appService.publishApp(appId, categories, loginUser));
    }

    @PostMapping("/unpublish")
    public BaseResponse<Boolean> unpublishApp(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        Long appId = Long.parseLong(body.get("appId").toString());
        User loginUser = userService.getLoginUser(request);
        return ResultUtils.success(appService.unpublishApp(appId, loginUser));
    }

    @GetMapping("/categories")
    public BaseResponse<List<String>> listCategories() {
        return ResultUtils.success(appService.listCategories());
    }

    @PostMapping("/marketplace/list/page/vo")
    public BaseResponse<Page<MarketplaceAppVO>> listMarketplaceAppVOByPage(
            @RequestBody MarketplaceQueryRequest marketplaceQueryRequest) {
        Page<MarketplaceAppVO> page = appService.listMarketplaceAppVOByPage(marketplaceQueryRequest);
        return ResultUtils.success(page);
    }

    @PostMapping("/fork")
    public BaseResponse<Long> forkApp(@RequestBody Map<String, Object> body, HttpServletRequest request) {
        Long appId = Long.parseLong(body.get("appId").toString());
        User loginUser = userService.getLoginUser(request);
        return ResultUtils.success(appService.forkApp(appId, loginUser));
    }

    // endregion

}
