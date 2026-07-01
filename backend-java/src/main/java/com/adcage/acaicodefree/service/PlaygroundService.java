package com.adcage.acaicodefree.service;

import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.chat.ToolInfoVO;
import reactor.core.publisher.Flux;

import java.util.List;

/**
 * Playground 服务层
 */
public interface PlaygroundService {

    /**
     * Playground 流式对话
     *
     * @param message      用户消息
     * @param enabledTools 启用的工具名列表
     * @param loginUser    当前登录用户
     * @return SSE 流
     */
    Flux<String> playgroundChat(String message, List<String> enabledTools, User loginUser);

    /**
     * 获取可用的工具列表
     *
     * @return 工具信息列表
     */
    List<ToolInfoVO> listAvailableTools();

    /**
     * 重置 Playground（为当前管理员创建新 Session）
     *
     * @param loginUser 当前登录用户
     * @return 新 Session ID
     */
    Long resetPlayground(User loginUser);
}
