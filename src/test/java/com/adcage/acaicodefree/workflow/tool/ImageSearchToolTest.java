package com.adcage.acaicodefree.workflow.tool;

import com.adcage.acaicodefree.workflow.model.ImageCategoryEnum;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class ImageSearchToolTest {

    @Test
    void searchWhenKeywordBlankShouldReturnEmptyList() {
        ImageSearchTool tool = new ImageSearchTool("api-key", 5, keyword -> "{}");

        assertTrue(tool.search("   ").isEmpty());
    }

    @Test
    void searchWhenApiKeyMissingShouldReturnEmptyList() {
        ImageSearchTool tool = new ImageSearchTool("", 5, keyword -> {
            fail("missing api key should not call http requester");
            return "{}";
        });

        assertTrue(tool.search("saas website").isEmpty());
    }

    @Test
    void searchShouldParsePexelsResponse() {
        String response = """
                {
                  \"photos\": [
                    {
                      \"alt\": \"hero image\",
                      \"src\": {
                        \"large\": \"https://images.example.com/hero.jpg\"
                      }
                    },
                    {
                      \"alt\": \"team photo\",
                      \"src\": {
                        \"large\": \"https://images.example.com/team.jpg\"
                      }
                    }
                  ]
                }
                """;
        ImageSearchTool tool = new ImageSearchTool("api-key", 5, keyword -> response);

        var result = tool.search("enterprise website");

        assertEquals(2, result.size());
        assertEquals(ImageCategoryEnum.CONTENT, result.get(0).getCategory());
        assertEquals("hero image", result.get(0).getDescription());
        assertEquals("https://images.example.com/hero.jpg", result.get(0).getUrl());
    }

    @Test
    void searchWhenRequesterThrowsShouldReturnEmptyList() {
        ImageSearchTool tool = new ImageSearchTool("api-key", 5, keyword -> {
            throw new RuntimeException("network error");
        });

        List<?> result = tool.search("landing page");

        assertTrue(result.isEmpty());
    }
}
