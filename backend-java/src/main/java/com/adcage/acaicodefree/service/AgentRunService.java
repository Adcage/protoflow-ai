package com.adcage.acaicodefree.service;

import com.mybatisflex.core.service.IService;
import com.adcage.acaicodefree.model.entity.AgentRun;

public interface AgentRunService extends IService<AgentRun> {

    Long createAgentRun(Long appId, Long sessionId, Long userId, String runtime);

    Long createAgentRun(Long appId, Long sessionId, Long userId, String runtime,
                        Long modelConfigId, Integer configVersion, String workspacePath);

    void completeAgentRun(Long id, String workspacePath, Integer latencyMs);

    void failAgentRun(Long id, String errorMessage);

    void failRunningRun(Long appId, Long sessionId, Long userId, String errorMessage);

    void updateAgentRunWorkspacePath(Long id, String workspacePath);

    void pauseAgentRun(Long id, String loopStateJson);

    AgentRun claimLatestPausedRun(Long appId, Long sessionId, Long userId);

    boolean hasRunningRun(Long appId, Long sessionId, Long userId);
}
