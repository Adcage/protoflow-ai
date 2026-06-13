package com.adcage.acaicodefree.model.vo.app;

import com.adcage.acaicodefree.model.vo.user.UserVO;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 应用视图
 * 
 * @author adcage
 */
@Data
public class AppVO implements Serializable {

    /**
     * id
     */
    private Long id;

    /**
     * 应用名称
     */
    private String appName;

    /**
     * 应用封面
     */
    private String cover;

    /**
     * 初始化提示词
     */
    private String initPrompt;

    /**
     * 代码生成类型（枚举）
     */
    private String codeGenType;

    /**
     * 风格模板
     */
    private String styleTemplate;

    /**
     * 部署标识
     */
    private String deployKey;

    /**
     * 部署时间
     */
    private LocalDateTime deployedTime;

    /**
     * 优先级
     */
    private Integer priority;

    /**
     * 创建用户id
     */
    private Long userId;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    private LocalDateTime updateTime;

    /**
     * 创建用户信息
     */
    private UserVO user;

    /**
     * 封面任务状态（PENDING/RUNNING/SUCCESS/FAILED）
     */
    private String coverTaskStatus;

    /**
     * 封面任务重试次数
     */
    private Integer coverRetryCount;

    /**
     * 封面任务错误信息
     */
    private String coverErrorMessage;

    private static final long serialVersionUID = 1L;
}
