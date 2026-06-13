package com.adcage.acaicodefree.legacy.workflow.state;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.model.QualityResult;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.StateGraph;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.bsc.langgraph4j.StateGraph.END;
import static org.bsc.langgraph4j.StateGraph.START;
import static org.bsc.langgraph4j.action.AsyncNodeAction.node_async;
import static org.junit.jupiter.api.Assertions.*;

class WorkflowContextTest {

    @Test
    void testWorkflowContextCreation() {
        var ctx = WorkflowContext.builder()
                .appId(1L)
                .originalPrompt("test prompt")
                .build();

        assertEquals(1L, ctx.getAppId());
        assertEquals("test prompt", ctx.getOriginalPrompt());
        assertNotNull(ctx.getImageList());
        assertTrue(ctx.getImageList().isEmpty());
    }

    @Test
    void testWorkflowContextAdvanceStep() {
        var ctx = new WorkflowContext();
        ctx.advanceStep("image_collect");
        assertEquals("image_collect", ctx.getCurrentStep());

        ctx.advanceStep("prompt_enhancer");
        assertEquals("prompt_enhancer", ctx.getCurrentStep());
    }

    @Test
    void testWorkflowContextAddError() {
        var ctx = new WorkflowContext();
        ctx.advanceStep("code_generator");
        ctx.addError("generation failed");
        assertEquals("generation failed", ctx.getErrorMessage());
        assertEquals("code_generator", ctx.getCurrentStep());
    }

    @Test
    void testQualityResultFactoryMethods() {
        var valid = QualityResult.valid();
        assertTrue(valid.getIsValid());
        assertTrue(valid.getErrors().isEmpty());

        var invalid = QualityResult.invalid(List.of("missing index.html"));
        assertFalse(invalid.getIsValid());
        assertEquals(1, invalid.getErrors().size());
    }

    @Test
    void testImageResourceCreation() {
        var img = ImageResource.builder()
                .category(ImageCategoryEnum.CONTENT)
                .description("a beautiful landscape")
                .url("https://example.com/img.jpg")
                .build();

        assertEquals(ImageCategoryEnum.CONTENT, img.getCategory());
        assertEquals("a beautiful landscape", img.getDescription());
    }

    @Test
    void testWorkflowContextInAgentState() throws Exception {
        var schema = WorkflowContext.schema();

        var graph = new StateGraph<>(schema, AgentState::new)
                .addNode("init", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.setAppId(42L);
                    ctx.setOriginalPrompt("build a website");
                    ctx.advanceStep("init");
                    return ctx.toStateUpdate();
                }))
                .addNode("enrich", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.setEnhancedPrompt("build a modern responsive website with images");
                    ctx.advanceStep("enrich");
                    return ctx.toStateUpdate();
                }))
                .addEdge(START, "init")
                .addEdge("init", "enrich")
                .addEdge("enrich", END);

        CompiledGraph<AgentState> workflow = graph.compile();

        var result = workflow.invoke(Map.of());
        assertTrue(result.isPresent());

        AgentState finalState = result.get();
        var ctx = WorkflowContext.fromState(finalState);

        assertEquals(42L, ctx.getAppId());
        assertEquals("build a website", ctx.getOriginalPrompt());
        assertEquals("build a modern responsive website with images", ctx.getEnhancedPrompt());
        assertEquals("enrich", ctx.getCurrentStep());
    }

    @Test
    void testWorkflowContextStateSurvivesMultipleNodes() throws Exception {
        var schema = WorkflowContext.schema();

        var graph = new StateGraph<>(schema, AgentState::new)
                .addNode("node_a", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.setAppId(100L);
                    ctx.setOriginalPrompt("original");
                    ctx.setImageListStr("image1, image2");
                    ctx.advanceStep("node_a");
                    return ctx.toStateUpdate();
                }))
                .addNode("node_b", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    assertEquals(100L, ctx.getAppId());
                    assertEquals("original", ctx.getOriginalPrompt());
                    assertEquals("image1, image2", ctx.getImageListStr());
                    ctx.setEnhancedPrompt("enhanced: " + ctx.getOriginalPrompt());
                    ctx.setGenerationType(CodeGenTypeEnum.SINGLE_FILE);
                    ctx.advanceStep("node_b");
                    return ctx.toStateUpdate();
                }))
                .addNode("node_c", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.setGeneratedCodeDir("/tmp/generated/100");
                    ctx.setQualityResult(QualityResult.valid());
                    ctx.advanceStep("node_c");
                    return ctx.toStateUpdate();
                }))
                .addEdge(START, "node_a")
                .addEdge("node_a", "node_b")
                .addEdge("node_b", "node_c")
                .addEdge("node_c", END);

        CompiledGraph<AgentState> workflow = graph.compile();
        var result = workflow.invoke(Map.of());
        assertTrue(result.isPresent());

        var ctx = WorkflowContext.fromState(result.get());
        assertEquals(100L, ctx.getAppId());
        assertEquals("enhanced: original", ctx.getEnhancedPrompt());
        assertEquals(CodeGenTypeEnum.SINGLE_FILE, ctx.getGenerationType());
        assertEquals("/tmp/generated/100", ctx.getGeneratedCodeDir());
        assertTrue(ctx.getQualityResult().getIsValid());
        assertEquals("node_c", ctx.getCurrentStep());
    }

    @Test
    void testWorkflowContextWithImageList() throws Exception {
        var schema = WorkflowContext.schema();

        var graph = new StateGraph<>(schema, AgentState::new)
                .addNode("collect_images", node_async(state -> {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.setImageList(List.of(
                            ImageResource.builder().category(ImageCategoryEnum.CONTENT).description("hero").url("u1").build(),
                            ImageResource.builder().category(ImageCategoryEnum.LOGO).description("logo").url("u2").build()
                    ));
                    ctx.advanceStep("collect_images");
                    return ctx.toStateUpdate();
                }))
                .addEdge(START, "collect_images")
                .addEdge("collect_images", END);

        CompiledGraph<AgentState> workflow = graph.compile();
        var result = workflow.invoke(Map.of());
        assertTrue(result.isPresent());

        var ctx = WorkflowContext.fromState(result.get());
        assertEquals(2, ctx.getImageList().size());
        assertEquals(ImageCategoryEnum.CONTENT, ctx.getImageList().get(0).getCategory());
        assertEquals(ImageCategoryEnum.LOGO, ctx.getImageList().get(1).getCategory());
    }
}
