package com.adcage.acaicodefree.legacy.ai;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.service.impl.AppServiceImpl;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class AiCodeGenTypeRoutingServiceTest {

    @Test
    void resolveCodeGenType_shouldUseExplicitValueFirst() {
        AppServiceImpl appService = new AppServiceImpl();
        Object result = ReflectionTestUtils.invokeMethod(appService,
                "resolveCodeGenType", "vue_project", "后台管理系统");
        Assertions.assertEquals(CodeGenTypeEnum.VUE_PROJECT, result);
    }

    @Test
    void resolveCodeGenType_shouldFallbackToMultiFileWhenNoExplicitValue() {
        AppServiceImpl appService = new AppServiceImpl();
        Object result = ReflectionTestUtils.invokeMethod(appService,
                "resolveCodeGenType", null, "个人简介页面");
        Assertions.assertEquals(CodeGenTypeEnum.MULTI_FILE, result);
    }
}
