package com.adcage.acaicodefree.model.vo.user;

import lombok.Data;

import java.io.Serial;
import java.io.Serializable;

@Data
public class DailyUsageVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private String date;
    private Long inputTokens;
    private Long outputTokens;
    private Long messages;
}
