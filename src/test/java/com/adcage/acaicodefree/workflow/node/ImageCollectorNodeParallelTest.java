package com.adcage.acaicodefree.workflow.node;

import com.adcage.acaicodefree.workflow.ai.ImageCollectionPlanService;
import com.adcage.acaicodefree.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.workflow.model.ImageCollectionPlan;
import com.adcage.acaicodefree.workflow.model.ImageResource;
import com.adcage.acaicodefree.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class ImageCollectorNodeParallelTest {

    @Test
    void applyWhenParallelEnabledShouldAggregateDifferentImageCategories() {
        ImageCollectionPlanService planService = prompt -> ImageCollectionPlan.builder()
                .contentQuery("saas hero")
                .illustrationQuery("dashboard illustration")
                .diagramQuery("microservice architecture")
                .logoPrompt("cloud brand")
                .build();
        ImageCollectorNode node = new ImageCollectorNode(
                planService,
                8,
                query -> List.of(image(ImageCategoryEnum.CONTENT, "内容图", "u1")),
                query -> List.of(image(ImageCategoryEnum.ILLUSTRATION, "插画", "u2")),
                query -> List.of(image(ImageCategoryEnum.ARCHITECTURE, "架构图", "u3")),
                query -> List.of(image(ImageCategoryEnum.LOGO, "Logo", "u4"))
        );
        WorkflowContext context = WorkflowContext.builder().appId(1L).originalPrompt("做一个产品网站").build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals(4, updated.getImageList().size());
        assertTrue(updated.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.CONTENT));
        assertTrue(updated.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.ILLUSTRATION));
        assertTrue(updated.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.ARCHITECTURE));
        assertTrue(updated.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.LOGO));
    }

    @Test
    void applyWhenOneParallelCollectorFailsShouldKeepOtherResults() {
        ImageCollectionPlanService planService = prompt -> ImageCollectionPlan.builder()
                .contentQuery("saas hero")
                .illustrationQuery("dashboard illustration")
                .diagramQuery("microservice architecture")
                .logoPrompt("cloud brand")
                .build();
        ImageCollectorNode node = new ImageCollectorNode(
                planService,
                8,
                query -> List.of(image(ImageCategoryEnum.CONTENT, "内容图", "u1")),
                query -> {
                    throw new RuntimeException("illustration failed");
                },
                query -> List.of(image(ImageCategoryEnum.ARCHITECTURE, "架构图", "u3")),
                query -> List.of(image(ImageCategoryEnum.LOGO, "Logo", "u4"))
        );
        WorkflowContext context = WorkflowContext.builder().appId(2L).originalPrompt("做一个产品网站").build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals(3, updated.getImageList().size());
        assertFalse(updated.getImageList().stream().anyMatch(item -> item.getCategory() == ImageCategoryEnum.ILLUSTRATION));
        assertTrue(updated.getImageListStr().contains("内容图"));
    }

    private ImageResource image(ImageCategoryEnum category, String description, String url) {
        return ImageResource.builder().category(category).description(description).url(url).build();
    }
}
