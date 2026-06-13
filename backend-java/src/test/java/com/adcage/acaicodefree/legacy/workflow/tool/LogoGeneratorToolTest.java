package com.adcage.acaicodefree.legacy.workflow.tool;

import com.adcage.acaicodefree.config.properties.StorageProperties;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class LogoGeneratorToolTest {

    @TempDir
    Path tempDir;

    @Test
    void generateLogoWhenPromptBlankShouldReturnEmptyList() {
        LogoGeneratorTool tool = new LogoGeneratorTool(
                "api-key",
                tempDir.toString(),
                new LocalOnlyStorageManager(tempDir),
                prompt -> "https://images.example.com/logo.png",
                (url, targetFile) -> Files.writeString(targetFile, "png", StandardCharsets.UTF_8)
        );

        assertTrue(tool.generateLogo("   ").isEmpty());
    }

    @Test
    void generateLogoWhenApiKeyMissingShouldReturnEmptyList() {
        LogoGeneratorTool tool = new LogoGeneratorTool(
                "",
                tempDir.toString(),
                new LocalOnlyStorageManager(tempDir),
                prompt -> {
                    fail("missing api key should not call logo client");
                    return "";
                },
                (url, targetFile) -> {
                }
        );

        assertTrue(tool.generateLogo("saas logo").isEmpty());
    }

    @Test
    void generateLogoShouldDownloadAndUpload() {
        LogoGeneratorTool tool = new LogoGeneratorTool(
                "api-key",
                tempDir.toString(),
                new LocalOnlyStorageManager(tempDir),
                prompt -> "https://images.example.com/logo.png",
                (url, targetFile) -> Files.writeString(targetFile, "png", StandardCharsets.UTF_8)
        );

        var result = tool.generateLogo("cloud platform");

        assertEquals(1, result.size());
        assertEquals(ImageCategoryEnum.LOGO, result.get(0).getCategory());
        assertTrue(result.get(0).getDescription().contains("cloud platform"));
        assertTrue(result.get(0).getUrl().contains("workflow/logo"));
    }

    @Test
    void generateLogoWhenClientThrowsShouldReturnEmptyList() {
        LogoGeneratorTool tool = new LogoGeneratorTool(
                "api-key",
                tempDir.toString(),
                new LocalOnlyStorageManager(tempDir),
                prompt -> {
                    throw new RuntimeException("dashscope timeout");
                },
                (url, targetFile) -> {
                }
        );

        assertTrue(tool.generateLogo("cloud platform").isEmpty());
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
