package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.core.generation.ActiveGeneration;
import com.adcage.acaicodefree.core.generation.ActiveGenerationManager;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.ChatSession;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.model.vo.chat.ToolInfoVO;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntimeRouter;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.PlaygroundService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Playground 服务层实现
 */
@Service
public class PlaygroundServiceImpl implements PlaygroundService {

    private static final Logger log = LoggerFactory.getLogger(PlaygroundServiceImpl.class);

    /**
     * 虚拟测试 App 特殊标记：isTestApp = 2 表示 Playground 虚拟 App
     */
    private static final int PLAYGROUND_APP_MARKER = 2;

    /**
     * 可用工具列表（硬编码，与 Python 端 create_implementor_tools 对齐）
     */
    private static final List<ToolInfoVO> AVAILABLE_TOOLS = List.of(
            ToolInfoVO.builder().name("Read").displayName("读取文件").description("读取文件或目录内容").category("file").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Write").displayName("写入文件").description("创建新文件并写入内容").category("file").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Edit").displayName("编辑文件").description("精确替换文件中的内容").category("file").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Insert").displayName("插入文本").description("在文件指定行插入文本").category("file").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Glob").displayName("搜索文件").description("按文件名模式搜索文件路径").category("search").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Grep").displayName("搜索内容").description("按正则表达式搜索文件内容").category("search").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("Bash").displayName("执行命令").description("执行终端命令（白名单限制）").category("system").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("LoadSkill").displayName("加载技能").description("加载技能规则到上下文").category("knowledge").defaultEnabled(true).build(),
            ToolInfoVO.builder().name("AskUser").displayName("向用户提问").description("向用户提问并暂停等待回复").category("interaction").defaultEnabled(false).build(),
            ToolInfoVO.builder().name("SearchDocs").displayName("检索文档").description("从知识库检索技术文档").category("knowledge").defaultEnabled(false).build()
    );

    @Resource
    private AppService appService;

    @Resource
    private ChatSessionMapper chatSessionMapper;

    @Resource
    private ChatHistoryMapper chatHistoryMapper;

    @Resource
    private AgentRunService agentRunService;

    @Resource
    private WorkspaceProperties workspaceProperties;

    @Resource
    private CodeGenerationRuntimeRouter codeGenerationRuntimeRouter;

    @Resource
    private ActiveGenerationManager activeGenerationManager;

    /**
     * 缓存的虚拟 App ID，避免每次请求都查询数据库
     */
    private final AtomicLong cachedVirtualAppId = new AtomicLong(0);

    @Override
    public Flux<String> playgroundChat(String message, List<String> enabledTools, User loginUser) {
        ThrowUtils.throwIf(StrUtil.isBlank(message), ErrorCode.PARAMS_ERROR, "用户消息不能为空");

        // 1. 获取/创建虚拟测试 App
        App virtualApp = getOrCreateVirtualApp();

        // 2. 获取/创建该管理员的 Playground Session
        ChatSession session = getOrCreatePlaygroundSession(virtualApp.getId(), loginUser.getId());
        Long sessionId = session.getId();

        // 3. 保存用户消息到 chat_history
        saveHistoryMessage(sessionId, virtualApp.getId(), loginUser.getId(), message, "user", "success");

        // 4. 创建 AgentRun
        CodeGenerationRuntime runtime = codeGenerationRuntimeRouter.select();
        Long agentRunId = agentRunService.createAgentRun(virtualApp.getId(), sessionId, loginUser.getId(), runtime.getName());
        String workspacePath = workspaceProperties.getAgentWorkspaceDir() + "/playground/" + loginUser.getId();
        agentRunService.updateAgentRunWorkspacePath(agentRunId, workspacePath);

        // 5. 构建 CodeGenerationRequest
        String runtimeOptionsJson = JSONUtil.toJsonStr(Map.of("enabled_tools", enabledTools));
        CodeGenerationRequest runtimeRequest = CodeGenerationRequest.builder()
                .agentRunId(agentRunId)
                .appId(virtualApp.getId())
                .sessionId(sessionId)
                .message(message)
                .app(virtualApp)
                .loginUser(loginUser)
                .codeGenTypeEnum(CodeGenTypeEnum.SINGLE_FILE)
                .generationMode("test_playground")
                .workspacePath(workspacePath)
                .isTest(true)  // Playground 始终是测试模式
                .runtimeOptionsJson(runtimeOptionsJson)
                .build();

        // 6. 注册活跃生成状态 + 获取 SSE 流
        ActiveGeneration activeGen = activeGenerationManager.register(sessionId, agentRunId);
        activeGen.setOnGenerationCompleted(finalText -> {
            log.info("[Playground] onGenerationCompleted, sessionId={}, agentRunId={}, textLen={}",
                    sessionId, agentRunId, finalText != null ? finalText.length() : 0);
            activeGenerationManager.remove(sessionId);
        });

        Flux<String> sourceStream = runtime.stream(runtimeRequest);

        // Playground 模式不做构建/部署/截图，直接返回源流
        return sourceStream
                .doOnError(error -> {
                    log.error("[Playground] SSE error, sessionId={}, agentRunId={}", sessionId, agentRunId, error);
                })
                .doFinally(signalType -> {
                    log.info("[Playground] SSE finished, signal={}, sessionId={}", signalType, sessionId);
                    activeGenerationManager.remove(sessionId);
                });
    }

    @Override
    public List<ToolInfoVO> listAvailableTools() {
        return AVAILABLE_TOOLS;
    }

    @Override
    public Long resetPlayground(User loginUser) {
        App virtualApp = getOrCreateVirtualApp();
        // 创建新的 Session
        ChatSession newSession = ChatSession.builder()
                .appId(virtualApp.getId())
                .userId(loginUser.getId())
                .title("Playground " + LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("HH:mm")))
                .messageCount(0)
                .build();
        chatSessionMapper.insert(newSession);
        return newSession.getId();
    }

    // ── 私有方法 ──────────────────────────────────────────────────

    /**
     * 获取或创建虚拟测试 App（全局单例）
     */
    private App getOrCreateVirtualApp() {
        long cachedId = cachedVirtualAppId.get();
        if (cachedId > 0) {
            App app = appService.getById(cachedId);
            if (app != null) {
                return app;
            }
        }

        // 查询已有的 Playground 虚拟 App
        App existing = appService.getOne(QueryWrapper.create()
                .eq("isTestApp", PLAYGROUND_APP_MARKER));
        if (existing != null) {
            cachedVirtualAppId.set(existing.getId());
            return existing;
        }

        // 创建虚拟 App
        App virtualApp = new App();
        virtualApp.setAppName("AI Playground (System)");
        virtualApp.setInitPrompt("[SYSTEM] AI Playground");
        virtualApp.setCodeGenType("single_file");
        virtualApp.setGenerationMode("test_playground");
        virtualApp.setIsTestApp(PLAYGROUND_APP_MARKER);
        virtualApp.setUserId(0L);
        virtualApp.setIsPublic(0);
        appService.save(virtualApp);
        cachedVirtualAppId.set(virtualApp.getId());
        log.info("[Playground] 虚拟测试 App 创建成功, appId={}", virtualApp.getId());
        return virtualApp;
    }

    /**
     * 获取或创建该管理员的 Playground Session
     */
    private ChatSession getOrCreatePlaygroundSession(Long virtualAppId, Long userId) {
        // 查找该用户最近的 Session
        ChatSession latestSession = chatSessionMapper.selectOneByQuery(QueryWrapper.create()
                .eq("appId", virtualAppId)
                .eq("userId", userId)
                .orderBy("createTime", false)
                .limit(1));
        if (latestSession != null) {
            return latestSession;
        }

        // 创建新 Session
        ChatSession newSession = ChatSession.builder()
                .appId(virtualAppId)
                .userId(userId)
                .title("Playground")
                .messageCount(0)
                .build();
        chatSessionMapper.insert(newSession);
        return newSession;
    }

    /**
     * 保存聊天历史记录
     */
    private void saveHistoryMessage(Long sessionId, Long appId, Long userId, String message,
                                    String messageType, String status) {
        // 获取下一个序号
        Integer nextSeqNo = getNextSeqNo(sessionId);

        ChatHistory chatHistory = ChatHistory.builder()
                .sessionId(sessionId)
                .seqNo(nextSeqNo)
                .message(StrUtil.blankToDefault(message, ""))
                .messageType(messageType)
                .status(status)
                .appId(appId)
                .userId(userId)
                .build();
        int insertResult = chatHistoryMapper.insert(chatHistory);
        ThrowUtils.throwIf(insertResult <= 0, ErrorCode.OPERATION_ERROR, "保存聊天记录失败");

        // 更新 Session 摘要
        ChatSession session = chatSessionMapper.selectOneByQuery(QueryWrapper.create().eq("id", sessionId));
        if (session != null) {
            long count = chatHistoryMapper.selectCountByQuery(QueryWrapper.create().eq("sessionId", sessionId));
            session.setMessageCount((int) count);
            session.setLastMessageTime(LocalDateTime.now());
            chatSessionMapper.update(session);
        }
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
}
