package com.adcage.acaicodefree.workflow.service;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.workflow.model.QualityResult;
import com.adcage.acaicodefree.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphRepresentation;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class CodeGenWorkflowStructureTest {

    private CodeGenWorkflow codeGenWorkflow;

    @BeforeEach
    void setUp() {
        codeGenWorkflow = new CodeGenWorkflow();
    }

    @Test
    void testWorkflowCanCompile() throws Exception {
        CompiledGraph<AgentState> workflow = codeGenWorkflow.createWorkflow();
        assertNotNull(workflow, "Workflow should compile successfully");
    }

    @Test
    void testWorkflowMermaidDiagram() throws Exception {
        CompiledGraph<AgentState> workflow = codeGenWorkflow.createWorkflow();
        GraphRepresentation repr = workflow.getGraph(GraphRepresentation.Type.MERMAID);
        String mermaid = repr.content();
        assertNotNull(mermaid);
        assertFalse(mermaid.isBlank());
        System.out.println("=== CodeGenWorkflow Mermaid Diagram ===");
        System.out.println(mermaid);
        assertTrue(mermaid.contains("image_collect"), "Mermaid should contain image_collect node");
        assertTrue(mermaid.contains("prompt_enhancer"), "Mermaid should contain prompt_enhancer node");
        assertTrue(mermaid.contains("router"), "Mermaid should contain router node");
        assertTrue(mermaid.contains("code_generator"), "Mermaid should contain code_generator node");
        assertTrue(mermaid.contains("code_quality_check"), "Mermaid should contain code_quality_check node");
        assertTrue(mermaid.contains("project_builder"), "Mermaid should contain project_builder node");
    }

    @Test
    void testWorkflowExecutionSingleFile() throws Exception {
        WorkflowContext result = codeGenWorkflow.execute(1L, "做一个个人介绍网页");
        assertNotNull(result);
        assertEquals(1L, result.getAppId());
        assertEquals("做一个个人介绍网页", result.getOriginalPrompt());
        assertNotNull(result.getImageListStr());
        assertNotNull(result.getEnhancedPrompt());
        assertNotNull(result.getGenerationType());
        assertNotNull(result.getGeneratedCodeDir());
        assertNotNull(result.getQualityResult());
        assertTrue(result.getQualityResult().getIsValid());
    }

    @Test
    void testWorkflowExecutionMultiFile() throws Exception {
        WorkflowContext result = codeGenWorkflow.execute(2L, "做一个企业官网，包含首页和关于我们");
        assertNotNull(result);
        assertEquals(CodeGenTypeEnum.MULTI_FILE, result.getGenerationType());
    }

    @Test
    void testWorkflowStepsExecutedInOrder() throws Exception {
        WorkflowContext result = codeGenWorkflow.execute(3L, "做一个简单的页面");
        assertEquals("code_quality_check", result.getCurrentStep());
    }

    @Test
    void testWorkflowQualityCheckRoutesToSkipBuild() throws Exception {
        WorkflowContext result = codeGenWorkflow.execute(4L, "test");
        assertTrue(result.getQualityResult().getIsValid());
        assertNull(result.getBuildResultDir(), "Should skip build, so buildResultDir should be null");
    }
}
