package com.adcage.acaicodefree.runtime.impl;

import com.adcage.acaicodefree.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;
import reactor.test.StepVerifier;

class JavaLegacyRuntimeTest {

    @Test
    void stream_shouldDelegateToAiCodeGeneratorFacade() {
        AiCodeGeneratorFacade facade = Mockito.mock(AiCodeGeneratorFacade.class);
        JavaLegacyRuntime runtime = new JavaLegacyRuntime();
        ReflectionTestUtils.setField(runtime, "aiCodeGeneratorFacade", facade);
        Mockito.when(facade.generateAndSaveCodeStream("build app", CodeGenTypeEnum.VUE_PROJECT, 1L))
                .thenReturn(Flux.just("chunk-1", "chunk-2"));

        CodeGenerationRequest request = CodeGenerationRequest.builder()
                .appId(1L)
                .message("build app")
                .codeGenTypeEnum(CodeGenTypeEnum.VUE_PROJECT)
                .build();

        StepVerifier.create(runtime.stream(request))
                .expectNext("chunk-1")
                .expectNext("chunk-2")
                .verifyComplete();

        Mockito.verify(facade).generateAndSaveCodeStream("build app", CodeGenTypeEnum.VUE_PROJECT, 1L);
    }

    @Test
    void getName_shouldReturnJavaLegacy() {
        Assertions.assertEquals("java-legacy", new JavaLegacyRuntime().getName());
    }
}
