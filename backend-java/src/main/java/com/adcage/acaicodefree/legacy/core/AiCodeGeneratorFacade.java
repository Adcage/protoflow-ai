package com.adcage.acaicodefree.legacy.core;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.legacy.ai.AiCodeGenServiceFactory;
import com.adcage.acaicodefree.legacy.ai.AiCodeGeneratorService;
import com.adcage.acaicodefree.legacy.ai.guardrail.PromptSafetyInputGuardrail;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.core.saver.CodeFileSaverExecutor;
import com.adcage.acaicodefree.core.VisualEditPromptHelper;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import dev.langchain4j.service.TokenStream;
import dev.langchain4j.service.tool.ToolExecution;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;

import java.io.File;

/**
 * AI代码生成门面类,组合代码生成和保存功能
 *
 * @deprecated Java AI 代码生成门面已禁用，代码生成核心必须通过 Python Agent Runtime。
 * @author adcage
 * @description AiCodeGeneratorFacade
 */
@Deprecated(since = "2026-06-13", forRemoval = false)
@Service
public class AiCodeGeneratorFacade {

    @Resource
    private AiCodeGenServiceFactory aiCodeGenServiceFactory;

    @Resource
    private PromptSafetyInputGuardrail promptSafetyInputGuardrail;

    /**
     * 统一入口,生成并保存代码
     *
     * @param userMessage
     * @param codeGenType
     * @return
     */
    public File generateAndSaveCode(String userMessage, CodeGenTypeEnum codeGenType,Long appId) {
        promptSafetyInputGuardrail.validate(userMessage);
        if (codeGenType == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "生成代码类型不能为空");
        }
        AiCodeGeneratorService aiCodeGeneratorService = aiCodeGenServiceFactory.getService(appId, codeGenType);
        Object result = switch (codeGenType) {
            case SINGLE_FILE -> aiCodeGeneratorService.generateSingleFileCode(userMessage);
            case MULTI_FILE -> aiCodeGeneratorService.generateMultiFileCode(userMessage);
            default -> {
                String message = "不支持的生成代码类型" + codeGenType.getValue();
                throw new BusinessException(ErrorCode.PARAMS_ERROR, message);
            }
        };
        return CodeFileSaverExecutor.executeSaver(result, codeGenType,appId);
    }

    /**
     * 统一入口,生成并保存代码(流式)
     *
     * @param userMessage
     * @param codeGenType
     * @return
     */
    public Flux<String> generateAndSaveCodeStream(String userMessage, CodeGenTypeEnum codeGenType,Long appId) {
        promptSafetyInputGuardrail.validate(userMessage);
        if (codeGenType == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "生成代码类型不能为空");
        }
        AiCodeGeneratorService aiCodeGeneratorService = aiCodeGenServiceFactory.getService(appId, codeGenType);
        boolean modifyRequest = VisualEditPromptHelper.isVisualEditRequest(userMessage);
        Flux<String> codeStream = switch (codeGenType) {
            case SINGLE_FILE -> buildSingleFileMessageStream(aiCodeGeneratorService, appId, userMessage, modifyRequest);
            case MULTI_FILE -> buildMultiFileMessageStream(aiCodeGeneratorService, appId, userMessage, modifyRequest);
            case VUE_PROJECT -> buildVueProjectMessageStream(aiCodeGeneratorService, appId, userMessage, modifyRequest);
            default -> {
                String message = "不支持的生成代码类型" + codeGenType.getValue();
                throw new BusinessException(ErrorCode.PARAMS_ERROR, message);
            }
        };
        if (codeGenType == CodeGenTypeEnum.VUE_PROJECT
                || codeGenType == CodeGenTypeEnum.MULTI_FILE
                || codeGenType == CodeGenTypeEnum.SINGLE_FILE) {
            return codeStream;
        }
        // 委托给 Executor 处理解析与保存逻辑
        return CodeFileSaverExecutor.executeSaverStream(codeStream, codeGenType,appId);
    }

    private Flux<String> buildSingleFileMessageStream(AiCodeGeneratorService service,
                                                      Long appId,
                                                      String userMessage,
                                                      boolean modifyRequest) {
        TokenStream tokenStream = modifyRequest
                ? service.modifySingleFileCodeStream(appId, userMessage)
                : service.generateSingleFileCodeStream(appId, userMessage);
        return Flux.create(sink -> {
            try {
                tokenStream
                        .onNext(token -> {
                            if (sink.isCancelled() || StrUtil.isBlank(token)) {
                                return;
                            }
                            sink.next(token);
                        })
                        .onToolExecuted(toolExecution -> handleToolExecution(sink, toolExecution))
                        .onError(sink::error)
                        .onComplete(response -> sink.complete())
                        .start();
            } catch (Exception e) {
                sink.error(e);
            }
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    private Flux<String> buildMultiFileMessageStream(AiCodeGeneratorService service,
                                                     Long appId,
                                                     String userMessage,
                                                     boolean modifyRequest) {
        TokenStream tokenStream = modifyRequest
                ? service.modifyMultiFileCodeStream(appId, userMessage)
                : service.generateMultiFileCodeStream(appId, userMessage);
        return Flux.create(sink -> {
            try {
                tokenStream
                        .onNext(token -> {
                            if (sink.isCancelled() || StrUtil.isBlank(token)) {
                                return;
                            }
                            sink.next(token);
                        })
                        .onToolExecuted(toolExecution -> handleToolExecution(sink, toolExecution))
                        .onError(sink::error)
                        .onComplete(response -> sink.complete())
                        .start();
            } catch (Exception e) {
                sink.error(e);
            }
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    private Flux<String> buildVueProjectMessageStream(AiCodeGeneratorService service,
                                                      Long appId,
                                                      String userMessage,
                                                      boolean modifyRequest) {
        TokenStream tokenStream = modifyRequest
                ? service.modifyVueProjectCodeStream(appId, userMessage)
                : service.generateVueProjectCodeStream(appId, userMessage);
        return Flux.create(sink -> {
            try {
                tokenStream
                        .onNext(token -> handleToken(sink, token))
                        .onToolExecuted(toolExecution -> handleToolExecution(sink, toolExecution))
                        .onError(sink::error)
                        .onComplete(response -> sink.complete())
                        .start();
            } catch (Exception e) {
                sink.error(e);
            }
        }, FluxSink.OverflowStrategy.BUFFER);
    }

    private void handleToken(FluxSink<String> sink, String token) {
        if (sink.isCancelled() || StrUtil.isBlank(token)) {
            return;
        }
        sink.next(JSONUtil.toJsonStr(new AiResponseMessage(token, "")));
    }

    private void handleToolExecution(FluxSink<String> sink, ToolExecution toolExecution) {
        if (sink.isCancelled() || toolExecution == null || toolExecution.request() == null) {
            return;
        }
        String id = toolExecution.request().id();
        String name = toolExecution.request().name();
        String arguments = toolExecution.request().arguments();
        sink.next(JSONUtil.toJsonStr(new ToolRequestMessage(id, name, arguments, "")));
        sink.next(JSONUtil.toJsonStr(new ToolExecutedMessage(id, name, arguments, toolExecution.result(), "")));
    }

}
