package com.adcage.acaicodefree.legacy.runtime.impl;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.stereotype.Component;

class JavaAgentRuntimeTest {

    @Test
    void javaAgentRuntime_shouldBeDeprecatedLegacyOnly() {
        Assertions.assertTrue(JavaAgentRuntime.class.isAnnotationPresent(Deprecated.class));
    }

    @Test
    void javaAgentRuntime_shouldNotBeSpringComponent() {
        Assertions.assertFalse(JavaAgentRuntime.class.isAnnotationPresent(Component.class));
    }
}
