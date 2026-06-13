package com.adcage.acaicodefree.controller;

import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.IdUtil;
import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.common.BaseResponse;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.common.ResultUtils;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.service.UserService;
import com.adcage.acaicodefree.storage.FileStorageStrategy;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

@RestController
@RequestMapping("/file")
@Slf4j
public class FileController {

    @Resource
    private FileStorageStrategy fileStorageStrategy;

    @Resource
    private UserService userService;

    private static final long MAX_AVATAR_SIZE = 2 * 1024 * 1024;

    @PostMapping("/upload/avatar")
    public BaseResponse<String> uploadAvatar(@RequestParam("file") MultipartFile file,
                                              HttpServletRequest request) {
        ThrowUtils.throwIf(file == null || file.isEmpty(), ErrorCode.PARAMS_ERROR, "请选择头像文件");
        ThrowUtils.throwIf(file.getSize() > MAX_AVATAR_SIZE, ErrorCode.PARAMS_ERROR, "头像文件不能超过 2MB");

        String contentType = file.getContentType();
        ThrowUtils.throwIf(contentType == null || !contentType.startsWith("image/"), ErrorCode.PARAMS_ERROR, "仅支持图片文件");

        User loginUser = userService.getLoginUser(request);
        String originalFilename = file.getOriginalFilename();
        String ext = "jpg";
        if (StrUtil.isNotBlank(originalFilename) && originalFilename.contains(".")) {
            ext = originalFilename.substring(originalFilename.lastIndexOf(".") + 1).toLowerCase();
        }
        String allowedExts = "jpg,jpeg,png,gif,webp";
        ThrowUtils.throwIf(!allowedExts.contains(ext), ErrorCode.PARAMS_ERROR, "不支持的图片格式，仅支持 jpg/png/gif/webp");

        String datePath = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy/MM/dd"));
        String fileName = IdUtil.fastSimpleUUID() + "." + ext;
        String key = "avatars/" + datePath + "/" + fileName;

        File tempFile = null;
        try {
            tempFile = File.createTempFile("upload-", "." + ext);
            file.transferTo(tempFile);
            String url = fileStorageStrategy.uploadFile(key, tempFile);
            log.info("头像上传成功, userId={}, url={}", loginUser.getId(), url);
            return ResultUtils.success(url);
        } catch (Exception e) {
            log.error("头像上传失败, userId={}", loginUser.getId(), e);
            throw new RuntimeException("头像上传失败: " + e.getMessage());
        } finally {
            if (tempFile != null) {
                FileUtil.del(tempFile);
            }
        }
    }
}
