package com.adcage.acaicodefree.legacy.workflow.tool;

import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class UndrawIllustrationToolTest {

    @Test
    void searchWhenKeywordBlankShouldReturnEmptyList() {
        UndrawIllustrationTool tool = new UndrawIllustrationTool((keyword, limit) -> "");

        assertTrue(tool.search("", 3).isEmpty());
    }

    @Test
    void searchShouldParseIllustrationCards() {
        String html = """
                <html><body>
                  <img src=\"https://undraw.co/illustration_1.svg\" alt=\"Dashboard illustration\" />
                  <img src=\"https://undraw.co/illustration_2.svg\" alt=\"Team collaboration\" />
                </body></html>
                """;
        UndrawIllustrationTool tool = new UndrawIllustrationTool((keyword, limit) -> html);

        var result = tool.search("dashboard", 2);

        assertEquals(2, result.size());
        assertEquals(ImageCategoryEnum.ILLUSTRATION, result.get(0).getCategory());
        assertEquals("Dashboard illustration", result.get(0).getDescription());
        assertEquals("https://undraw.co/illustration_1.svg", result.get(0).getUrl());
    }

    @Test
    void searchWhenFetcherThrowsShouldReturnEmptyList() {
        UndrawIllustrationTool tool = new UndrawIllustrationTool((keyword, limit) -> {
            throw new RuntimeException("undraw unavailable");
        });

        assertTrue(tool.search("dashboard", 2).isEmpty());
    }
}
