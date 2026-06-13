package com.adcage.acaicodefree.workflow.service;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.workflow.ai.ImageCollectionPlanServiceFactory;
import com.adcage.acaicodefree.workflow.ai.ImageCollectionServiceFactory;
import com.adcage.acaicodefree.workflow.ai.PromptEnhancerServiceFactory;
import com.adcage.acaicodefree.workflow.config.WorkflowProperties;
import com.adcage.acaicodefree.workflow.node.CodeGeneratorNode;
import com.adcage.acaicodefree.workflow.node.CodeQualityCheckNode;
import com.adcage.acaicodefree.workflow.node.ImageCollectorNode;
import com.adcage.acaicodefree.workflow.node.ProjectBuilderNode;
import com.adcage.acaicodefree.workflow.node.PromptEnhancerNode;
import com.adcage.acaicodefree.workflow.node.RouterNode;
import com.adcage.acaicodefree.workflow.node.concurrent.ContentImageCollectorNode;
import com.adcage.acaicodefree.workflow.node.concurrent.DiagramCollectorNode;
import com.adcage.acaicodefree.workflow.node.concurrent.ImageAggregatorNode;
import com.adcage.acaicodefree.workflow.node.concurrent.ImagePlanNode;
import com.adcage.acaicodefree.workflow.node.concurrent.IllustrationCollectorNode;
import com.adcage.acaicodefree.workflow.node.concurrent.LogoCollectorNode;
import com.adcage.acaicodefree.workflow.state.WorkflowContext;
import com.adcage.acaicodefree.workflow.tool.ImageSearchTool;
import com.adcage.acaicodefree.workflow.tool.LogoGeneratorTool;
import com.adcage.acaicodefree.workflow.tool.MermaidDiagramTool;
import com.adcage.acaicodefree.workflow.tool.UndrawIllustrationTool;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.bsc.langgraph4j.state.AgentState;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.scheduler.Schedulers;

import java.util.Map;

@Slf4j
@Service
public class WorkflowCodeGeneratorService {

    @Resource
    private WorkflowProperties workflowProperties;

    @Resource
    private ImageCollectionServiceFactory imageCollectionServiceFactory;

    @Resource
    private PromptEnhancerServiceFactory promptEnhancerServiceFactory;

    @Resource
    private ImageCollectionPlanServiceFactory imageCollectionPlanServiceFactory;

    @Resource
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    @Resource
    private ImageSearchTool imageSearchTool;

    @Resource
    private UndrawIllustrationTool undrawIllustrationTool;

    @Resource
    private MermaidDiagramTool mermaidDiagramTool;

    @Resource
    private LogoGeneratorTool logoGeneratorTool;

    public WorkflowContext executeWorkflow(Long appId, String message) throws Exception {
        if (workflowProperties.isEnableParallelImageCollect()) {
            return buildConcurrentWorkflow().execute(appId, message);
        }
        CodeGenWorkflow workflow = new CodeGenWorkflow(
                new ImageCollectorNode(imageCollectionServiceFactory.createService(), workflowProperties.getImageSummaryLimit()),
                new PromptEnhancerNode(promptEnhancerServiceFactory.createService()),
                new RouterNode(),
                new CodeGeneratorNode(aiCodeGeneratorFacade),
                new CodeQualityCheckNode(),
                new ProjectBuilderNode()
        );
        return workflow.execute(appId, message);
    }

    public Flux<String> executeWorkflowWithFlux(Long appId, String message) {
        return executeWorkflowEventFlux(appId, message)
                .map(event -> {
                    if ("message".equals(event.event())) {
                        return event.data();
                    }
                    JSONObject json = new JSONObject();
                    json.set("type", "workflow_event");
                    json.set("event", event.event());
                    json.set("data", JSONUtil.parseObj(event.data()));
                    return json.toString();
                });
    }

