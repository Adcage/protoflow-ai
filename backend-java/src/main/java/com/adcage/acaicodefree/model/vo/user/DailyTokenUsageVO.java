package com.adcage.acaicodefree.model.vo.user;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
public class DailyTokenUsageVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private String date;
    private Long inputTokens;
    private Long outputTokens;
    private Long cacheReadTokens;
    private Long cacheCreationTokens;
    private Long runs;
}
