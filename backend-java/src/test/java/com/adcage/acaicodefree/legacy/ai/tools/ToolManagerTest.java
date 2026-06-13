package com.adcage.acaicodefree.legacy.ai.tools;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Arrays;

class ToolManagerTest {

    @Test
    void shouldRegisterAndFindToolsByToolName() {
        ToolManager toolManager = createToolManager(new FileWriteTool(), new FileModifyTool());

        BaseTool writeTool = toolManager.getTool("writeFile");
        BaseTool modifyTool = toolManager.getTool("modifyFile");

        Assertions.assertNotNull(writeTool);
        Assertions.assertNotNull(modifyTool);
        Assertions.assertEquals("写文件", writeTool.getDisplayName());
        Assertions.assertEquals("改文件", modifyTool.getDisplayName());
    }

    @Test
    void shouldExposeAllToolsAsArray() {
        ToolManager toolManager = createToolManager(new FileWriteTool(), new FileReadTool(), new FileDirReadTool());

        Object[] allTools = toolManager.getAllTools();

        Assertions.assertEquals(3, allTools.length);
    }

    @Test
    void shouldThrowWhenToolNameDuplicated() {
        ToolManager toolManager = new ToolManager();
        ReflectionTestUtils.setField(toolManager, "tools", new BaseTool[]{new FileWriteTool(), new FileWriteTool()});

        Assertions.assertThrows(IllegalStateException.class, toolManager::init);
    }

    private ToolManager createToolManager(BaseTool... tools) {
        ToolManager toolManager = new ToolManager();
        ReflectionTestUtils.setField(toolManager, "tools", Arrays.copyOf(tools, tools.length));
        toolManager.init();
        return toolManager;
    }
}
