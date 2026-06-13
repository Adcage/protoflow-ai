package com.adcage.acaicodefree.legacy.ai;

import com.adcage.acaicodefree.legacy.ai.model.SingleCodeResult;
import com.adcage.acaicodefree.legacy.ai.model.MultiFileCodeResult;
import jakarta.annotation.Resource;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import reactor.core.publisher.Flux;

@SpringBootTest
@Disabled("依赖真实模型与网络环境，默认回归中跳过")
class AiCodeGeneratorServiceTest {

    @Resource
    private AiCodeGeneratorService aiCodeGeneratorService;

    @Test
    void generateSingleFileCode() {
        SingleCodeResult code = aiCodeGeneratorService.generateSingleFileCode("做一个个人博客界面,不超20行");
        System.out.println(code);
    }

    @Test
    void generateMultiFileCode() {
        MultiFileCodeResult code = aiCodeGeneratorService.generateMultiFileCode("做一个个人博客界面,不超过50行");
        System.out.println(code);
    }

    @Test
    void testChat() {
        String chat = aiCodeGeneratorService.chat("你好,你是谁");
        System.out.println(chat);
    }

    // ============流式输出测试================
    @Test
    void generateMultiFileCodeStream() {
        Flux<String> stringFlux = aiCodeGeneratorService.chatStream("你好,你是谁");
        stringFlux.doOnNext(token -> {
            System.out.println("这次输出:" + token);
        }).blockLast();
    }

}
