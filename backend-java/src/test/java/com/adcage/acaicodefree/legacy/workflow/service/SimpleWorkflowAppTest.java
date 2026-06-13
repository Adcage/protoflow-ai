package com.adcage.acaicodefree.legacy.workflow.service;

import org.bsc.langgraph4j.CompiledGraph;
import org.bsc.langgraph4j.GraphRepresentation;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class SimpleWorkflowAppTest {

    @Test
    void testWorkflowCanCompileAndRun() throws Exception {
        var app = new SimpleWorkflowApp();
        CompiledGraph<AgentState> workflow = app.createWorkflow();
        assertNotNull(workflow, "Workflow should compile successfully");

        Map<String, Object> initialState = new LinkedHashMap<>();
        initialState.put("currentStep", "");
        initialState.put("message", "");

        var result = workflow.invoke(initialState);
        assertTrue(result.isPresent(), "Workflow should return a result");
        AgentState state = result.get();
        assertEquals("step_two", state.value("currentStep").orElse(""), "Final step should be step_two");
        assertEquals("Step two completed", state.value("message").orElse(""), "Final message should match");
    }

    @Test
    void testWorkflowMermaidOutput() throws Exception {
        var app = new SimpleWorkflowApp();
        CompiledGraph<AgentState> workflow = app.createWorkflow();

        GraphRepresentation repr = workflow.getGraph(GraphRepresentation.Type.MERMAID);
        assertNotNull(repr, "Graph representation should not be null");
        String mermaid = repr.content();
        assertNotNull(mermaid, "Mermaid output should not be null");
        assertFalse(mermaid.isBlank(), "Mermaid output should not be blank");
        System.out.println("=== LangGraph4j Mermaid Diagram ===");
        System.out.println(mermaid);
    }
}
