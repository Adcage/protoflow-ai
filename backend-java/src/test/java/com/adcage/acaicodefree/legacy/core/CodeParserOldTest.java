package com.adcage.acaicodefree.legacy.core;

import com.adcage.acaicodefree.legacy.ai.model.SingleCodeResult;
import com.adcage.acaicodefree.legacy.ai.model.MultiFileCodeResult;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.BusinessException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class CodeParserOldTest {

    @Test
    void testParseSingleCode_WithValidHtml() {
        String content = "```html\n<div>Test</div>\n```";
        SingleCodeResult result = CodeParserOld.parseSingleCode(content);
        assertNotNull(result);
        System.out.println(result.getHtmlCode());
        assertEquals("<div>Test</div>", result.getHtmlCode());
    }

    @Test
    void testParseSingleCode_WithCaseInsensitiveHtml() {
        String content = "```SINGLE_FILE\n<div>Test</div>\n```";
        SingleCodeResult result = CodeParserOld.parseSingleCode(content);
        assertNotNull(result);
        assertEquals("<div>Test</div>", result.getHtmlCode());
    }

    @Test
    void testParseSingleCode_WithNoHtml() {
        String content = "Some text without SINGLE_FILE code blocks";
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            CodeParserOld.parseSingleCode(content);
        });
        assertEquals(ErrorCode.NOT_FOUND_ERROR.getCode(), exception.getCode());
    }

    @Test
    void testParseSingleCode_WithEmptyHtml() {
        String content = "```html\n\n```";
        BusinessException exception = assertThrows(BusinessException.class, () -> {
            CodeParserOld.parseSingleCode(content);
        });
        assertEquals(ErrorCode.NOT_FOUND_ERROR.getCode(), exception.getCode());
    }

    @Test
    void testParseSingleCode_WithDoctypeFallback() {
        String content = "这是说明文字\n<!DOCTYPE html>\n<html><body>fallback</body></html>";
        SingleCodeResult result = CodeParserOld.parseSingleCode(content);
        assertNotNull(result);
        assertTrue(result.getHtmlCode().startsWith("<!DOCTYPE html>"));
    }

    @Test
    void testParseSingleCode_WithUnclosedFenceFallback() {
        String content = "```html\n<html><body>unclosed fence";
        SingleCodeResult result = CodeParserOld.parseSingleCode(content);
        assertNotNull(result);
        assertTrue(result.getHtmlCode().contains("<html>"));
    }

    @Test
    void testExtractMutiFileCode_WithAllCodeTypes() {
        String content = "```html\n<div>Test</div>\n```\n```css\nbody { color: red; }\n```\n```js\nconsole.log('test');\n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("<div>Test</div>", result.getHtmlCode());
        assertEquals("body { color: red; }", result.getCssCode());
        assertEquals("console.log('test');", result.getJsCode());
    }

    @Test
    void testExtractMutiFileCode_WithJavaScript() {
        String content = "```javascript\nconsole.log('test');\n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("console.log('test');", result.getJsCode());
    }

    @Test
    void testExtractMutiFileCode_WithEmptyContent() {
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode("");
        assertNull(result);
    }

    @Test
    void testExtractMutiFileCode_WithNullContent() {
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(null);
        assertNull(result);
    }

    @Test
    void testExtractMutiFileCode_WithPartialCode() {
        String content = "```html\n<div>Test</div>\n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("<div>Test</div>", result.getHtmlCode());
        assertNull(result.getCssCode());
        assertNull(result.getJsCode());
    }

    @Test
    void testExtractMutiFileCode_WithMultipleMatches() {
        String content = "```html\n<div>First</div>\n```\n```html\n<div>Second</div>\n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("<div>First</div>", result.getHtmlCode());
    }

    @Test
    void testExtractMutiFileCode_WithWhitespaceInCodeBlocks() {
        String content = "```html\n  <div>Test</div>  \n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("<div>Test</div>", result.getHtmlCode());
    }

    @Test
    void testExtractMutiFileCode_WithMixedCase() {
        String content = "```SINGLE_FILE\n<div>Test</div>\n```\n```CSS\nbody { color: red; }\n```\n```JavaScript\nconsole.log('test');\n```";
        MultiFileCodeResult result = CodeParserOld.extractMutiFileCode(content);
        assertNotNull(result);
        assertEquals("<div>Test</div>", result.getHtmlCode());
        assertEquals("body { color: red; }", result.getCssCode());
        assertEquals("console.log('test');", result.getJsCode());
    }
}
