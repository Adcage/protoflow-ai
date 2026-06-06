package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.workflow.service.WorkflowCodeGeneratorService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class JavaWorkflowRuntimeTest {

    @Test
    void stream_shouldDelegateToWorkflowService() {
        WorkflowCodeGeneratorService workflowService = Mockito.mock(WorkflowCodeGeneratorService.class);
        JavaWorkflowRuntime runtime = new JavaWorkflowRuntime();
        ReflectionTestUtils.setField(runtime, "workflowCodeGeneratorService", workflowService);
        Mockito.when(workflowService.executeWorkflowWithFlux(1L, "build app"))
                .thenReturn(Flux.just("workflow-start", "workflow-done"));

        CodeGenerationRequest request = CodeGenerationRequest.builder()
                .appId(1L)
                .message("build app")
                .build();

        StepVerifier.create(runtime.stream(request))
                .expectNext("workflow-start")
                .expectNext("workflow-done")
                .verifyComplete();
    }

    @Test
    void getName_shouldReturnJavaWorkflow() {
        Assertions.assertEquals("java-workflow", new JavaWorkflowRuntime().getName());
    }
}
