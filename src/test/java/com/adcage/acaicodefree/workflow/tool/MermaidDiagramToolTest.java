package com.adcage.acaicodefree.workflow.tool;

import com.adcage.acaicodefree.config.properties.StorageProperties;
import com.adcage.acaicodefree.workflow.model.ImageCategoryEnum;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MermaidDiagramToolTest {

    @TempDir
    Path tempDir;

    @Test
    void renderWhenContentBlankShouldReturnEmptyList() {
        MermaidDiagramTool tool = new MermaidDiagramTool(
                new LocalOnlyStorageManager(tempDir),
                "mmdc",
                tempDir.toString(),
                (command, outputFile) -> 0
        );

        assertTrue(tool.renderArchitectureDiagram("  ", "blank").isEmpty());
    }

    @Test
    void renderWhenCommandFailsShouldReturnEmptyList() {
        MermaidDiagramTool tool = new MermaidDiagramTool(
                new LocalOnlyStorageManager(tempDir),
                "mmdc_not_found",
                tempDir.toString(),
                (command, outputFile) -> 1
        );

        assertTrue(tool.renderArchitectureDiagram("graph TD\nA-->B", "failed").isEmpty());
    }

    @Test
    void renderShouldUploadGeneratedDiagram() {
        MermaidDiagramTool tool = new MermaidDiagramTool(
                new LocalOnlyStorageManager(tempDir),
                "mmdc",
                tempDir.toString(),
                (command, outputFile) -> {
                    Files.writeString(outputFile, "png-binary", StandardCharsets.UTF_8);
                    return 0;
                }
        );

        var result = tool.renderArchitectureDiagram("graph TD\nA-->B", "system architecture");

        assertEquals(1, result.size());
        assertEquals(ImageCategoryEnum.ARCHITECTURE, result.get(0).getCategory());
        assertEquals("system architecture", result.get(0).getDescription());
        assertTrue(result.get(0).getUrl().contains("workflow/mermaid"));
    }

    private static final class LocalOnlyStorageManager extends ObjectStorageManager {
        private LocalOnlyStorageManager(Path tempDir) {
            super(storageProperties(tempDir), null);
        }

        private static StorageProperties storageProperties(Path tempDir) {
            StorageProperties storageProperties = new StorageProperties();
            storageProperties.setType("local");
            storageProperties.getLocal().setPath(tempDir.resolve("storage-root").toString());
            storageProperties.getLocal().setUrlPrefix("http://localhost:8700/api/storage");
            return storageProperties;
        }
    }
}
