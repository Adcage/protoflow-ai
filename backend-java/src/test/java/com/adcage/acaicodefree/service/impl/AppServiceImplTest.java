package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.service.AppService;
import com.adcage.acaicodefree.service.UserService;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

import jakarta.annotation.Resource;

@SpringBootTest
class AppServiceImplTest {

    @Resource
    private AppService appService;

    @Resource
    private UserService userService;

    @Test
    void testServicesShouldBeInjected() {
        Assertions.assertNotNull(appService, "AppService should be available");
        Assertions.assertNotNull(userService, "UserService should be available");
    }

    @Test
    void testGetAppByIdNotFound() {
        var app = appService.getById(-1L);
        Assertions.assertNull(app, "App should not exist for invalid ID");
    }
}
