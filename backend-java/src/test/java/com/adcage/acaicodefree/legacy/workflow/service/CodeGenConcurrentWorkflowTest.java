package com.adcage.acaicodefree.legacy.workflow.service;

import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCollectionPlan;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.ContentImageCollectorNode;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.DiagramCollectorNode;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.ImageAggregatorNode;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.ImagePlanNode;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.IllustrationCollectorNode;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.LogoCollectorNode;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphRepresentation;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class CodeGenConcurrentWorkflowTest {

    @Test
    void workflowShouldCompileAndContainConcurrentNodes() throws Exception {
        CodeGenConcurrentWorkflow workflow = new CodeGenConcurrentWorkflow(
                new ImagePlanNode(prompt -> ImageCollectionPlan.builder()
                        .contentQuery("hero")
                        .illustrationQuery("illustration")
                        .diagramQuery("diagram")
                        .logoPrompt("logo")
                        .build()),
                new ContentImageCollectorNode(query -> List.of(image(ImageCategoryEnum.CONTENT, "内容图"))),
                new IllustrationCollectorNode(query -> List.of(image(ImageCategoryEnum.ILLUSTRATION, "插画"))),
                new DiagramCollectorNode(query -> List.of(image(ImageCategoryEnum.ARCHITECTURE, "架构图"))),
                new LogoCollectorNode(query -> List.of(image(ImageCategoryEnum.LOGO, "Logo"))),
                new ImageAggregatorNode()
        );

        CompiledGraph<AgentState> compiledGraph = workflow.createWorkflow();
        GraphRepresentation graph = compiledGraph.getGraph(GraphRepresentation.Type.MERMAID);

        assertTrue(graph.content().contains("image_plan"));
        assertTrue(graph.content().contains("content_image_collector"));
        assertTrue(graph.content().contains("illustration_collector"));
        assertTrue(graph.content().contains("diagram_collector"));
        assertTrue(graph.content().contains("logo_collector"));
        assertTrue(graph.content().contains("image_aggregator"));
    }

    @Test
    void workflowShouldAggregateImagesFromAllBranches() throws Exception {
        CodeGenConcurrentWorkflow workflow = new CodeGenConcurrentWorkflow(
                new ImagePlanNode(prompt -> ImageCollectionPlan.builder()
                        .contentQuery("hero")
                        .illustrationQuery("illustration")
                        .diagramQuery("diagram")
                        .logoPrompt("logo")
                        .build()),
                new ContentImageCollectorNode(query -> List.of(image(ImageCategoryEnum.CONTENT, "内容图"))),
                new IllustrationCollectorNode(query -> List.of(image(ImageCategoryEnum.ILLUSTRATION, "插画"))),
                new DiagramCollectorNode(query -> List.of(image(ImageCategoryEnum.ARCHITECTURE, "架构图"))),
                new LogoCollectorNode(query -> List.of(image(ImageCategoryEnum.LOGO, "Logo"))),
                new ImageAggregatorNode()
        );

        WorkflowContext context = workflow.execute(1L, "做一个产品网站");

        assertEquals(4, context.getImageList().size());
        assertTrue(context.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.CONTENT));
        assertTrue(context.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.ILLUSTRATION));
        assertTrue(context.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.ARCHITECTURE));
        assertTrue(context.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.LOGO));
    }

    private ImageResource image(ImageCategoryEnum category, String description) {
        return ImageResource.builder().category(category).description(description).url("https://img.example.com/" + description).build();
    }
}
