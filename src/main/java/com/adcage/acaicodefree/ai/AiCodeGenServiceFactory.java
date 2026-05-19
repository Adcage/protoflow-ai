package com.adcage.acaicodefree.ai;

import com.adcage.acaicodefree.ai.tools.ToolManager;
import com.adcage.acaicodefree.core.memory.ChatMemoryLoader;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import dev.langchain4j.memory.ChatMemory;
import dev.langchain4j.memory.chat.MessageWindowChatMemory;
import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.chat.StreamingChatLanguageModel;
import dev.langchain4j.service.AiServices;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;

@Component
public class AiCodeGenServiceFactory {

    private static final Logger log = LoggerFactory.getLogger(AiCodeGenServiceFactory.class);

    @Resource
    private ChatLanguageModel chatModel;

    @Resource(name = "openAiStreamingChatModel")
    private StreamingChatLanguageModel legacyStreamingChatLanguageModel;

    @Resource(name = "reasoningStreamingChatModel")
    private StreamingChatLanguageModel reasoningStreamingChatModel;

    @Resource(name = "routingChatModel")
    private ChatLanguageModel routingChatModel;

    @Resource
    private ToolManager toolManager;

    @Resource
    private ObjectProvider<ChatMemoryLoader> chatMemoryLoaderProvider;

    @Value("${app.ai.vue-project.memory-window-size:20}")
    private int memoryWindowSize;

    @Value("${app.ai.max-sequential-tools-invocations:20}")
    private int maxSequentialToolsInvocations;

    private final Cache<String, AiCodeGeneratorService> serviceCache = Caffeine.newBuilder()
            .maximumSize(1000)
            .expireAfterWrite(30, TimeUnit.MINUTES)
            .expireAfterAccess(10, TimeUnit.MINUTES)
            .build();

    public AiCodeGeneratorService getService(Long appId, CodeGenTypeEnum codeGenType) {
        String cacheKey = buildCacheKey(appId, codeGenType);
        return serviceCache.get(cacheKey, ignored -> createService(appId, codeGenType));
    }

    String buildCacheKey(Long appId, CodeGenTypeEnum codeGenType) {
        return appId + ":" + codeGenType.getValue();
    }

    private AiCodeGeneratorService createService(Long appId, CodeGenTypeEnum codeGenType) {
        if (codeGenType == CodeGenTypeEnum.VUE_PROJECT) {
            log.info("创建代码生成服务, appId={}, codeGenType={}, streamModel=reasoning, tools=enabled", appId, codeGenType);
            return createToolService(appId, reasoningStreamingChatModel);
        }
        log.info("创建代码生成服务, appId={}, codeGenType={}, streamModel=legacy, tools=enabled", appId, codeGenType);
        return createToolService(appId, legacyStreamingChatLanguageModel);
    }

    /**
     * 创建带工具的服务（统一使用）
     */
    protected AiCodeGeneratorService createToolService(Long appId, StreamingChatLanguageModel streamingChatLanguageModel) {
        log.info("工具调用上限配置: maxSequentialToolsInvocations={}, 注意: LangChain4j 0.36.2 不支持通过 builder API 设置此参数，当前由框架内部硬编码为 100，配置值将在升级后生效",
                maxSequentialToolsInvocations);
        return AiServices.builder(AiCodeGeneratorService.class)
                .chatLanguageModel(chatModel)
                .streamingChatLanguageModel(streamingChatLanguageModel)
                .tools(toolManager.getAllTools())
                .chatMemoryProvider(memoryId -> resolveChatMemory(memoryId, appId))
                .build();
    }

    public ChatLanguageModel getRoutingModel() {
        return routingChatModel;
    }

    ChatMemory resolveChatMemory(Object memoryId, Long appId) {
        Long currentAppId;
        if (memoryId instanceof Long longMemoryId) {
            currentAppId = longMemoryId;
        } else {
            currentAppId = appId;
        }

        ChatMemoryLoader chatMemoryLoader = chatMemoryLoaderProvider.getIfAvailable();
        if (chatMemoryLoader == null) {
            log.warn("ChatMemoryLoader bean unavailable during restart, fallback to in-memory chat window");
            return MessageWindowChatMemory.withMaxMessages(memoryWindowSize);
        }
        return chatMemoryLoader.load(currentAppId);
    }
}
