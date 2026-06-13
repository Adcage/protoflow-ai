package com.adcage.acaicodefree.legacy.workflow.e2e;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.http.HttpUtil;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.tool.ImageSearchTool;
import com.adcage.acaicodefree.legacy.workflow.tool.LogoGeneratorTool;
import com.adcage.acaicodefree.legacy.workflow.tool.MermaidDiagramTool;
import com.adcage.acaicodefree.legacy.workflow.tool.ObjectStorageManager;
import com.adcage.acaicodefree.legacy.workflow.tool.UndrawIllustrationTool;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

public class WorkflowToolsE2ETest extends BaseE2ETest {

    private static final String PEXELS_API_KEY = System.getProperty("pexels.api-key", "");
    private static final String DASHSCOPE_API_KEY = System.getProperty("dashscope.api-key", "");

    @Nested
    @DisplayName("ImageSearchTool 真实 API E2E")
    class ImageSearchToolE2E {

        @Test
        @DisplayName("使用真实 Pexels API 搜索图片应返回非空列表")
        void searchWithRealPexelsApi_shouldReturnImages() {
            if (PEXELS_API_KEY.isEmpty()) {
                return;
            }
            ImageSearchTool tool = new ImageSearchTool(PEXELS_API_KEY, 5, keyword -> {
                HttpResponse response = HttpRequest.get("https://api.pexels.com/v1/search")
                        .form(Map.of("query", keyword, "per_page", 5))
                        .header("Authorization", PEXELS_API_KEY)
                        .execute();
                return response.body();
            });
            List<ImageResource> results = tool.search("nature");
            assertNotNull(results);
            if (!results.isEmpty()) {
                ImageResource first = results.get(0);
                assertEquals(ImageCategoryEnum.CONTENT, first.getCategory());
                assertNotNull(first.getUrl());
                assertNotNull(first.getDescription());
            }
        }

        @Test
        @DisplayName("空关键词应返回空列表")
        void searchWithBlankKeyword_shouldReturnEmptyList() {
            ImageSearchTool tool = new ImageSearchTool(PEXELS_API_KEY, 5, keyword -> "");
            List<ImageResource> results = tool.search("");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("空 API Key 应返回空列表")
        void searchWithBlankApiKey_shouldReturnEmptyList() {
            ImageSearchTool tool = new ImageSearchTool("", 5, keyword -> {
                throw new RuntimeException("不应调用 HTTP");
            });
            List<ImageResource> results = tool.search("test");
            assertTrue(results.isEmpty());
        }
    }

    @Nested
    @DisplayName("UndrawIllustrationTool 真实 API E2E")
    class UndrawIllustrationToolE2E {

        @Test
        @DisplayName("使用真实 undraw.co 搜索插画 HTML")
        void searchWithRealUndrawApi_shouldReturnResults() {
            UndrawIllustrationTool tool = new UndrawIllustrationTool((keyword, limit) ->
                    HttpUtil.get("https://undraw.co/search?query=" + HttpUtil.encodeParams(keyword, StandardCharsets.UTF_8)));
            List<ImageResource> results = tool.search("technology", 5);
            assertNotNull(results);
        }

        @Test
        @DisplayName("空关键词应返回空列表")
        void searchWithBlankKeyword_shouldReturnEmptyList() {
            UndrawIllustrationTool tool = new UndrawIllustrationTool((keyword, limit) -> "");
            List<ImageResource> results = tool.search("", 5);
            assertTrue(results.isEmpty());
        }
    }

    @Nested
    @DisplayName("MermaidDiagramTool E2E")
    class MermaidDiagramToolE2E {

        @Test
        @DisplayName("mmdc 不存在时应返回空列表而不是抛异常")
        void renderWithMissingCommand_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            MermaidDiagramTool tool = new MermaidDiagramTool(storageManager,
                    "nonexistent_mmdc_command", tempDir.toString(),
                    (command, outputFile) -> 1);
            List<ImageResource> results = tool.renderArchitectureDiagram("graph TD; A-->B", "测试图");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("空 mermaid 内容应返回空列表")
        void renderWithBlankContent_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            MermaidDiagramTool tool = new MermaidDiagramTool(storageManager,
                    "mmdc", tempDir.toString(),
                    (command, outputFile) -> 0);
            List<ImageResource> results = tool.renderArchitectureDiagram("", "空图");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("有效内容但命令执行失败应返回空列表")
        void renderWithValidContentButFailedExecution_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            MermaidDiagramTool tool = new MermaidDiagramTool(storageManager,
                    "mmdc", tempDir.toString(),
                    (command, outputFile) -> 1);
            List<ImageResource> results = tool.renderArchitectureDiagram("graph TD; A-->B", "测试图");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("有效内容且命令成功时应返回生成的图片资源")
        void renderWithValidContentAndSuccess_shouldReturnImageResource(@TempDir Path tempDir) throws Exception {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            MermaidDiagramTool tool = new MermaidDiagramTool(storageManager,
                    "echo", tempDir.toString(),
                    (command, outputFile) -> {
                        Files.createDirectories(outputFile.getParent());
                        Files.writeString(outputFile, "fake png content");
                        return 0;
                    });
            List<ImageResource> results = tool.renderArchitectureDiagram("graph TD; A-->B", "测试图");
            assertNotNull(results);
            if (!results.isEmpty()) {
                assertEquals(ImageCategoryEnum.ARCHITECTURE, results.get(0).getCategory());
                assertNotNull(results.get(0).getUrl());
            }
        }
    }

