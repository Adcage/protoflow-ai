package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.AgentRunMapper;
import com.adcage.acaicodefree.model.entity.AgentRun;
import com.adcage.acaicodefree.service.AgentRunService;
import com.mybatisflex.spring.service.impl.ServiceImpl;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class AgentRunServiceImpl extends ServiceImpl<AgentRunMapper, AgentRun> implements AgentRunService {

    @Override
    public Long createAgentRun(Long appId, Long sessionId, Long userId, String runtime) {
        return createAgentRun(appId, sessionId, userId, runtime, null, null, null);
    }

    @Override
    public Long createAgentRun(Long appId, Long sessionId, Long userId, String runtime,
                               Long modelConfigId, Integer configVersion, String workspacePath) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 不能为空");
        ThrowUtils.throwIf(userId == null || userId <= 0, ErrorCode.PARAMS_ERROR, "用户 ID 不能为空");
        AgentRun agentRun = AgentRun.builder()
                .appId(appId)
                .sessionId(sessionId)
                .userId(userId)
                .runtime(runtime)
                .modelConfigId(modelConfigId)
                .configVersion(configVersion)
                .workspacePath(workspacePath)
                .status("running")
                .latencyMs(0)
                .createTime(LocalDateTime.now())
                .build();
        boolean saveResult = this.save(agentRun);
        ThrowUtils.throwIf(!saveResult, ErrorCode.OPERATION_ERROR, "创建 AgentRun 失败");
        return agentRun.getId();
    }

    @Override
    public void completeAgentRun(Long id, String workspacePath, Integer latencyMs) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "AgentRun ID 不能为空");
        AgentRun agentRun = this.getById(id);
        ThrowUtils.throwIf(agentRun == null, ErrorCode.NOT_FOUND_ERROR, "AgentRun 不存在");
        AgentRun update = AgentRun.builder()
                .id(id)
                .status("completed")
                .workspacePath(workspacePath)
                .latencyMs(latencyMs)
                .loopStateJson("")
                .build();
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新 AgentRun 状态失败");
    }

    @Override
    public void failAgentRun(Long id, String errorMessage) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "AgentRun ID 不能为空");
        AgentRun agentRun = this.getById(id);
        ThrowUtils.throwIf(agentRun == null, ErrorCode.NOT_FOUND_ERROR, "AgentRun 不存在");
        AgentRun update = AgentRun.builder()
                .id(id)
                .status("failed")
                .errorMessage(errorMessage)
                .loopStateJson("")
                .build();
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新 AgentRun 状态失败");
    }

    @Override
    public void failRunningRun(Long appId, Long sessionId, Long userId, String errorMessage) {
        AgentRun running = getOne(QueryWrapper.create()
                .eq("appId", appId)
                .eq("sessionId", sessionId)
                .eq("userId", userId)
                .eq("status", "running"));
        if (running != null) {
            failAgentRun(running.getId(), errorMessage);
        }
    }

    @Override
    public void updateAgentRunWorkspacePath(Long id, String workspacePath) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "AgentRun ID 不能为空");
        AgentRun agentRun = this.getById(id);
        ThrowUtils.throwIf(agentRun == null, ErrorCode.NOT_FOUND_ERROR, "AgentRun 不存在");
        AgentRun update = AgentRun.builder()
                .id(id)
                .workspacePath(workspacePath)
                .build();
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新 AgentRun 工作空间路径失败");
    }

    @Override
    public void pauseAgentRun(Long id, String loopStateJson) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "AgentRun ID 不能为空");
        AgentRun agentRun = this.getById(id);
        ThrowUtils.throwIf(agentRun == null, ErrorCode.NOT_FOUND_ERROR, "AgentRun 不存在");
        AgentRun update = AgentRun.builder()
                .id(id)
                .status("waiting_for_user")
                .loopStateJson(loopStateJson)
                .build();
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新 AgentRun 暂停状态失败");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentRun claimLatestPausedRun(Long appId, Long sessionId, Long userId) {
        AgentRun paused = mapper.selectLatestWaitingForUpdate(appId, sessionId, userId);
        if (paused == null) {
            return null;
        }
        AgentRun update = AgentRun.builder()
                .id(paused.getId())
                .status("running")
                .build();
        boolean updated = updateById(update);
        ThrowUtils.throwIf(!updated, ErrorCode.OPERATION_ERROR, "恢复 AgentRun 失败");
        paused.setStatus("running");
        return paused;
    }

    @Override
    public boolean hasRunningRun(Long appId, Long sessionId, Long userId) {
        return count(QueryWrapper.create()
                .eq("appId", appId)
                .eq("sessionId", sessionId)
                .eq("userId", userId)
                .eq("status", "running")) > 0;
    }
}
