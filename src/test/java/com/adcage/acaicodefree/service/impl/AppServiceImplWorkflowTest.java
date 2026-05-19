package com.adcage.acaicodefree.service.impl;

import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.core.handler.StreamHandlerExecutor;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.mapper.UserMapper;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatSession;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.workflow.config.WorkflowProperties;
import com.adcage.acaicodefree.workflow.service.WorkflowCodeGeneratorService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.jdbc.core.JdbcTemplate;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@SpringBootTest
class AppServiceImplWorkflowTest {

    @Resource
    private AppServiceImpl appService;

    @Resource
    private WorkflowProperties workflowProperties;

    @Resource
    private UserMapper userMapper;

    @Resource
    private AppMapper appMapper;

    @Resource
    private ChatSessionMapper chatSessionMapper;

    @Resource
    private ChatHistoryMapper chatHistoryMapper;

    @Resource
    private JdbcTemplate jdbcTemplate;

    @MockBean
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    @MockBean
    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @MockBean
    private StreamHandlerExecutor streamHandlerExecutor;

    private User loginUser;
    private App testApp;
    private ChatSession testSession;

    @BeforeEach
    void setUp() {
        ensureChatSchema();
        workflowProperties.setEnabled(false);
        workflowProperties.setMode("legacy");

        String suffix = String.valueOf(System.nanoTime());
        loginUser = User.builder()
                .userAccount("workflow_user_" + suffix)
                .userPassword("password")
                .userName("Workflow测试用户")
                .userRole(UserConstant.DEFAULT_ROLE)
                .editTime(LocalDateTime.now())
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .isDelete(0)
                .build();
        userMapper.insert(loginUser);

        testApp = App.builder()
                .appName("Workflow接入测试应用")
                .initPrompt("生成页面")
                .codeGenType(CodeGenTypeEnum.SINGLE_FILE.getValue())
                .userId(loginUser.getId())
                .priority(0)
                .editTime(LocalDateTime.now())
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .isDelete(0)
                .build();
        appMapper.insert(testApp);

        testSession = ChatSession.builder()
                .appId(testApp.getId())
                .userId(loginUser.getId())
                .title("会话1")
                .messageCount(0)
                .modelName(testApp.getCodeGenType())
                .lastMessageTime(LocalDateTime.now())
                .build();
        chatSessionMapper.insert(testSession);
    }

    @AfterEach
    void tearDown() {
        if (testApp != null && testApp.getId() != null) {
            chatHistoryMapper.deleteByQuery(QueryWrapper.create().eq("appId", testApp.getId()));
            chatSessionMapper.deleteByQuery(QueryWrapper.create().eq("appId", testApp.getId()));
            appMapper.deleteByQuery(QueryWrapper.create().eq("id", testApp.getId()));
        }
        if (loginUser != null && loginUser.getId() != null) {
            userMapper.deleteByQuery(QueryWrapper.create().eq("id", loginUser.getId()));
        }
    }

    @Test
    void chatToGenCodeWhenWorkflowEnabledShouldUseWorkflowService() {
        workflowProperties.setEnabled(true);
        workflowProperties.setMode("workflow");
        when(workflowCodeGeneratorService.executeWorkflowWithFlux(anyLong(), anyString()))
                .thenReturn(Flux.just("workflow_start", "workflow_completed"));

        List<String> result = appService.chatToGenCode(testApp.getId(), testSession.getId(), "帮我做一个官网", loginUser)
                .collectList()
                .block();

        assertEquals(List.of("workflow_start", "workflow_completed"), result);
        verify(workflowCodeGeneratorService).executeWorkflowWithFlux(testApp.getId(), "帮我做一个官网");
        verify(aiCodeGeneratorFacade, never()).generateAndSaveCodeStream(anyString(), any(), anyLong());
    }

    @Test
    void chatToGenCodeWhenWorkflowDisabledShouldUseLegacyFacade() {
        workflowProperties.setEnabled(false);
        workflowProperties.setMode("legacy");
        Flux<String> sourceFlux = Flux.just("legacy_chunk");
        when(aiCodeGeneratorFacade.generateAndSaveCodeStream(anyString(), any(), anyLong())).thenReturn(sourceFlux);
        when(streamHandlerExecutor.handle(any(), any(), any())).thenAnswer(invocation -> invocation.getArgument(1));

        List<String> result = appService.chatToGenCode(testApp.getId(), testSession.getId(), "帮我做一个单页", loginUser)
                .collectList()
                .block();

        assertEquals(List.of("legacy_chunk"), result);
        verify(aiCodeGeneratorFacade).generateAndSaveCodeStream("帮我做一个单页", CodeGenTypeEnum.SINGLE_FILE, testApp.getId());
        verify(workflowCodeGeneratorService, never()).executeWorkflowWithFlux(anyLong(), anyString());
    }

    private void ensureChatSchema() {
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS chat_session (
                  id BIGINT PRIMARY KEY,
                  appId BIGINT NOT NULL,
                  userId BIGINT NOT NULL,
                  title VARCHAR(256) NULL,
                  messageCount INT DEFAULT 0 NOT NULL,
                  modelName VARCHAR(128) NULL,
                  lastMessageTime DATETIME NULL,
                  createTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                  updateTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
                  isDelete TINYINT DEFAULT 0 NOT NULL
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                  id BIGINT PRIMARY KEY,
                  sessionId BIGINT NOT NULL,
                  seqNo INT NOT NULL,
                  message MEDIUMTEXT NOT NULL,
                  messageType VARCHAR(32) NOT NULL,
                  status VARCHAR(16) NOT NULL DEFAULT 'success',
                  appId BIGINT NOT NULL,
                  userId BIGINT NOT NULL,
                  modelName VARCHAR(128) NULL,
                  inputTokens INT NOT NULL DEFAULT 0,
                  outputTokens INT NOT NULL DEFAULT 0,
                  latencyMs INT NULL,
                  requestId VARCHAR(64) NULL,
                  extra JSON NULL,
                  createTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                  updateTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
                  isDelete TINYINT DEFAULT 0 NOT NULL
                )
                """);
    }
}