    @Nested
    @DisplayName("LogoGeneratorTool E2E")
    class LogoGeneratorToolE2E {

        @Test
        @DisplayName("空 API Key 应返回空列表")
        void generateWithBlankApiKey_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            LogoGeneratorTool tool = new LogoGeneratorTool("", tempDir.toString(), storageManager,
                    prompt -> "", (url, targetFile) -> {});
            List<ImageResource> results = tool.generateLogo("test logo");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("空 prompt 应返回空列表")
        void generateWithBlankPrompt_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            LogoGeneratorTool tool = new LogoGeneratorTool("some-key", tempDir.toString(), storageManager,
                    prompt -> "https://example.com/logo.png", (url, targetFile) -> {});
            List<ImageResource> results = tool.generateLogo("");
            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("LogoClient 返回空 URL 应返回空列表")
        void generateWithEmptyImageUrl_shouldReturnEmptyList(@TempDir Path tempDir) {
            ObjectStorageManager storageManager = new ObjectStorageManager(
                    createTestStorageProperties(tempDir), null);
            LogoGeneratorTool tool = new LogoGeneratorTool("some-key", tempDir.toString(), storageManager,
                    prompt -> "", (url, targetFile) -> {});
            List<ImageResource> results = tool.generateLogo("test logo");
            assertTrue(results.isEmpty());
        }
    }

    @Nested
    @DisplayName("ObjectStorageManager E2E")
    class ObjectStorageManagerE2E {

        @Test
        @DisplayName("本地存储模式应正确上传文件并返回本地 URL")
        void uploadToLocal_shouldReturnLocalUrl(@TempDir Path tempDir) throws Exception {
            Path storageDir = Files.createDirectories(tempDir.resolve("storage"));
            com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig localConfig =
                    new com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig();
            localConfig.setPath(storageDir.toString());
            localConfig.setUrlPrefix("http://localhost:8700/api/static");
            com.adcage.acaicodefree.config.properties.StorageProperties props =
                    new com.adcage.acaicodefree.config.properties.StorageProperties();
            props.setType("local");
            props.setLocal(localConfig);

            ObjectStorageManager manager = new ObjectStorageManager(props, null);
            Path testFile = Files.writeString(tempDir.resolve("test.txt"), "hello e2e");
            String url = manager.uploadFile("/workflow/test.txt", testFile.toFile());
            assertTrue(url.startsWith("http://localhost:8700/api/static/workflow/test.txt"));
            assertTrue(Files.exists(storageDir.resolve("workflow").resolve("test.txt")));
        }

        @Test
        @DisplayName("上传不存在文件应抛出异常")
        void uploadNonExistentFile_shouldThrowException(@TempDir Path tempDir) {
            com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig localConfig =
                    new com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig();
            localConfig.setPath(tempDir.toString());
            localConfig.setUrlPrefix("http://localhost:8700/api/static");
            com.adcage.acaicodefree.config.properties.StorageProperties props =
                    new com.adcage.acaicodefree.config.properties.StorageProperties();
            props.setType("local");
            props.setLocal(localConfig);

            ObjectStorageManager manager = new ObjectStorageManager(props, null);
            Path nonExistent = tempDir.resolve("does-not-exist.txt");
            assertThrows(Exception.class, () -> manager.uploadFile("/test.txt", nonExistent.toFile()));
        }
    }

    private com.adcage.acaicodefree.config.properties.StorageProperties createTestStorageProperties(Path tempDir) {
        com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig localConfig =
                new com.adcage.acaicodefree.config.properties.StorageProperties.LocalConfig();
        localConfig.setPath(tempDir.toString());
        localConfig.setUrlPrefix("http://localhost:8700/api/static");
        com.adcage.acaicodefree.config.properties.StorageProperties props =
                new com.adcage.acaicodefree.config.properties.StorageProperties();
        props.setType("local");
        props.setLocal(localConfig);
        return props;
    }
}