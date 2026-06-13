package com.adcage.acaicodefree.legacy.workflow.node;

import com.adcage.acaicodefree.legacy.workflow.ai.ImageCollectionService;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class ImageCollectorNodeTest {

    @Test
    void applyShouldWriteStructuredImagesAndSummary() {
        ImageCollectionService imageCollectionService = prompt -> List.of(
                ImageResource.builder()
                        .category(ImageCategoryEnum.CONTENT)
                        .description("企业官网 hero 图")
                        .url("https://img.example.com/hero.jpg")
                        .build(),
                ImageResource.builder()
                        .category(ImageCategoryEnum.LOGO)
                        .description("企业品牌 logo")
                        .url("https://img.example.com/logo.png")
                        .build()
        );
        ImageCollectorNode node = new ImageCollectorNode(imageCollectionService, 5);
        WorkflowContext context = WorkflowContext.builder()
                .appId(1L)
                .originalPrompt("帮我做一个企业官网")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("image_collect", updated.getCurrentStep());
        assertEquals(2, updated.getImageList().size());
        assertTrue(updated.getImageListStr().contains("企业官网 hero 图"));
        assertTrue(updated.getImageListStr().contains("企业品牌 logo"));
    }

    @Test
    void applyWhenServiceFailsShouldDegradeToEmptyImages() {
        ImageCollectionService imageCollectionService = prompt -> {
            throw new RuntimeException("tool chain failed");
        };
        ImageCollectorNode node = new ImageCollectorNode(imageCollectionService, 5);
        WorkflowContext context = WorkflowContext.builder()
                .appId(2L)
                .originalPrompt("帮我做一个作品集页面")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertEquals("image_collect", updated.getCurrentStep());
        assertNotNull(updated.getImageList());
        assertTrue(updated.getImageList().isEmpty());
        assertEquals("", updated.getImageListStr());
    }

    @Test
    void applyShouldLimitSummaryLengthByConfiguredImageCount() {
        ImageCollectionService imageCollectionService = prompt -> List.of(
                image("图1"), image("图2"), image("图3")
        );
        ImageCollectorNode node = new ImageCollectorNode(imageCollectionService, 2);
        WorkflowContext context = WorkflowContext.builder()
                .appId(3L)
                .originalPrompt("帮我做一个产品页")
                .build();

        Map<String, Object> result = node.apply(new AgentState(context.toStateUpdate()));
        WorkflowContext updated = (WorkflowContext) result.get(WorkflowContext.STATE_KEY);

        assertTrue(updated.getImageListStr().contains("图1"));
        assertTrue(updated.getImageListStr().contains("图2"));
        assertFalse(updated.getImageListStr().contains("图3"));
    }

    private ImageResource image(String description) {
        return ImageResource.builder()
                .category(ImageCategoryEnum.CONTENT)
                .description(description)
                .url("https://img.example.com/" + description + ".jpg")
                .build();
    }
}
