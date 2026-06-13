package com.adcage.acaicodefree.service.impl;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.collection.CollUtil;
import cn.hutool.core.util.StrUtil;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.mapper.ModelConfigMapper;
import com.adcage.acaicodefree.model.entity.ModelConfig;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.modelconfig.ModelConfigVO;
import com.adcage.acaicodefree.service.ModelConfigEventPublisher;
import com.adcage.acaicodefree.service.ModelConfigService;
import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.spring.service.impl.ServiceImpl;
import jakarta.annotation.Resource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class ModelConfigServiceImpl extends ServiceImpl<ModelConfigMapper, ModelConfig> implements ModelConfigService {

    @Resource
    private ModelConfigEventPublisher modelConfigEventPublisher;

    @Value("${langchain4j.open-ai.chat-model.base-url:}")
    private String defaultBaseUrl;

    @Value("${langchain4j.open-ai.chat-model.api-key:}")
    private String defaultApiKey;

    @Value("${langchain4j.open-ai.chat-model.model-name:}")
    private String defaultModelName;

    @Override
    public void validModelConfig(ModelConfig modelConfig, boolean add) {
        if (modelConfig == null) {
            throw new BusinessException(ErrorCode.PARAMS_ERROR);
        }
        if (add) {
            ThrowUtils.throwIf(StrUtil.isBlank(modelConfig.getProvider()), ErrorCode.PARAMS_ERROR, "供应商不能为空");
            ThrowUtils.throwIf(StrUtil.isBlank(modelConfig.getModelName()), ErrorCode.PARAMS_ERROR, "模型名称不能为空");
            ThrowUtils.throwIf(StrUtil.isBlank(modelConfig.getBaseUrl()), ErrorCode.PARAMS_ERROR, "接口地址不能为空");
            ThrowUtils.throwIf(StrUtil.isBlank(modelConfig.getApiKeyCipher()), ErrorCode.PARAMS_ERROR, "API密钥不能为空");
        }
    }

    @Override
    public ModelConfigVO getModelConfigVO(ModelConfig modelConfig) {
        if (modelConfig == null) {
            return null;
        }
        ModelConfigVO modelConfigVO = new ModelConfigVO();
        BeanUtil.copyProperties(modelConfig, modelConfigVO);
        return modelConfigVO;
    }

    @Override
    public List<ModelConfigVO> getModelConfigVOList(List<ModelConfig> modelConfigList) {
        if (CollUtil.isEmpty(modelConfigList)) {
            return new ArrayList<>();
        }
        return modelConfigList.stream().map(this::getModelConfigVO).toList();
    }

    @Override
    public void incrementConfigVersion(Long id) {
        ModelConfig modelConfig = this.getById(id);
        ThrowUtils.throwIf(modelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        ModelConfig update = new ModelConfig();
        update.setId(id);
        update.setConfigVersion(modelConfig.getConfigVersion() + 1);
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "更新配置版本失败");
        modelConfigEventPublisher.publishConfigUpdated(modelConfig);
    }

    @Override
    public ModelConfig getDefaultEnabledModelConfig(Long userId) {
        QueryWrapper defaultQuery = QueryWrapper.create()
                .eq("userId", userId)
                .eq("enabled", 1)
                .eq("isDefault", 1)
                .limit(1);
        ModelConfig defaultConfig = mapper.selectOneByQuery(defaultQuery);
        if (defaultConfig != null) {
            return defaultConfig;
        }
        QueryWrapper fallbackQuery = QueryWrapper.create()
                .eq("userId", userId)
                .eq("enabled", 1)
                .orderBy("updateTime", false)
                .limit(1);
        ModelConfig userConfig = mapper.selectOneByQuery(fallbackQuery);
        if (userConfig != null) {
            return userConfig;
        }
        return buildServerDefaultConfig();
    }

    private ModelConfig buildServerDefaultConfig() {
        if (StrUtil.isBlank(defaultBaseUrl) || StrUtil.isBlank(defaultApiKey) || StrUtil.isBlank(defaultModelName)) {
            return null;
        }
        return ModelConfig.builder()
                .provider("openai")
                .modelName(defaultModelName)
                .baseUrl(defaultBaseUrl)
                .apiKeyCipher(defaultApiKey)
                .temperature(0.7)
                .maxTokens(8192)
                .configVersion(0)
                .enabled(1)
                .isDefault(1)
                .build();
    }

    @Override
    public ModelConfig getServerDefaultConfig() {
        return buildServerDefaultConfig();
    }

    @Override
    public void toggleEnabled(Long id, User loginUser) {
        ModelConfig modelConfig = this.getById(id);
        ThrowUtils.throwIf(modelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        if (!modelConfig.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限操作该模型配置");
        }
        int newEnabled = modelConfig.getEnabled() == 1 ? 0 : 1;
        ModelConfig update = new ModelConfig();
        update.setId(id);
        update.setEnabled(newEnabled);
        if (newEnabled == 0 && Integer.valueOf(1).equals(modelConfig.getIsDefault())) {
            update.setIsDefault(0);
        }
        boolean result = this.updateById(update);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "切换启用状态失败");
    }

    @Override
    public void setDefault(Long id, User loginUser) {
        ModelConfig modelConfig = this.getById(id);
        ThrowUtils.throwIf(modelConfig == null, ErrorCode.NOT_FOUND_ERROR, "模型配置不存在");
        if (!modelConfig.getUserId().equals(loginUser.getId()) && !UserConstant.ADMIN_ROLE.equals(loginUser.getUserRole())) {
            throw new BusinessException(ErrorCode.NO_AUTH_ERROR, "无权限操作该模型配置");
        }
        QueryWrapper clearQuery = QueryWrapper.create()
                .eq("userId", modelConfig.getUserId())
                .eq("isDefault", 1);
        List<ModelConfig> defaultConfigs = mapper.selectListByQuery(clearQuery);
        for (ModelConfig dc : defaultConfigs) {
            ModelConfig clearUpdate = new ModelConfig();
            clearUpdate.setId(dc.getId());
            clearUpdate.setIsDefault(0);
            this.updateById(clearUpdate);
        }
        ModelConfig setUpdate = new ModelConfig();
        setUpdate.setId(id);
        setUpdate.setIsDefault(1);
        boolean result = this.updateById(setUpdate);
        ThrowUtils.throwIf(!result, ErrorCode.OPERATION_ERROR, "设置默认配置失败");
    }
}
