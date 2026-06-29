package com.adcage.acaicodefree.model.vo.app;

import com.adcage.acaicodefree.model.vo.user.UserVO;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class MarketplaceAppVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Long id;
    private String appName;
    private String cover;
    private String initPrompt;
    private String codeGenType;
    private Integer forkCount;
    private List<String> categories;
    private UserVO user;
    private LocalDateTime createTime;
}
