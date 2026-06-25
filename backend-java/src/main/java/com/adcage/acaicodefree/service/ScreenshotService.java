package com.adcage.acaicodefree.service;

public interface ScreenshotService {

    /**
     * 根据应用访问地址生成封面并上传，返回可访问 URL
     *
     * @param appId   应用 id
     * @param appUrl  应用访问地址
     * @return 封面图 URL
     */
    String generateAndUploadCover(Long appId, String appUrl);

    /**
     * 在 Agent 运行结束后触发封面截图（如果需要）。
     * 基于 AgentRun 粒度追踪：同一 AgentRun 内防重复，不同 AgentRun 允许更新封面。
     *
     * @param appId      应用 id
     * @param agentRunId 当前 AgentRun id（用于防重复和追踪）
     */
    void triggerCoverGenerationIfNeeded(Long appId, Long agentRunId);
}
