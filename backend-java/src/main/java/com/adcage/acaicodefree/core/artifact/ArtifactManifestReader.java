package com.adcage.acaicodefree.core.artifact;

import cn.hutool.core.io.FileUtil;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.model.vo.app.ArtifactManifestVO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Component
public class ArtifactManifestReader {

    private static final Logger log = LoggerFactory.getLogger(ArtifactManifestReader.class);

    private static final String MANIFEST_DIR = ".acai";
    private static final String MANIFEST_FILE = "artifact-manifest.json";

    public ArtifactManifestVO readManifest(Path workspaceRoot) {
        if (workspaceRoot == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR, "工作区路径不能为空");
        }
        Path normalizedRoot = workspaceRoot.toAbsolutePath().normalize();
        Path manifestPath = normalizedRoot.resolve(MANIFEST_DIR).resolve(MANIFEST_FILE).toAbsolutePath().normalize();

        if (!manifestPath.startsWith(normalizedRoot)) {
            throw new BusinessException(ErrorCode.FORBIDDEN_ERROR, "路径越界访问被拒绝");
        }

        if (!FileUtil.exist(manifestPath.toFile())) {
            log.debug("Manifest 文件不存在: {}", manifestPath);
            return null;
        }

        try {
            String content = FileUtil.readUtf8String(manifestPath.toFile());
            JSONObject json = JSONUtil.parseObj(content);
            ArtifactManifestVO vo = new ArtifactManifestVO();
            vo.setVersion(json.getStr("version"));
            vo.setGenerationMode(json.getStr("generationMode"));
            vo.setArtifactFormat(json.getStr("artifactFormat"));
            vo.setEntry(json.getStr("entry"));
            vo.setStatus(json.getStr("status"));

            JSONArray filesArray = json.getJSONArray("supportingFiles");
            if (filesArray != null && !filesArray.isEmpty()) {
                List<String> files = new ArrayList<>(filesArray.size());
                for (Object item : filesArray) {
                    files.add(String.valueOf(item));
                }
                vo.setSupportingFiles(files);
            } else {
                vo.setSupportingFiles(List.of());
            }

            return vo;
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("解析 Manifest 文件失败: {}", manifestPath, e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR, "Manifest 文件解析失败: " + e.getMessage());
        }
    }
}
