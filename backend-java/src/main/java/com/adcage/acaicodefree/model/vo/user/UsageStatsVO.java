package com.adcage.acaicodefree.model.vo.user;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
public class UsageStatsVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long totalInputTokens;
    private Long totalOutputTokens;
    private Long totalMessages;
    private Integer totalApps;
    private Integer totalSessions;
    private Double avgLatencyMs;
    private List<DailyUsageVO> recentDailyUsage;
}
