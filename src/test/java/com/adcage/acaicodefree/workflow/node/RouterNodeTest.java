package com.adcage.acaicodefree.workflow.node;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class RouterNodeTest {

    @Test
    void applyShouldRouteEnterpriseSiteToMultiFile() {
        RouterNode node = new RouterNode();
        WorkflowContext context = WorkflowContext.builder()
                .enhancedPrompt("请生成一个企业官网，包含首页、关于我们、产品介绍和联系方式")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("router", updated.getCurrentStep());
        assertEquals(CodeGenTypeEnum.MULTI_FILE, updated.getGenerationType());
    }

    @Test
    void applyShouldRouteSimplePageToSingleFile() {
        RouterNode node = new RouterNode();
        WorkflowContext context = WorkflowContext.builder()
                .enhancedPrompt("请生成一个个人介绍单页，突出头像、技能和联系方式")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals(CodeGenTypeEnum.SINGLE_FILE, updated.getGenerationType());
    }
}
