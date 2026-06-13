package com.adcage.acaicodefree.legacy.ai.tools;

import com.adcage.acaicodefree.exception.BusinessException;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

class FileDeleteToolTest {

    @TempDir
    Path tempDir;

    @Test
    void deleteFileShouldDeleteNormalFile() throws Exception {
        FileDeleteTool fileDeleteTool = createTool();
        Path targetFile = tempDir.resolve("vue_project_1").resolve("src/components/Hello.vue");
        Files.createDirectories(targetFile.getParent());
        Files.writeString(targetFile, "<template>hello</template>", StandardCharsets.UTF_8);

        String result = fileDeleteTool.deleteFile("src/components/Hello.vue", 1L, "vue_project");

        Assertions.assertEquals("文件删除成功：src/components/Hello.vue", result);
        Assertions.assertFalse(Files.exists(targetFile));
    }

    @Test
    void deleteFileShouldBlockProtectedFile() throws Exception {
        FileDeleteTool fileDeleteTool = createTool();
        Path targetFile = tempDir.resolve("vue_project_1").resolve("package.json");
        Files.createDirectories(targetFile.getParent());
        Files.writeString(targetFile, "{}", StandardCharsets.UTF_8);

        Assertions.assertThrows(BusinessException.class, () -> fileDeleteTool.deleteFile("package.json", 1L, "vue_project"));
        Assertions.assertTrue(Files.exists(targetFile));
    }

    @Test
    void deleteFileShouldWorkWithSingleFile() throws Exception {
        FileDeleteTool fileDeleteTool = createTool();
        Path targetFile = tempDir.resolve("single_file_1").resolve("index.html");
        Files.createDirectories(targetFile.getParent());
        Files.writeString(targetFile, "<html></html>", StandardCharsets.UTF_8);

        String result = fileDeleteTool.deleteFile("index.html", 1L, "single_file");

        Assertions.assertEquals("文件删除成功：index.html", result);
        Assertions.assertFalse(Files.exists(targetFile));
    }

    @Test
    void deleteFileShouldWorkWithMultiFile() throws Exception {
        FileDeleteTool fileDeleteTool = createTool();
        Path targetFile = tempDir.resolve("multi-file_1").resolve("script.js");
        Files.createDirectories(targetFile.getParent());
        Files.writeString(targetFile, "console.log('test')", StandardCharsets.UTF_8);

        String result = fileDeleteTool.deleteFile("script.js", 1L, "multi-file");

        Assertions.assertEquals("文件删除成功：script.js", result);
        Assertions.assertFalse(Files.exists(targetFile));
    }

    private FileDeleteTool createTool() {
        FileDeleteTool fileDeleteTool = new FileDeleteTool();
        ReflectionTestUtils.setField(fileDeleteTool, "codeOutputRootPath", tempDir);
        return fileDeleteTool;
    }
}
