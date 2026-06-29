package com.adcage.acaicodefree.model.vo.app;

import com.adcage.acaicodefree.model.vo.user.UserVO;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

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
     * 生成模式（application/presentation/prototype/diagram）
     */
    private String generationMode;

    /**
     * 产物格式（从 Manifest 读取，如 web_single_file/web_multi_file/vue_project）
     */
    private String artifactFormat;

    /**
     * 预览 URL（服务端根据 artifactFormat 计算）
     */
    private String previewUrl;

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
     * 是否测试应用
     */
    private Integer isTestApp;

    /**
     * 是否公开
     */
    private Integer isPublic;

    /**
     * Fork 数
     */
    private Integer forkCount;

    /**
     * Fork 来源应用 ID
     */
    private Long sourceAppId;

    /**
     * 分类列表（从 app_category 表关联）
     */
    private List<String> categories;

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
