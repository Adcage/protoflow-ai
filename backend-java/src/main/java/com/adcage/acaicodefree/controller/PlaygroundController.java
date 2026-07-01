package com.adcage.acaicodefree.controller;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.annotation.AuthCheck;
import com.adcage.acaicodefree.common.BaseResponse;
import com.adcage.acaicodefree.common.ResultUtils;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.model.dto.chat.PlaygroundChatRequest;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.chat.ToolInfoVO;
import com.adcage.acaicodefree.service.PlaygroundService;
import com.adcage.acaicodefree.service.UserService;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

/**
 * Playground 控制器（管理员专用 AI 工具能力测试）
 */
@RestController
@RequestMapping("/playground")
@Slf4j
public class PlaygroundController {

    @Resource
    private PlaygroundService playgroundService;

    @Resource
    private UserService userService;

    /**
     * Playground 流式对话（SSE）
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public Flux<ServerSentEvent<String>> playgroundChat(
            @RequestBody PlaygroundChatRequest request,
            HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        String message = request.getMessage();
        List<String> enabledTools = request.getEnabledTools();

        log.info("[Playground] chat request | userId={}, messageLen={}, enabledTools={}",
                loginUser.getId(), message != null ? message.length() : 0, enabledTools);

        Flux<String> stringFlux = playgroundService.playgroundChat(message, enabledTools, loginUser);

        // meta 事件
        ServerSentEvent<String> metaEvent = ServerSentEvent.<String>builder()
                .event("meta")
                .data("{\"mode\":\"playground\"}")
                .build();

        // done 事件
        ServerSentEvent<String> doneEvent = ServerSentEvent.<String>builder()
                .event("done")
                .data("")
                .build();

        return Flux.just(metaEvent)
                .concatWith(stringFlux.map(chunk -> {
                    Map<String, String> data = Map.of("d", chunk);
                    String jsonData = JSONUtil.toJsonStr(data);
                    return ServerSentEvent.<String>builder()
                            .data(jsonData)
                            .build();
                }))
                .concatWith(Mono.just(doneEvent))
                .onErrorResume(error -> {
                    log.error("[Playground] SSE error, userId={}", loginUser.getId(), error);
                    Map<String, Object> errorData = Map.of(
                            "code", 50000,
                            "message", "生成失败：" + error.getMessage()
                    );
                    ServerSentEvent<String> errorEvent = ServerSentEvent.<String>builder()
                            .event("business-error")
                            .data(JSONUtil.toJsonStr(errorData))
                            .build();
                    return Flux.just(errorEvent);
                });
    }

    /**
     * 获取可用的工具列表
     */
    @GetMapping("/tools")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<List<ToolInfoVO>> listAvailableTools() {
        return ResultUtils.success(playgroundService.listAvailableTools());
    }

    /**
     * 重置 Playground（新建对话 Session）
     */
    @PostMapping("/reset")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Long> resetPlayground(HttpServletRequest httpRequest) {
        User loginUser = userService.getLoginUser(httpRequest);
        Long newSessionId = playgroundService.resetPlayground(loginUser);
        return ResultUtils.success(newSessionId);
    }
}
