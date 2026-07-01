package com.adcage.acaicodefree.model.vo.chat;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 工具信息 VO（Playground 勾选用）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ToolInfoVO implements Serializable {

    /**
     * 工具名（如 "Read", "Write", "Bash"）
     */
    private String name;

    /**
     * 显示名（如 "读取文件", "写入文件", "执行命令"）
     */
    private String displayName;

    /**
     * 工具功能简述
     */
    private String description;

    /**
     * 分类：file / search / system / interaction / knowledge
     */
    private String category;

    /**
     * 是否默认启用
     */
    private boolean defaultEnabled;

    private static final long serialVersionUID = 1L;
}
