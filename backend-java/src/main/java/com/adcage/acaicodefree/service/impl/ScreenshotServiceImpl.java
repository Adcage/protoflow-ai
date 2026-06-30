package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.config.properties.ScreenshotProperties;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.mybatisflex.core.update.UpdateChain;
import com.adcage.acaicodefree.service.ScreenshotService;
import com.adcage.acaicodefree.storage.FileStorageStrategy;
import com.adcage.acaicodefree.utils.WebScreenshotUtils;
import jakarta.annotation.PreDestroy;
import jakarta.annotation.Resource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
public class ScreenshotServiceImpl implements ScreenshotService {

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy/MM/dd");
    private static final Logger log = LoggerFactory.getLogger(ScreenshotServiceImpl.class);

    @Resource
    private FileStorageStrategy fileStorageStrategy;

    @Resource
    private ScreenshotProperties screenshotProperties;

    @Resource
    private AppMapper appMapper;

    @Resource
    private WorkspaceProperties workspaceProperties;

    @Value("${server.port:8700}")
    private String serverPort;

    @Value("${server.servlet.context-path:}")
    private String contextPath;

    private final ExecutorService screenshotTaskExecutor = Executors.newSingleThreadExecutor(runnable -> {
        Thread thread = new Thread(runnable);
        thread.setName("screenshot-task");
        thread.setDaemon(true);
        return thread;
    });

    private final Map<Long, Map<String, Object>> coverTaskStateMap = new ConcurrentHashMap<>();

    @PreDestroy
    public void destroyScreenshotExecutor() {
        screenshotTaskExecutor.shutdown();
    }

