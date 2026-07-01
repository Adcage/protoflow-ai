package com.adcage.acaicodefree.legacy.ai.tools;

import com.adcage.acaicodefree.exception.BusinessException;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

class FileWriteToolTest {

    @TempDir
    Path tempDir;

    @Test
    void writeFileShouldCreateParentDirectoriesAndWriteUtf8Content() throws Exception {
        FileWriteTool fileWriteTool = createFileWriteTool();

        String result = fileWriteTool.writeFile("src/App.vue", "你好，Vue 工程", 1L, "vue_project");

        Path expectedFile = tempDir.resolve("vue_project1").resolve("src/App.vue");
        Assertions.assertTrue(Files.exists(expectedFile));
        Assertions.assertEquals("你好，Vue 工程", Files.readString(expectedFile, StandardCharsets.UTF_8));
        Assertions.assertEquals("文件写入成功：src/App.vue", result);
    }

    @Test
    void writeFileShouldRejectAbsolutePath() {
        FileWriteTool fileWriteTool = createFileWriteTool();

        Assertions.assertThrows(BusinessException.class,
                () -> fileWriteTool.writeFile("C:/windows/system32/test.txt", "bad", 1L, "vue_project"));
    }

    @Test
    void writeFileShouldRejectPathTraversal() {
        FileWriteTool fileWriteTool = createFileWriteTool();

        Assertions.assertThrows(BusinessException.class,
                () -> fileWriteTool.writeFile("../escape.txt", "bad", 1L, "vue_project"));
    }

    @Test
    void writeFileShouldReturnRelativePathOnly() {
        FileWriteTool fileWriteTool = createFileWriteTool();

        String result = fileWriteTool.writeFile("package.json", "{}", 1L, "vue_project");

        Assertions.assertEquals("文件写入成功：package.json", result);
        Assertions.assertFalse(result.contains(tempDir.toString()));
        Assertions.assertFalse(result.contains(":\\"));
    }

    @Test
    void writeFileShouldWorkWithSingleFile() throws Exception {
        FileWriteTool fileWriteTool = createFileWriteTool();

        String result = fileWriteTool.writeFile("index.html", "<html></html>", 1L, "single_file");

        Path expectedFile = tempDir.resolve("single_file1").resolve("index.html");
        Assertions.assertTrue(Files.exists(expectedFile));
        Assertions.assertEquals("文件写入成功：index.html", result);
    }

    @Test
    void writeFileShouldWorkWithMultiFile() throws Exception {
        FileWriteTool fileWriteTool = createFileWriteTool();

        String result = fileWriteTool.writeFile("style.css", "body {}", 1L, "multi-file");

        Path expectedFile = tempDir.resolve("multi-file1").resolve("style.css");
        Assertions.assertTrue(Files.exists(expectedFile));
        Assertions.assertEquals("文件写入成功：style.css", result);
    }

    private FileWriteTool createFileWriteTool() {
        FileWriteTool fileWriteTool = new FileWriteTool();
        ReflectionTestUtils.setField(fileWriteTool, "codeOutputRootPath", tempDir);
        return fileWriteTool;
    }
}
