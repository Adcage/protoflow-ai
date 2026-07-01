package com.adcage.acaicodefree.core.build;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

class VueProjectBuildServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void shouldRunNpmInstallAndBuildInVueProjectDirectory() throws Exception {
        List<List<String>> commands = new ArrayList<>();
        TestBuildService buildService = new TestBuildService(tempDir, commands);
        Long appId = 1L;
        Path projectDir = tempDir.resolve("vue_project").resolve(String.valueOf(appId));
        Files.createDirectories(projectDir);
        Files.writeString(projectDir.resolve("package.json"), "{\"name\":\"demo\"}");

        buildService.buildVueProject(appId);

        Assertions.assertEquals(2, commands.size());
        Assertions.assertTrue(commands.get(0).contains("install"));
        Assertions.assertTrue(commands.get(1).contains("build"));
        Assertions.assertTrue(Files.exists(projectDir.resolve("dist")));
    }

    @Test
    void shouldUseNpmCmdOnWindows() {
        VueProjectBuildService buildService = new VueProjectBuildService();

        Assertions.assertEquals("npm.cmd", buildService.resolveNpmCommand("Windows 11"));
        Assertions.assertEquals("npm", buildService.resolveNpmCommand("Linux"));
    }

    @Test
    void shouldFailWhenDistDirectoryMissingAfterBuild() throws Exception {
        TestBuildService buildService = new TestBuildService(tempDir, new ArrayList<>()) {
            @Override
            protected CommandResult executeCommand(List<String> command, Path projectDir, int timeoutSeconds) {
                return new CommandResult(0, "ok");
            }
        };
        Long appId = 2L;
        Path projectDir = tempDir.resolve("vue_project").resolve(String.valueOf(appId));
        Files.createDirectories(projectDir);
        Files.writeString(projectDir.resolve("package.json"), "{\"name\":\"demo\"}");

        Assertions.assertThrows(RuntimeException.class, () -> buildService.buildVueProject(appId));
    }

    @Test
    void shouldRepairInvalidPackageVersionAndRetryInstall() throws Exception {
        Long appId = 3L;
        Path projectDir = tempDir.resolve("vue_project").resolve(String.valueOf(appId));
        Files.createDirectories(projectDir);
        Files.writeString(projectDir.resolve("package.json"), """
                {
                  "name": "demo",
                  "version": "1.0.0",
                  "dependencies": {
                    "@vue/compiler-dom": "3.5.30"
                  }
                }
                """);

        List<List<String>> commands = new ArrayList<>();
        TestBuildService buildService = new TestBuildService(tempDir, commands) {
            private int installCount = 0;

            @Override
            protected CommandResult executeCommand(List<String> command, Path commandProjectDir, int timeoutSeconds) {
                commands.add(command);
                if (command.contains("install")) {
                    installCount++;
                    if (installCount == 1) {
                        return new CommandResult(1, "npm error notarget No matching version found for @vue/compiler-dom@3.5.30.");
                    }
                    try {
                        Files.createDirectories(commandProjectDir.resolve("dist"));
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                    return new CommandResult(0, "ok");
                }
                if (command.contains("view")) {
                    return new CommandResult(0, "3.5.29");
                }
                if (command.contains("build")) {
                    return new CommandResult(0, "build ok");
                }
                return new CommandResult(0, "ok");
            }
        };

        buildService.buildVueProject(appId);

        Assertions.assertTrue(commands.stream().anyMatch(cmd -> cmd.contains("view")));
        Assertions.assertEquals(2, commands.stream().filter(cmd -> cmd.contains("install")).count());
        String packageJson = Files.readString(projectDir.resolve("package.json"));
        Assertions.assertTrue(packageJson.contains("\"@vue/compiler-dom\": \"3.5.29\""));
    }

    @Test
    void shouldFallbackToUpdateVueWhenCompilerDomMissingIsTransitive() throws Exception {
        Long appId = 4L;
        Path projectDir = tempDir.resolve("vue_project").resolve(String.valueOf(appId));
        Files.createDirectories(projectDir);
        Files.writeString(projectDir.resolve("package.json"), """
                {
                  "name": "demo",
                  "version": "1.0.0",
                  "dependencies": {
                    "vue": "3.5.30"
                  },
                  "devDependencies": {
                    "@vue/compiler-sfc": "3.5.30"
                  }
                }
                """);

        TestBuildService buildService = new TestBuildService(tempDir, new ArrayList<>()) {
            private int installCount = 0;

            @Override
            protected CommandResult executeCommand(List<String> command, Path commandProjectDir, int timeoutSeconds) {
                if (command.contains("install")) {
                    installCount++;
                    if (installCount == 1) {
                        return new CommandResult(1, "npm error notarget No matching version found for @vue/compiler-dom@3.5.30.");
                    }
                    try {
                        Files.createDirectories(commandProjectDir.resolve("dist"));
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                    return new CommandResult(0, "ok");
                }
                if (command.contains("view")) {
                    return new CommandResult(0, "3.5.29");
                }
                if (command.contains("build")) {
                    return new CommandResult(0, "build ok");
                }
                return new CommandResult(0, "ok");
            }
        };

        buildService.buildVueProject(appId);

        String packageJson = Files.readString(projectDir.resolve("package.json"));
        Assertions.assertTrue(packageJson.contains("\"vue\": \"3.5.29\""));
        Assertions.assertTrue(packageJson.contains("\"@vue/compiler-sfc\": \"3.5.29\""));
    }

    private static class TestBuildService extends VueProjectBuildService {

        private final List<List<String>> commands;

        private TestBuildService(Path outputRootPath, List<List<String>> commands) {
            this.commands = commands;
            ReflectionTestUtils.setField(this, "outputRootPath", outputRootPath);
            ReflectionTestUtils.setField(this, "installTimeoutSeconds", 300);
            ReflectionTestUtils.setField(this, "buildTimeoutSeconds", 180);
        }

        @Override
        protected CommandResult executeCommand(List<String> command, Path projectDir, int timeoutSeconds) {
            commands.add(command);
            if (command.contains("build")) {
                try {
                    Files.createDirectories(projectDir.resolve("dist"));
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
            return new CommandResult(0, "ok");
        }
    }
}
