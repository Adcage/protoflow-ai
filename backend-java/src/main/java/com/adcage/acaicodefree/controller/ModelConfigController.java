package com.adcage.acaicodefree.controller;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.annotation.AuthCheck;
import com.adcage.acaicodefree.common.BaseResponse;
import com.adcage.acaicodefree.common.DeleteRequest;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.common.ResultUtils;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.model.dto.modelconfig.ModelConfigAddRequest;
import com.adcage.acaicodefree.model.dto.modelconfig.ModelConfigEditRequest;
import com.adcage.acaicodefree.model.dto.modelconfig.ModelConfigQueryRequest;
import com.adcage.acaicodefree.model.entity.ModelConfig;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.modelconfig.ModelConfigVO;
import com.adcage.acaicodefree.service.ModelConfigService;
import com.adcage.acaicodefree.service.UserService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.io.Serializable;
import java.util.List;

@RestController
@RequestMapping("/model-config")
@Slf4j
public class ModelConfigController {

    @Resource
    private ModelConfigService modelConfigService;

    @Resource
    private UserService userService;

    @Value("${agent.runtime.internal-secret:}")
    private String internalSecret;

    @PostMapping("/add")
    public BaseResponse<Long> addModelConfig(@RequestBody ModelConfigAddRequest modelConfigAddRequest, HttpServletRequest request) {
        ThrowUtils.throwIf(modelConfigAddRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        ModelConfig modelConfig = new ModelConfig();
        BeanUtil.copyProperties(modelConfigAddRequest, modelConfig);
        modelConfig.setUserId(loginUser.getId());
        modelConfigService.validModelConfig(modelConfig, true);
        boolean result = modelConfigService.save(modelConfig);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "创建模型配置失败");
        return ResultUtils.success(modelConfig.getId());
    }