    @Override
    public String generateAndUploadCover(Long appId, String appUrl) {
        if (appId == null || appId <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "应用 id 不合法");
        }
        if (StrUtil.isBlank(appUrl)) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "应用访问地址不能为空");
        }
        File compressedFile = null;
        try {
            compressedFile = captureCompressedFile(appUrl);
            String objectKey = buildObjectKey(compressedFile.getName());
            return fileStorageStrategy.uploadFile(objectKey, compressedFile);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("生成应用封面失败, appId={}, appUrl={}", appId, appUrl, e);
            throw new BusinessException(ErrorCode.OPERATION_ERROR, "生成封面失败: " + e.getMessage());
        } finally {
            WebScreenshotUtils.deleteIfExists(compressedFile);
        }
    }

    @Override
    public void triggerCoverGenerationIfNeeded(Long appId, Long agentRunId) {
        if (appId == null || appId <= 0) {
            return;
        }

        Map<String, Object> existingState = coverTaskStateMap.get(appId);
        if (existingState != null) {
            String status = (String) existingState.getOrDefault("status", "");
            Long existingAgentRunId = (Long) existingState.get("agentRunId");

            if (agentRunId != null && agentRunId.equals(existingAgentRunId)
                    && ("RUNNING".equals(status) || "SUCCESS".equals(status) || "PENDING".equals(status))) {
                log.info("封面任务已在进行或已完成（同一 AgentRun），跳过, appId={}, agentRunId={}", appId, agentRunId);
                return;
            }

            if ("RUNNING".equals(status) || "PENDING".equals(status)) {
                log.info("封面任务正在执行中（不同 AgentRun），跳过本次触发, appId={}, currentAgentRunId={}, newAgentRunId={}",
                        appId, existingAgentRunId, agentRunId);
                return;
            }
        }

        App app = appMapper.selectOneById(appId);
        if (app == null) {
            return;
        }

        String previewUrl = computePreviewUrl(app);
        if (StrUtil.isBlank(previewUrl)) {
            log.debug("应用无可预览内容，跳过截图, appId={}", appId);
            return;
        }

        updateCoverTaskState(appId, "PENDING", 0, null, agentRunId);
        screenshotTaskExecutor.submit(() -> {
            int maxRetries = screenshotProperties.getMaxRetries() == null ? 3 : Math.max(screenshotProperties.getMaxRetries(), 1);
            long retryDelayMillis = screenshotProperties.getRetryDelayMillis() == null ? 3000L : Math.max(screenshotProperties.getRetryDelayMillis(), 0L);
            for (int attempt = 1; attempt <= maxRetries; attempt++) {
                updateCoverTaskState(appId, "RUNNING", attempt, null, agentRunId);
                try {
                    String coverUrl = generateAndUploadCover(appId, previewUrl);
                    if (StrUtil.isBlank(coverUrl)) {
                        updateCoverTaskState(appId, "FAILED", attempt, "封面地址为空", agentRunId);
                        continue;
                    }
                    App updateApp = new App();
                    updateApp.setId(appId);
                    updateApp.setCover(coverUrl);
                    boolean updated = UpdateChain.of(App.class)
                            .set(App::getCover, coverUrl)
                            .where(App::getId).eq(appId)
                            .update();
                    if (!updated) {
                        updateCoverTaskState(appId, "FAILED", attempt, "封面地址回写失败", agentRunId);
                        log.warn("封面地址回写失败, appId={}, coverUrl={}", appId, coverUrl);
                        continue;
                    }
                    updateCoverTaskState(appId, "SUCCESS", attempt, null, agentRunId);
                    return;
                } catch (Exception e) {
                    updateCoverTaskState(appId, "FAILED", attempt, e.getMessage(), agentRunId);
                    log.error("异步生成封面失败, appId={}, attempt={}", appId, attempt, e);
                    if (attempt < maxRetries && retryDelayMillis > 0) {
                        try {
                            Thread.sleep(retryDelayMillis);
                        } catch (InterruptedException interruptedException) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                    }
                }
            }
        });
    }

    /**
     * 计算应用的可预览 URL。
     * 优先使用部署 URL，其次使用 workspace 路径。
     */
    public String computePreviewUrl(App app) {
        if (app == null || app.getId() == null) {
            return null;
        }

        String deployKey = app.getDeployKey();
        if (StrUtil.isNotBlank(deployKey)) {
            return buildDeployUrl(deployKey);
        }

        CodeGenTypeEnum typeEnum = CodeGenTypeEnum.getEnumByValue(app.getCodeGenType());
        if (typeEnum == null) {
            return null;
        }

        String prefix = getCodeGenOutputPrefix(typeEnum);
        Path workspaceRoot = Path.of(workspaceProperties.getAgentWorkspaceDir()).toAbsolutePath().normalize();
        Path appDir = workspaceRoot.resolve(prefix).resolve(String.valueOf(app.getId()));
        if (!Files.exists(appDir)) {
            appDir = AppConstant.getCodeOutputRootPath().resolve(prefix).resolve(String.valueOf(app.getId()));
            if (!Files.exists(appDir)) {
                return null;
            }
        }

        if (typeEnum == CodeGenTypeEnum.VUE_PROJECT) {
            if (!Files.exists(appDir.resolve("dist").resolve("index.html"))) {
                return null;
            }
            return buildWorkspaceUrl(prefix, String.valueOf(app.getId()), "dist/index.html");
        }

        if (!Files.exists(appDir.resolve("index.html"))) {
            return null;
        }
        return buildWorkspaceUrl(prefix, String.valueOf(app.getId()), "index.html");
    }

    /**
     * 获取封面任务状态（供 AppService 读取）
     */
    public Map<String, Object> getCoverTaskState(Long appId) {
        if (appId == null) {
            return null;
        }
        return coverTaskStateMap.get(appId);
    }

    File captureCompressedFile(String appUrl) throws Exception {
        return WebScreenshotUtils.captureAndCompress(appUrl,
                screenshotProperties.getTempDir(),
                screenshotProperties.getWidth(),
                screenshotProperties.getHeight(),
                screenshotProperties.getWaitAfterLoadMillis(),
                screenshotProperties.getCompressionQuality(),
                screenshotProperties.getBrowserType());
    }

    private String buildObjectKey(String fileName) {
        String prefix = StrUtil.blankToDefault(screenshotProperties.getUploadPrefix(), "/screenshots");
        if (!prefix.startsWith("/")) {
            prefix = "/" + prefix;
        }
        return prefix + "/" + DATE_FORMATTER.format(LocalDate.now()) + "/" + fileName;
    }

    private void updateCoverTaskState(Long appId, String status, Integer retryCount, String errorMessage, Long agentRunId) {
        Map<String, Object> state = new HashMap<>();
        state.put("status", status);
        state.put("retryCount", retryCount == null ? 0 : retryCount);
        state.put("errorMessage", StrUtil.blankToDefault(errorMessage, ""));
        state.put("updatedTime", LocalDateTime.now());
        state.put("agentRunId", agentRunId);
        coverTaskStateMap.put(appId, state);
    }

    private String buildDeployUrl(String deployKey) {
        String baseHost = AppConstant.CODE_DEPLOY_HOST;
        String normalizedContextPath = contextPath == null || contextPath.isBlank() ? "" : contextPath;
        if (!normalizedContextPath.startsWith("/")) {
            normalizedContextPath = "/" + normalizedContextPath;
        }
        if (normalizedContextPath.endsWith("/")) {
            normalizedContextPath = normalizedContextPath.substring(0, normalizedContextPath.length() - 1);
        }
        String hostWithPort = baseHost.contains("://") && baseHost.matches("^https?://[^/:]+:\\d+$")
                ? baseHost
                : baseHost + ":" + serverPort;
        return String.format("%s%s/static/%s/index.html", hostWithPort, normalizedContextPath, deployKey);
    }

    private String buildWorkspaceUrl(String prefix, String appId, String entryFile) {
        String baseHost = AppConstant.CODE_DEPLOY_HOST;
        String normalizedContextPath = contextPath == null || contextPath.isBlank() ? "" : contextPath;
        if (!normalizedContextPath.startsWith("/")) {
            normalizedContextPath = "/" + normalizedContextPath;
        }
        if (normalizedContextPath.endsWith("/")) {
            normalizedContextPath = normalizedContextPath.substring(0, normalizedContextPath.length() - 1);
        }
        String hostWithPort = baseHost.contains("://") && baseHost.matches("^https?://[^/:]+:\\d+$")
                ? baseHost
                : baseHost + ":" + serverPort;
        return String.format("%s%s/static/%s/%s/%s", hostWithPort, normalizedContextPath, prefix, appId, entryFile);
    }

    private String getCodeGenOutputPrefix(CodeGenTypeEnum typeEnum) {
        return switch (typeEnum) {
            case VUE_PROJECT -> AppConstant.VUE_PROJECT_OUTPUT_PREFIX;
            case SINGLE_FILE -> AppConstant.SINGLE_FILE_OUTPUT_PREFIX;
            case MULTI_FILE -> AppConstant.MULTI_FILE_OUTPUT_PREFIX;
        };
    }
}
