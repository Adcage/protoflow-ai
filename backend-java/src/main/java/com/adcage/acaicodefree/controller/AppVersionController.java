package com.adcage.acaicodefree.controller;

import cn.hutool.core.bean.BeanUtil;
import com.adcage.acaicodefree.common.BaseResponse;
import com.adcage.acaicodefree.common.ErrorCode;
import com.adcage.acaicodefree.common.ResultUtils;
import com.adcage.acaicodefree.exception.ThrowUtils;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.AppVersion;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.app.AppVersionVO;
import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.AppVersionService;
import com.adcage.acaicodefree.service.UserService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/app-version")
public class AppVersionController {

    @Resource
    private AppVersionService appVersionService;

    @Resource
    private AppService appService;

    @Resource
    private UserService userService;

    @GetMapping("/list")
    public BaseResponse<List<AppVersionVO>> listVersions(@RequestParam Long appId,
                                                          @RequestParam(required = false, defaultValue = "20") int limit,
                                                          HttpServletRequest request) {
        ThrowUtils.throwIf(appId == null || appId <= 0, ErrorCode.PARAMS_ERROR, "应用 ID 无效");
        User loginUser = userService.getLoginUser(request);
        App app = appService.getById(appId);
        ThrowUtils.throwIf(app == null, ErrorCode.NOT_FOUND_ERROR, "应用不存在");
        boolean isAdmin = "admin".equals(loginUser.getUserRole());
        ThrowUtils.throwIf(!isAdmin && !app.getUserId().equals(loginUser.getId()), ErrorCode.NO_AUTH_ERROR, "无权查看此应用版本");

        QueryWrapper queryWrapper = QueryWrapper.create()
                .eq("appId", appId)
                .orderBy("versionNo", false)
                .limit(limit);
        List<AppVersion> versions = appVersionService.list(queryWrapper);
        List<AppVersionVO> voList = versions.stream().map(v -> {
            AppVersionVO vo = new AppVersionVO();
            BeanUtil.copyProperties(v, vo);
            return vo;
        }).collect(Collectors.toList());
        return ResultUtils.success(voList);
    }
}
