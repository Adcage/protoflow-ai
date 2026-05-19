package com.adcage.acaicodefree.workflow.controller;

import com.adcage.acaicodefree.workflow.service.WorkflowCodeGeneratorService;
import com.adcage.acaicodefree.workflow.service.WorkflowStreamEvent;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import reactor.core.publisher.Flux;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class WorkflowSseControllerTest {

    @jakarta.annotation.Resource
    private MockMvc mockMvc;

    @MockBean
    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @Test
    void streamShouldReturnNamedWorkflowEvents() {
        when(workflowCodeGeneratorService.executeWorkflowEventFlux(1L, "做一个产品网站"))
                .thenReturn(Flux.just(
                        new WorkflowStreamEvent("workflow_start", "{\"step\":\"start\"}"),
                        new WorkflowStreamEvent("step_completed", "{\"step\":\"image_collect\"}"),
                        new WorkflowStreamEvent("workflow_completed", "{\"step\":\"done\"}")
                ));

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
            org.junit.jupiter.api.Assertions.assertTrue(body.contains("event:workflow_start"));
            org.junit.jupiter.api.Assertions.assertTrue(body.contains("event:step_completed"));
            org.junit.jupiter.api.Assertions.assertTrue(body.contains("event:workflow_completed"));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
