package com.adcage.acaicodefree.mapper;

import com.adcage.acaicodefree.model.entity.AgentRun;
import com.adcage.acaicodefree.model.vo.user.DailyTokenUsageVO;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

public interface AgentRunMapper extends BaseMapper<AgentRun> {

    @Select("SELECT * FROM agent_run " +
            "WHERE appId = #{appId} AND sessionId = #{sessionId} AND userId = #{userId} " +
            "AND status = 'waiting_for_user' AND isDelete = 0 " +
            "ORDER BY createTime DESC LIMIT 1 FOR UPDATE")
    AgentRun selectLatestWaitingForUpdate(
            @Param("appId") Long appId,
            @Param("sessionId") Long sessionId,
            @Param("userId") Long userId
    );

    @Select("SELECT DISTINCT appId FROM agent_run " +
            "WHERE createTime > DATE_SUB(NOW(), INTERVAL #{lookbackHours} HOUR) " +
            "AND status IN ('completed', 'failed') " +
            "AND isDelete = 0")
    List<Long> selectRecentActiveAppIds(@Param("lookbackHours") int lookbackHours);

    @Select("SELECT COALESCE(SUM(inputTokens), 0) AS totalInputTokens, " +
            "COALESCE(SUM(outputTokens), 0) AS totalOutputTokens, " +
            "COALESCE(SUM(cacheReadTokens), 0) AS totalCacheReadTokens, " +
            "COALESCE(SUM(cacheCreationTokens), 0) AS totalCacheCreationTokens, " +
            "COUNT(*) AS totalRuns, " +
            "COALESCE(AVG(latencyMs), 0) AS avgLatencyMs " +
            "FROM agent_run WHERE userId = #{userId} AND status = 'completed' " +
            "AND isDelete = 0 AND createTime >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY)")
    Map<String, Object> selectTokenStatsByUserId(@Param("userId") Long userId, @Param("days") int days);

    @Select("SELECT DATE(createTime) AS date, " +
            "COALESCE(SUM(inputTokens), 0) AS inputTokens, " +
            "COALESCE(SUM(outputTokens), 0) AS outputTokens, " +
            "COALESCE(SUM(cacheReadTokens), 0) AS cacheReadTokens, " +
            "COALESCE(SUM(cacheCreationTokens), 0) AS cacheCreationTokens, " +
            "COUNT(*) AS runs " +
            "FROM agent_run WHERE userId = #{userId} AND status = 'completed' " +
            "AND isDelete = 0 AND createTime >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY) " +
            "GROUP BY DATE(createTime) ORDER BY date")
    List<DailyTokenUsageVO> selectDailyTokenUsageByUserId(@Param("userId") Long userId, @Param("days") int days);
}
