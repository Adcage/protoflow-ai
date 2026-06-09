package com.adcage.acaicodefree.runtime;

import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.BusinessException;
import jakarta.annotation.Resource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class CodeGenerationRuntimeRouter {

    @Resource
    private List<CodeGenerationRuntime> runtimes;

    @Value("${agent.runtime:java-agent}")
    private String runtimeName;

    public CodeGenerationRuntime select() {
        return runtimes.stream()
                .filter(runtime -> runtime.getName().equalsIgnoreCase(runtimeName))
                .findFirst()
                .orElseThrow(() -> new BusinessException(ErrorCode.SYSTEM_ERROR, "未找到代码生成运行时：" + runtimeName));
    }
}
