package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.adcage.acaicodefree.workflow.service.WorkflowCodeGeneratorService;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;

@Component
public class JavaWorkflowRuntime implements CodeGenerationRuntime {

    private static final String NAME = "java-workflow";

    @Resource
    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public Flux<String> stream(CodeGenerationRequest request) {
        return workflowCodeGeneratorService.executeWorkflowWithFlux(request.getAppId(), request.getMessage());
    }
}
