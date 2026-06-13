package com.adcage.acaicodefree.legacy.workflow.node;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class CodeQualityCheckNodeTest {

    @TempDir
    Path tempDir;

    @Test
    void applyShouldPassForSingleFileWhenHtmlExists() throws Exception {
        Path dir = Files.createDirectories(tempDir.resolve("single"));
        Files.writeString(dir.resolve("index.html"), "<html></html>");
        CodeQualityCheckNode node = new CodeQualityCheckNode();
        WorkflowContext context = WorkflowContext.builder()
                .generatedCodeDir(dir.toString())
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertTrue(updated.getQualityResult().getIsValid());
        assertEquals(CodeQualityCheckNode.ROUTE_SKIP_BUILD, node.routeAfterCheck(new AgentState(updated.toStateUpdate())));
    }

    @Test
    void applyShouldFailWhenDirectoryMissing() {
        CodeQualityCheckNode node = new CodeQualityCheckNode();
        WorkflowContext context = WorkflowContext.builder()
                .generatedCodeDir(tempDir.resolve("missing").toString())
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertFalse(updated.getQualityResult().getIsValid());
        assertFalse(updated.getQualityResult().getErrors().isEmpty());
        assertEquals(CodeQualityCheckNode.ROUTE_RETRY, node.routeAfterCheck(new AgentState(updated.toStateUpdate())));
    }

    @Test
    void applyShouldFailForMultiFileWhenCoreFilesMissing() throws Exception {
        Path dir = Files.createDirectories(tempDir.resolve("multi"));
        Files.writeString(dir.resolve("index.html"), "<html></html>");
        CodeQualityCheckNode node = new CodeQualityCheckNode();
        WorkflowContext context = WorkflowContext.builder()
                .generatedCodeDir(dir.toString())
                .generationType(CodeGenTypeEnum.MULTI_FILE)
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertFalse(updated.getQualityResult().getIsValid());
        assertTrue(updated.getQualityResult().getErrors().stream().anyMatch(error -> error.contains("style.css") || error.contains("script.js")));
    }
}
