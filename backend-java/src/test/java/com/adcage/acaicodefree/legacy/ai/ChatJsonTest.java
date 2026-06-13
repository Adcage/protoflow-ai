package com.adcage.acaicodefree.legacy.ai;

import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.response.ChatResponse;
import dev.langchain4j.model.openai.OpenAiChatModel;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("local")
@Slf4j
@Disabled("依赖真实模型与网络环境，默认回归中跳过")
public class ChatJsonTest {
    @Resource
    private AiCodeGeneratorService aiService;

    @Value("${langchain4j.open-ai.chat-model.base-url}")
    private String baseUrl;

    @Value("${langchain4j.open-ai.chat-model.api-key}")
    private String apiKey;

    @Value("${langchain4j.open-ai.chat-model.model-name}")
    private String modelName;

    @Value("${langchain4j.open-ai.chat-model.response-format:}")
    private String responseFormat;


    @Test
    public void test() {
        Assumptions.assumeTrue(apiKey != null && !apiKey.isBlank() && !"<your-api-key>".equals(apiKey), "未配置可用 API Key，跳过测试");
        OpenAiChatModel.OpenAiChatModelBuilder modelBuilder = OpenAiChatModel.builder()
                .baseUrl(baseUrl)
                .apiKey(apiKey)
                .modelName(modelName)
                .logRequests(true);
        if (responseFormat != null && !responseFormat.isBlank()) {
            modelBuilder.responseFormat(responseFormat);
        }
        OpenAiChatModel openAiChatModel = modelBuilder.build();
        ChatResponse chatResponse = openAiChatModel.chat(ChatRequest.builder()
                .messages(UserMessage.from("你好,响应数据格式为{response:回答}"))
                .build());
        String chat = chatResponse.aiMessage().text();
        Assertions.assertNotNull(chat);
        Assertions.assertFalse(chat.isBlank());
        System.out.println(chat);
    }

    @Test
    public void test2() {
        String chat = aiService.chat("你好");
        System.out.println(chat);
    }
}
