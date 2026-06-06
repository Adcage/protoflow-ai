package com.adcage.acaicodefree.runtime;

import com.adcage.acaicodefree.exception.BusinessException;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;

import java.util.List;

class CodeGenerationRuntimeRouterTest {

    @Test
    void select_shouldReturnConfiguredRuntime() {
        CodeGenerationRuntimeRouter router = new CodeGenerationRuntimeRouter();
        ReflectionTestUtils.setField(router, "runtimes", List.of(new StubRuntime("java-legacy"), new StubRuntime("python-agent")));
        ReflectionTestUtils.setField(router, "runtimeName", "python-agent");

        CodeGenerationRuntime selected = router.select();

        Assertions.assertEquals("python-agent", selected.getName());
    }

    @Test
    void select_shouldThrowWhenRuntimeMissing() {
        CodeGenerationRuntimeRouter router = new CodeGenerationRuntimeRouter();
        ReflectionTestUtils.setField(router, "runtimes", List.of(new StubRuntime("java-legacy")));
        ReflectionTestUtils.setField(router, "runtimeName", "python-agent");

        BusinessException exception = Assertions.assertThrows(BusinessException.class, router::select);

        Assertions.assertTrue(exception.getMessage().contains("未找到代码生成运行时"));
    }

    private record StubRuntime(String name) implements CodeGenerationRuntime {
        @Override
        public String getName() {
            return name;
        }

        @Override
        public Flux<String> stream(CodeGenerationRequest request) {
            return Flux.just("ok");
        }
    }
}
