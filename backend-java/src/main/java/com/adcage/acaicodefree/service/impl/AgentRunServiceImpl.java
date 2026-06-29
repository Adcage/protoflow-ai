package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.AgentRunMapper;
import com.adcage.acaicodefree.model.entity.AgentRun;
import com.adcage.acaicodefree.model.vo.user.DailyTokenUsageVO;
import com.adcage.acaicodefree.model.vo.user.TokenUsageStatsVO;
import com.adcage.acaicodefree.service.AgentRunService;
import com.mybatisflex.spring.service.impl.ServiceImpl;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class AgentRunServiceImpl extends ServiceImpl<AgentRunMapper, AgentRun> implements AgentRunService {

    @Override
    public Long createAgentRun(Long appId, Long sessionId, Long userId, String runtime) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 不能为空");
        ThrowUtils.throwIf(sessionId == null || sessionId <= 0, ErrorCode.PARAMS_ERROR, "会话 ID 不能为空");
        ThrowUtils.throwIf(userId == null || userId <= 0, ErrorCode.PARAMS_ERROR, "用户 ID 不能为空");
        AgentRun agentRun = AgentRun.builder()
                .appId(appId)
                .sessionId(sessionId)
                .userId(userId)
                .runtime(runtime)
                .status("running")
                .latencyMs(0)
                .createTime(LocalDateTime.now())
                .build();
        boolean saveResult = this.save(agentRun);
        ThrowUtils.throwIf(!saveResult, ErrorCode.OPERATION_ERROR, "创建 AgentRun 失败");
        return agentRun.getId();
    }

    @Override
    public void completeAgentRun(Long id, String workspacePath, Integer latencyMs,
                                  Integer inputTokens, Integer outputTokens,
                                  Integer cacheReadTokens, Integer cacheCreationTokens) {
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "AgentRun ID 不能为空");
        AgentRun agentRun = this.getById(id);
        ThrowUtils.throwIf(agentRun == null, ErrorCode.NOT_FOUND_ERROR, "AgentRun 不存在");
        AgentRun update = AgentRun.builder()
                .id(id)
                .status("completed")
                .workspacePath(workspacePath)
                .latencyMs(latencyMs)
                .loopStateJson("")
                .inputTokens(inputTokens != null ? inputTokens : 0)
                .outputTokens(outputTokens != null ? outputTokens : 0)
                .cacheReadTokens(cacheReadTokens != null ? cacheReadTokens : 0)
                .cacheCreationTokens(cacheCreationTokens != null ? cacheCreationTokens : 0)
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

    @Override
    public TokenUsageStatsVO getTokenUsageStats(Long userId, int days) {
        TokenUsageStatsVO statsVO = new TokenUsageStatsVO();

        Map<String, Object> statsMap = mapper.selectTokenStatsByUserId(userId, days);
        if (statsMap != null) {
            long totalInputTokens = toLong(statsMap.get("totalInputTokens"));
            long totalOutputTokens = toLong(statsMap.get("totalOutputTokens"));
            long totalCacheReadTokens = toLong(statsMap.get("totalCacheReadTokens"));
            long totalCacheCreationTokens = toLong(statsMap.get("totalCacheCreationTokens"));

            statsVO.setTotalInputTokens(totalInputTokens);
            statsVO.setTotalOutputTokens(totalOutputTokens);
            statsVO.setTotalCacheReadTokens(totalCacheReadTokens);
            statsVO.setTotalCacheCreationTokens(totalCacheCreationTokens);
            statsVO.setTotalRuns(toLong(statsMap.get("totalRuns")));
            statsVO.setAvgLatencyMs(toDouble(statsMap.get("avgLatencyMs")));

            // 缓存命中率 = cacheReadTokens / (inputTokens + cacheReadTokens)
            long totalInput = totalInputTokens + totalCacheReadTokens;
            if (totalInput > 0) {
                statsVO.setCacheHitRate(Math.round(totalCacheReadTokens * 10000.0 / totalInput) / 100.0);
            } else {
                statsVO.setCacheHitRate(0.0);
            }
        } else {
            statsVO.setTotalInputTokens(0L);
            statsVO.setTotalOutputTokens(0L);
            statsVO.setTotalCacheReadTokens(0L);
            statsVO.setTotalCacheCreationTokens(0L);
            statsVO.setTotalRuns(0L);
            statsVO.setAvgLatencyMs(0.0);
            statsVO.setCacheHitRate(0.0);
        }

        List<DailyTokenUsageVO> dailyUsage = mapper.selectDailyTokenUsageByUserId(userId, days);
        statsVO.setDailyTokenUsage(dailyUsage != null ? dailyUsage : new ArrayList<>());

        return statsVO;
    }

    private Long toLong(Object value) {
        if (value == null) return 0L;
        if (value instanceof BigDecimal) return ((BigDecimal) value).longValue();
        if (value instanceof Number) return ((Number) value).longValue();
        return Long.parseLong(value.toString());
    }

    private Double toDouble(Object value) {
        if (value == null) return 0.0;
        if (value instanceof BigDecimal) return ((BigDecimal) value).doubleValue();
        if (value instanceof Number) return ((Number) value).doubleValue();
        return Double.parseDouble(value.toString());
    }
}