    public Flux<WorkflowStreamEvent> executeWorkflowEventFlux(Long appId, String message) {
        return Flux.create(sink -> {
            Schedulers.boundedElastic().schedule(() -> {
                sink.next(new WorkflowStreamEvent("workflow_start", "{\"step\":\"start\",\"appId\":" + appId + "}"));
                try {
                    WorkflowContext context = executeWorkflowWithEvents(appId, message, event -> {
                        if (!sink.isCancelled()) {
                            sink.next(event);
                        }
                    });
                    String codeGenType = context.getGenerationType() == null ? "" : context.getGenerationType().getValue();
                    sink.next(new WorkflowStreamEvent("workflow_completed", "{\"step\":\"done\",\"codeGenType\":\""
                            + codeGenType + "\",\"generatedCodeDir\":\""
                            + context.getGeneratedCodeDir().replace("\\", "\\\\") + "\"}"));
                    sink.complete();
                } catch (Exception e) {
                    log.error("[WorkflowCodeGeneratorService] workflow execution failed, appId={}", appId, e);
                    sink.next(new WorkflowStreamEvent("workflow_error", "{\"message\":\""
                            + (e.getMessage() == null ? "unknown" : e.getMessage().replace("\"", "'")) + "\"}"));
                    sink.complete();
                }
            });
        });
    }

    private WorkflowContext executeWorkflowWithEvents(Long appId,
                                                      String message,
                                                      java.util.function.Consumer<WorkflowStreamEvent> eventConsumer) {
        WorkflowContext context = WorkflowContext.builder()
                .appId(appId)
                .originalPrompt(message)
                .build();
        AgentState state = new AgentState(context.toStateUpdate());

        state = runStep(CodeGenWorkflow.NODE_IMAGE_COLLECT, state,
                new ImageCollectorNode(imageCollectionServiceFactory.createService(), workflowProperties.getImageSummaryLimit())::apply,
                eventConsumer);
        state = runStep(CodeGenWorkflow.NODE_PROMPT_ENHANCER, state,
                new PromptEnhancerNode(promptEnhancerServiceFactory.createService())::apply,
                eventConsumer);
        state = runStep(CodeGenWorkflow.NODE_ROUTER, state,
                new RouterNode()::apply,
                eventConsumer);
        state = runStep(CodeGenWorkflow.NODE_CODE_GENERATOR, state,
                new CodeGeneratorNode(aiCodeGeneratorFacade,
                        chunk -> eventConsumer.accept(new WorkflowStreamEvent("message", chunk)))::apply,
                eventConsumer);
        state = runStep(CodeGenWorkflow.NODE_CODE_QUALITY_CHECK, state,
                new CodeQualityCheckNode()::apply,
                eventConsumer);

        CodeQualityCheckNode qualityCheckNode = new CodeQualityCheckNode();
        String route = qualityCheckNode.routeAfterCheck(state);
        if (CodeQualityCheckNode.ROUTE_BUILD.equals(route)) {
            state = runStep(CodeGenWorkflow.NODE_PROJECT_BUILDER, state,
                    new ProjectBuilderNode()::apply,
                    eventConsumer);
        }
        return WorkflowContext.fromState(state);
    }

    private AgentState runStep(String step,
                               AgentState state,
                               java.util.function.Function<AgentState, Map<String, Object>> action,
                               java.util.function.Consumer<WorkflowStreamEvent> eventConsumer) {
        eventConsumer.accept(new WorkflowStreamEvent("step_started", "{\"step\":\"" + step + "\"}"));
        Map<String, Object> result = action.apply(state);
        AgentState updatedState = new AgentState(result);
        eventConsumer.accept(new WorkflowStreamEvent("step_completed", "{\"step\":\"" + step + "\"}"));
        return updatedState;
    }

    private CodeGenConcurrentWorkflow buildConcurrentWorkflow() {
        return new CodeGenConcurrentWorkflow(
                new ImagePlanNode(imageCollectionPlanServiceFactory.createService()),
                new ContentImageCollectorNode(query -> imageSearchTool.search(query)),
                new IllustrationCollectorNode(query -> undrawIllustrationTool.search(query, workflowProperties.getMaxImageCount())),
                new DiagramCollectorNode(query -> mermaidDiagramTool.renderArchitectureDiagram(query, query)),
                new LogoCollectorNode(query -> logoGeneratorTool.generateLogo(query)),
                new ImageAggregatorNode()
        );
    }
}
