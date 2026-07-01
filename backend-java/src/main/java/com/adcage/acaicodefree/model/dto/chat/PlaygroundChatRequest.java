package com.adcage.acaicodefree.model.dto.chat;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * Playground 对话请求
 */
@Data
public class PlaygroundChatRequest implements Serializable {

    /**
     * 用户消息
     */
    private String message;

    /**
     * 启用的工具名列表（如 ["Read", "Write", "Bash"]）
     */
    private List<String> enabledTools;

    private static final long serialVersionUID = 1L;
}
