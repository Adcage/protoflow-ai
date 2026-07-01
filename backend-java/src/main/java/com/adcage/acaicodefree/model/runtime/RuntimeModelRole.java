package com.adcage.acaicodefree.model.runtime;

public enum RuntimeModelRole {
    LIGHT("light"),
    PRIMARY("primary"),
    CRITIC("critic"),
    REPAIR("repair"),
    EMBEDDING("embedding");

    private final String value;

    RuntimeModelRole(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}
