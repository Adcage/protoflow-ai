package com.adcage.acaicodefree.runtime;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PythonAgentEvent {
    private String agentRunId;
    private Long seq;
    private String eventType;
    private Map<String, Object> data;
}
