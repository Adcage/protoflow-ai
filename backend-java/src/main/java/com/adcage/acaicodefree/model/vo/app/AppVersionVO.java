package com.adcage.acaicodefree.model.vo.app;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class AppVersionVO implements Serializable {

    private Long id;

    private Long appId;

    private Integer versionNo;

    private String status;

    private LocalDateTime createTime;
}
