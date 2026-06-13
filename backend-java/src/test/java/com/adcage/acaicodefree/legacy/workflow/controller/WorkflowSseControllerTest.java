package com.adcage.acaicodefree.legacy.workflow.controller;

import com.adcage.acaicodefree.legacy.workflow.service.WorkflowCodeGeneratorService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class WorkflowSseControllerTest {

    private MockMvc mockMvc;

    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @BeforeEach
    void setUp() {
        workflowCodeGeneratorService = org.mockito.Mockito.mock(WorkflowCodeGeneratorService.class);
        mockMvc = MockMvcBuilders.standaloneSetup(new WorkflowSseController()).build();
    }

    @Test
    void streamShouldReturnDisabledEventWithoutCallingJavaWorkflow() {
        try {
            MvcResult mvcResult = mockMvc.perform(get("/workflow/sse/execute")
                            .param("appId", "1")
                            .param("message", "做一个产品网站")
                            .accept(MediaType.TEXT_EVENT_STREAM))
                    .andExpect(request().asyncStarted())
                    .andReturn();

            MvcResult asyncResult = mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch(mvcResult))
                    .andExpect(status().isOk())
                    .andReturn();

            String body = asyncResult.getResponse().getContentAsString();
            org.junit.jupiter.api.Assertions.assertTrue(body.contains("event:business-error"));
            org.junit.jupiter.api.Assertions.assertTrue(body.contains("\"code\":50001"));
            org.mockito.Mockito.verifyNoInteractions(workflowCodeGeneratorService);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