    @PostMapping("/delete")
    public BaseResponse<Boolean> deleteModelConfig(@RequestBody DeleteRequest deleteRequest, HttpServletRequest request) {
        if (deleteRequest == null || deleteRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        long id = deleteRequest.getId();
        ModelConfig oldModelConfig = modelConfigService.getById(id);
        ThrowUtils.throwIf(oldModelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        if (!oldModelConfig.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限删除该模型配置");
        }
        boolean result = modelConfigService.removeById(id);
        return ResultUtils.success(result);
    }

    @PostMapping("/edit")
    public BaseResponse<Boolean> editModelConfig(@RequestBody ModelConfigEditRequest modelConfigEditRequest, HttpServletRequest request) {
        if (modelConfigEditRequest == null || modelConfigEditRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        long id = modelConfigEditRequest.getId();
        ModelConfig oldModelConfig = modelConfigService.getById(id);
        ThrowUtils.throwIf(oldModelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        if (!oldModelConfig.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限编辑该模型配置");
        }
        ModelConfig modelConfig = new ModelConfig();
        BeanUtil.copyProperties(modelConfigEditRequest, modelConfig);
        modelConfigService.validModelConfig(modelConfig, false);
        boolean result = modelConfigService.updateById(modelConfig);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "编辑模型配置失败");
        modelConfigService.incrementConfigVersion(id);
        return ResultUtils.success(true);
    }

    @GetMapping("/get/vo")
    public BaseResponse<ModelConfigVO> getModelConfigVOById(long id, HttpServletRequest request) {
        ThrowUtils.throwIf(id <= 0, ErrorCode.PARAMS_ERROR);
        ModelConfig modelConfig = modelConfigService.getById(id);
        ThrowUtils.throwIf(modelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        User loginUser = userService.getLoginUser(request);
        if (!modelConfig.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限查看该模型配置");
        }
        return ResultUtils.success(modelConfigService.getModelConfigVO(modelConfig));
    }

    @PostMapping("/my/list/page/vo")
    public BaseResponse<Page<ModelConfigVO>> listMyModelConfigVOByPage(@RequestBody ModelConfigQueryRequest modelConfigQueryRequest,
                                                                        HttpServletRequest request) {
        ThrowUtils.throwIf(modelConfigQueryRequest == null, ErrorCode.PARAMS_ERROR);
        User loginUser = userService.getLoginUser(request);
        long pageNum = modelConfigQueryRequest.getPageNum();
        long pageSize = modelConfigQueryRequest.getPageSize();
        ThrowUtils.throwIf(pageSize > 20, ErrorCode.PARAMS_ERROR, "每页最多查询20条");
        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("userId", loginUser.getId())
                .eq("provider", modelConfigQueryRequest.getProvider())
                .like("modelName", modelConfigQueryRequest.getModelName())
                .eq("enabled", modelConfigQueryRequest.getEnabled())
                .orderBy("createTime", false);
        Page<ModelConfig> modelConfigPage = modelConfigService.page(Page.of(pageNum, pageSize), queryWrapper);
        Page<ModelConfigVO> modelConfigVOPage = new Page<>(pageNum, pageSize, modelConfigPage.getTotalRow());
        List<ModelConfigVO> modelConfigVOList = modelConfigService.getModelConfigVOList(modelConfigPage.getRecords());
        modelConfigVOPage.setRecords(modelConfigVOList);
        return ResultUtils.success(modelConfigVOPage);
    }

    @PostMapping("/list/page/vo")
    @AuthCheck(mustRole = UserConstant.ADMIN_ROLE)
    public BaseResponse<Page<ModelConfigVO>> listModelConfigVOByPage(@RequestBody ModelConfigQueryRequest modelConfigQueryRequest) {
        ThrowUtils.throwIf(modelConfigQueryRequest == null, ErrorCode.PARAMS_ERROR);
        long pageNum = modelConfigQueryRequest.getPageNum();
        long pageSize = modelConfigQueryRequest.getPageSize();
        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("provider", modelConfigQueryRequest.getProvider())
                .like("modelName", modelConfigQueryRequest.getModelName())
                .eq("enabled", modelConfigQueryRequest.getEnabled())
                .orderBy("createTime", false);
        Page<ModelConfig> modelConfigPage = modelConfigService.page(Page.of(pageNum, pageSize), queryWrapper);
        Page<ModelConfigVO> modelConfigVOPage = new Page<>(pageNum, pageSize, modelConfigPage.getTotalRow());
        List<ModelConfigVO> modelConfigVOList = modelConfigService.getModelConfigVOList(modelConfigPage.getRecords());
        modelConfigVOPage.setRecords(modelConfigVOList);
        return ResultUtils.success(modelConfigVOPage);
    }

    @PostMapping("/toggle/enabled")
    public BaseResponse<Boolean> toggleEnabled(@RequestBody DeleteRequest toggleRequest, HttpServletRequest request) {
        if (toggleRequest == null || toggleRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        modelConfigService.toggleEnabled(toggleRequest.getId(), loginUser);
        return ResultUtils.success(true);
    }

    @PostMapping("/set/default")
    public BaseResponse<Boolean> setDefault(@RequestBody DeleteRequest setDefaultRequest, HttpServletRequest request) {
        if (setDefaultRequest == null || setDefaultRequest.getId() <= 0) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        User loginUser = userService.getLoginUser(request);
        modelConfigService.setDefault(setDefaultRequest.getId(), loginUser);
        return ResultUtils.success(true);
    }

    @GetMapping("/internal/runtime")
    public BaseResponse<ModelConfigRuntimeVO> getRuntimeConfig(@RequestParam Long id,
                                                                @RequestParam Integer configVersion,
                                                                @RequestHeader(value = "X-Internal-Secret", required = false) String secret) {
        if (StrUtil.isNotBlank(internalSecret)) {
            ThrowUtils.throwIf(!internalSecret.equals(secret), ErrorCode.NO_AUTH_ERROR, "内部接口鉴权失败");
        }
        ThrowUtils.throwIf(id == null || id <= 0, ErrorCode.PARAMS_ERROR, "配置ID无效");
        ModelConfig modelConfig = modelConfigService.getById(id);
        ThrowUtils.throwIf(modelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        ThrowUtils.throwIf(modelConfig.getEnabled() == null || modelConfig.getEnabled() != 1, ErrorCode.PARAMS_ERROR, "模型配置未启用");
        ThrowUtils.throwIf(!modelConfig.getConfigVersion().equals(configVersion), ErrorCode.PARAMS_ERROR, "配置版本不匹配");
        ModelConfigRuntimeVO runtimeVO = new ModelConfigRuntimeVO();
        runtimeVO.setProvider(modelConfig.getProvider());
        runtimeVO.setModelName(modelConfig.getModelName());
        runtimeVO.setBaseUrl(modelConfig.getBaseUrl());
        runtimeVO.setApiKey(modelConfig.getApiKeyCipher());
        return ResultUtils.success(runtimeVO);
    }

    @Data
    public static class ModelConfigRuntimeVO implements Serializable {

        private String provider;

        private String modelName;

        private String baseUrl;

        private String apiKey;

        private static final long serialVersionUID = 1L;
    }
}
