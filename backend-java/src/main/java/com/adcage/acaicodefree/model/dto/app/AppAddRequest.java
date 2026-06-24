package com.adcage.acaicodefree.model.dto.app;

import lombok.Data;

import java.io.Serializable;

/**
 * 创建应用请求
 * 
 * @author adcage
 */
@Data
public class AppAddRequest implements Serializable {

    /**
     * 初始化提示词（必填）
     */
    private String initPrompt;

    /**
     * 代码生成模式
     */
    private String codeGenType;

    /**
     * 生成模式（application/presentation/prototype/diagram），默认 application
     */
    private String generationMode;

    /**
     * 格模板
     */
    private String styleTemplate;

    /**
     * 是否测试应用（管理员创建测试应用时为 true）
     */
    private Boolean isTestApp;

    private static final long serialVersionUID = 1L;
}
