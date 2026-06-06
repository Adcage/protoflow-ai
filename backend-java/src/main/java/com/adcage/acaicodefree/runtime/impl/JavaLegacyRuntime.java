package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class JavaLegacyRuntime implements CodeGenerationRuntime {

    private static final String NAME = "java-legacy";

    @Resource
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public Flux<String> stream(CodeGenerationRequest request) {
        return aiCodeGeneratorFacade.generateAndSaveCodeStream(
                request.getMessage(),
                request.getCodeGenTypeEnum(),
                request.getAppId()
        );
    }
}
