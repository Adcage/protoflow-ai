package com.adcage.acaicodefree.legacy.workflow.node;

import com.adcage.acaicodefree.legacy.workflow.ai.PromptEnhancerService;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class PromptEnhancerNodeTest {

    @Test
    void applyShouldUseServiceOutput() {
        PromptEnhancerService promptEnhancerService = (prompt, imageSummary) ->
                "增强后提示词: " + prompt + " | 图片摘要: " + imageSummary;
        PromptEnhancerNode node = new PromptEnhancerNode(promptEnhancerService);
        WorkflowContext context = WorkflowContext.builder()
                .originalPrompt("做一个企业官网")
                .imageListStr("[CONTENT] hero 图; [LOGO] 品牌 logo")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("prompt_enhancer", updated.getCurrentStep());
        assertTrue(updated.getEnhancedPrompt().contains("做一个企业官网"));
        assertTrue(updated.getEnhancedPrompt().contains("品牌 logo"));
    }

    @Test
    void applyWhenServiceFailsShouldFallbackToComposedPrompt() {
        PromptEnhancerService promptEnhancerService = (prompt, imageSummary) -> {
            throw new RuntimeException("llm error");
        };
        PromptEnhancerNode node = new PromptEnhancerNode(promptEnhancerService);
        WorkflowContext context = WorkflowContext.builder()
                .originalPrompt("做一个产品页")
                .imageListStr("[CONTENT] 产品展示图")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("prompt_enhancer", updated.getCurrentStep());
        assertTrue(updated.getEnhancedPrompt().contains("做一个产品页"));
        assertTrue(updated.getEnhancedPrompt().contains("产品展示图"));
    }
}
