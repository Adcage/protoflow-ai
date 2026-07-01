package com.adcage.acaicodefree.config.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "app.ai.runtime-models")
public class RuntimeModelProperties {

    private ModelConfig light = new ModelConfig();

    private ModelConfig primary = new ModelConfig();

    private ModelConfig critic = new ModelConfig();

    private ModelConfig repair = new ModelConfig();

    /** Embedding 模型配置，用于 RAG 技术文档库的向量化。不 fallback 到 primary。 */
    private ModelConfig embedding = new ModelConfig();

    @Data
    public static class ModelConfig {
        private String provider = "";
        private String baseUrl = "";
        private String apiKey = "";
        private String modelName = "";
    }
}
