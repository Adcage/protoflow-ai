package com.adcage.acaicodefree.legacy.config;

import dev.langchain4j.model.chat.StreamingChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiStreamingChatModel;
import jakarta.annotation.Resource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;

/**
 * @deprecated Java LangChain4j 推理模型配置已禁用，模型调用必须通过 Python Agent Runtime。
 */
@Deprecated(since = "2026-06-13", forRemoval = false)
@Configuration
public class ReasoningStreamingChatModelConfig {

    @Value("${app.ai.vue-project.base-url}")
    private String baseUrl;

    @Value("${app.ai.vue-project.api-key:}")
    private String apiKey;

    @Value("${app.ai.vue-project.dev-model-name}")
    private String devModelName;

    @Value("${app.ai.vue-project.prod-model-name}")
    private String prodModelName;

    @Value("${app.ai.vue-project.dev-max-tokens}")
    private Integer devMaxTokens;

    @Value("${app.ai.vue-project.prod-max-tokens}")
    private Integer prodMaxTokens;

    @Value("${app.ai.vue-project.temperature:0.1}")
    private Double temperature;

    @Value("${app.ai.vue-project.max-retries:2}")
    private Integer maxRetries;

    @Resource
    private Environment environment;

    @Bean("reasoningStreamingChatModel")
    public StreamingChatLanguageModel reasoningStreamingChatModel() {
        boolean useDevModel = environment.acceptsProfiles(Profiles.of("local"));
        return OpenAiStreamingChatModel.builder()
                .baseUrl(baseUrl)
                .apiKey(apiKey)
                .modelName(useDevModel ? devModelName : prodModelName)
                .maxTokens(useDevModel ? devMaxTokens : prodMaxTokens)
                .temperature(temperature)
                .logRequests(true)
                .logResponses(true)
                .build();
    }
}
