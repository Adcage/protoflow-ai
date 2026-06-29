package com.adcage.acaicodefree.model.vo.user;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
public class TokenUsageStatsVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long totalInputTokens;
    private Long totalOutputTokens;
    private Long totalCacheReadTokens;
    private Long totalCacheCreationTokens;
    private Long totalRuns;
    private Double avgLatencyMs;
    private Double cacheHitRate;
    private List<DailyTokenUsageVO> dailyTokenUsage;
}
