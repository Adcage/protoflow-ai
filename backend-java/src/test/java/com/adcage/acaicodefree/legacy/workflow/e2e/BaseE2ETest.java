package com.adcage.acaicodefree.legacy.workflow.e2e;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.condition.EnabledIf;

@Tag("e2e")
@EnabledIf("isE2EEnabled")
public abstract class BaseE2ETest {

    static boolean isE2EEnabled() {
        return Boolean.parseBoolean(System.getProperty("e2e.enabled", "false"));
    }
}