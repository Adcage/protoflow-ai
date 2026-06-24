package com.adcage.acaicodefree.runtime;

import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class CodeGenerationRequest {
    private Long agentRunId;
    private Long appId;
    private Long sessionId;
    private String message;
    private App app;
    private User loginUser;
    private CodeGenTypeEnum codeGenTypeEnum;
    private String generationMode;
    private Long modelConfigId;
    private Integer configVersion;
    private String workspacePath;
    private String loopStateJson;
    private Boolean isTest;
}
