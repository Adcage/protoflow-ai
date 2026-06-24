package com.adcage.acaicodefree.core.artifact;

import cn.hutool.core.io.FileUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.vo.app.ArtifactManifestVO;
import com.adcage.acaicodefree.service.AppService;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Service
public class LegacyArtifactManifestBackfillService {

    private static final Logger log = LoggerFactory.getLogger(LegacyArtifactManifestBackfillService.class);

    private static final String MANIFEST_DIR = ".acai";
    private static final String MANIFEST_FILE = "artifact-manifest.json";
    private static final String MANIFEST_VERSION = "2";

    @Resource
    private AppService appService;

    @Resource
    private WorkspaceProperties workspaceProperties;

    @Resource
    private ArtifactManifestReader manifestReader;

    public BackfillResult backfill() {
        List<App> allApps = appService.list();
        int success = 0;
        int skipped = 0;
        int failed = 0;
        List<Long> failedIds = new ArrayList<>();

        for (App app : allApps) {
            try {
                if (app.getId() == null || app.getCodeGenType() == null) {
                    skipped++;
                    continue;
                }

                Path workspaceRoot = resolveWorkspaceRoot(app);
                if (workspaceRoot == null) {
                    skipped++;
                    continue;
                }

                ArtifactManifestVO existing = manifestReader.readManifest(workspaceRoot);
                if (existing != null) {
                    skipped++;
                    continue;
                }

                String artifactFormat = mapCodeGenTypeToArtifactFormat(app.getCodeGenType());
                if (artifactFormat == null) {
                    failed++;
                    failedIds.add(app.getId());
                    log.warn("未知的 codeGenType，跳过回填, appId={}, codeGenType={}", app.getId(), app.getCodeGenType());
                    continue;
                }

                generateManifest(workspaceRoot, artifactFormat, app.getGenerationMode());
                success++;
                log.info("回填 Manifest 成功, appId={}, codeGenType={}, artifactFormat={}",
                        app.getId(), app.getCodeGenType(), artifactFormat);
            } catch (Exception e) {
                failed++;
                failedIds.add(app.getId());
                log.error("回填 Manifest 失败, appId={}", app.getId(), e);
            }
        }

        log.info("Manifest 回填完成: success={}, skipped={}, failed={}, failedIds={}", success, skipped, failed, failedIds);
        return new BackfillResult(success, skipped, failed, failedIds);
    }

    private Path resolveWorkspaceRoot(App app) {
        String codeGenType = app.getCodeGenType();
        String prefix = switch (codeGenType) {
            case "single_file" -> "single_file";
            case "multi-file" -> "multi-file";
            case "vue_project" -> "vue_project";
            default -> null;
        };
        if (prefix == null) {
            return null;
        }
        Path workspaceDir = Path.of(workspaceProperties.getAgentWorkspaceDir()).toAbsolutePath().normalize();
        Path appDir = workspaceDir.resolve(prefix).resolve(String.valueOf(app.getId()));
        if (!FileUtil.exist(appDir.toFile())) {
            return null;
        }
        return appDir;
    }

    String mapCodeGenTypeToArtifactFormat(String codeGenType) {
        if (codeGenType == null) {
            return null;
        }
        return switch (codeGenType) {
            case "single_file" -> "web_single_file";
            case "multi-file" -> "web_multi_file";
            case "vue_project" -> "vue_project";
            default -> null;
        };
    }

    private void generateManifest(Path workspaceRoot, String artifactFormat, String generationMode) {
        Path acaiDir = workspaceRoot.resolve(MANIFEST_DIR);
        Path manifestPath = acaiDir.resolve(MANIFEST_FILE);

        FileUtil.mkdir(acaiDir.toFile());

        JSONObject manifest = new JSONObject();
        manifest.set("version", MANIFEST_VERSION);
        manifest.set("generationMode", generationMode != null ? generationMode : "application");
        manifest.set("artifactFormat", artifactFormat);
        manifest.set("entry", resolveEntry(artifactFormat));
        manifest.set("supportingFiles", new JSONArray());
        manifest.set("status", "complete");

        FileUtil.writeUtf8String(JSONUtil.toJsonPrettyStr(manifest), manifestPath.toFile());
    }

    private String resolveEntry(String artifactFormat) {
        return switch (artifactFormat) {
            case "web_single_file" -> "index.html";
            case "web_multi_file" -> "index.html";
            case "vue_project" -> "dist/index.html";
            default -> "index.html";
        };
    }

    public record BackfillResult(int success, int skipped, int failed, List<Long> failedIds) {
    }
}
