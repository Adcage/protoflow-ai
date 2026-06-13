package com.adcage.acaicodefree.mapper;

import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.vo.user.DailyUsageVO;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;
import java.util.Map;

public interface ChatHistoryMapper extends BaseMapper<ChatHistory> {

    @Select("SELECT COALESCE(SUM(inputTokens), 0) AS totalInputTokens, " +
            "COALESCE(SUM(outputTokens), 0) AS totalOutputTokens, " +
            "COUNT(*) AS totalMessages, " +
            "COALESCE(AVG(latencyMs), 0) AS avgLatencyMs " +
            "FROM chat_history WHERE userId = #{userId} AND isDelete = 0")
    Map<String, Object> selectUsageStatsByUserId(@Param("userId") Long userId);

    @Select("SELECT DATE(createTime) AS date, " +
            "COALESCE(SUM(inputTokens), 0) AS inputTokens, " +
            "COALESCE(SUM(outputTokens), 0) AS outputTokens, " +
            "COUNT(*) AS messages " +
            "FROM chat_history WHERE userId = #{userId} AND isDelete = 0 " +
            "AND createTime >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) " +
            "GROUP BY DATE(createTime) ORDER BY date")
    List<DailyUsageVO> selectDailyUsageByUserId(@Param("userId") Long userId);
}
