package com.adcage.acaicodefree.workflow.tool;

import com.adcage.acaicodefree.config.properties.StorageProperties;
import com.adcage.acaicodefree.manager.CosManager;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class ObjectStorageManagerTest {

    @TempDir
    Path tempDir;

    @Test
    void uploadFileWhenLocalStorageShouldCopyFileAndReturnUrl() throws IOException {
        StorageProperties storageProperties = new StorageProperties();
        storageProperties.setType("local");
        storageProperties.getLocal().setPath(tempDir.resolve("storage-root").toString());
        storageProperties.getLocal().setUrlPrefix("http://localhost:8700/api/storage");
        ObjectStorageManager objectStorageManager = new ObjectStorageManager(storageProperties, null);

        Path sourceFile = tempDir.resolve("source.txt");
        Files.writeString(sourceFile, "hello workflow", StandardCharsets.UTF_8);

        String url = objectStorageManager.uploadFile("/workflow/diagram/source.txt", sourceFile.toFile());

        assertEquals("http://localhost:8700/api/storage/workflow/diagram/source.txt", url);
        Path targetFile = tempDir.resolve("storage-root/workflow/diagram/source.txt");
        assertTrue(Files.exists(targetFile));
        assertEquals("hello workflow", Files.readString(targetFile, StandardCharsets.UTF_8));
    }

    @Test
    void uploadFileWhenCosStorageShouldDelegateToCosManager() {
        StorageProperties storageProperties = new StorageProperties();
        storageProperties.setType("cos");
        FakeCosManager cosManager = new FakeCosManager();
        ObjectStorageManager objectStorageManager = new ObjectStorageManager(storageProperties, cosManager);
        Path sourceFile = tempDir.resolve("demo.png");
        assertDoesNotThrow(() -> Files.writeString(sourceFile, "fake-png", StandardCharsets.UTF_8));

        String url = objectStorageManager.uploadFile("/workflow/logo.png", sourceFile.toFile());

        assertEquals("https://cos.example.com/workflow/logo.png", url);
        assertEquals("/workflow/logo.png", cosManager.lastKey);
        assertEquals("demo.png", cosManager.lastFile.getName());
    }

    @Test
    void uploadFileWhenSourceFileMissingShouldThrow() {
        StorageProperties storageProperties = new StorageProperties();
        storageProperties.setType("local");
        storageProperties.getLocal().setPath(tempDir.resolve("storage-root").toString());
        storageProperties.getLocal().setUrlPrefix("http://localhost:8700/api/storage");
        ObjectStorageManager objectStorageManager = new ObjectStorageManager(storageProperties, null);

        assertThrows(RuntimeException.class,
                () -> objectStorageManager.uploadFile("/workflow/missing.txt", tempDir.resolve("missing.txt").toFile()));
    }

    private static final class FakeCosManager extends CosManager {
        private String lastKey;
        private File lastFile;

        @Override
        public String uploadFile(String key, File file) {
            this.lastKey = key;
            this.lastFile = file;
            return "https://cos.example.com" + key;
        }
    }
}
