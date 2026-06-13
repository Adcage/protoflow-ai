package com.adcage.acaicodefree.legacy.workflow.node;

import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.legacy.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import reactor.core.publisher.Flux;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CodeGeneratorNodeTest {

    @TempDir
    Path tempDir;

    @Test
    void applyShouldCallFacadeAndWriteGeneratedDirectory() throws Exception {
        Path generatedDir = Files.createDirectories(tempDir.resolve("app-1"));
        AiCodeGeneratorFacade facade = new StubAiCodeGeneratorFacade(generatedDir.toFile());
        CodeGeneratorNode node = new CodeGeneratorNode(facade);
        WorkflowContext context = WorkflowContext.builder()
                .appId(1L)
                .enhancedPrompt("增强提示词")
                .generationType(CodeGenTypeEnum.MULTI_FILE)
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("code_generator", updated.getCurrentStep());
        assertEquals(AppConstant.getMultiFileOutputDir(1L).toString(), updated.getGeneratedCodeDir());
        assertEquals(CodeGenTypeEnum.MULTI_FILE, ((StubAiCodeGeneratorFacade) facade).lastType);
        assertEquals("增强提示词", ((StubAiCodeGeneratorFacade) facade).lastPrompt);
    }

    @Test
    void applyWhenGenerationTypeMissingShouldDefaultToMultiFile() throws Exception {
        Path generatedDir = Files.createDirectories(tempDir.resolve("app-2"));
        StubAiCodeGeneratorFacade facade = new StubAiCodeGeneratorFacade(generatedDir.toFile());
        CodeGeneratorNode node = new CodeGeneratorNode(facade);
        WorkflowContext context = WorkflowContext.builder()
                .appId(2L)
                .enhancedPrompt("增强提示词")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals(CodeGenTypeEnum.MULTI_FILE, facade.lastType);
        assertEquals(CodeGenTypeEnum.MULTI_FILE, updated.getGenerationType());
    }

    private static final class StubAiCodeGeneratorFacade extends AiCodeGeneratorFacade {
        private final File file;
        private String lastPrompt;
        private CodeGenTypeEnum lastType;

        private StubAiCodeGeneratorFacade(File file) {
            this.file = file;
        }

        @Override
        public Flux<String> generateAndSaveCodeStream(String userMessage, CodeGenTypeEnum codeGenType, Long appId) {
            this.lastPrompt = userMessage;
            this.lastType = codeGenType;
            return Flux.just(file.toString());
        }
    }
}
