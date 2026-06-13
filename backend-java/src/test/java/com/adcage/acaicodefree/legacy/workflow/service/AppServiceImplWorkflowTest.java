package com.adcage.acaicodefree.legacy.workflow.service;

import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.legacy.core.AiCodeGeneratorFacade;
import com.adcage.acaicodefree.core.handler.StreamHandlerExecutor;
import com.adcage.acaicodefree.exception.BusinessException;
import com.adcage.acaicodefree.service.impl.AppServiceImpl;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.mapper.UserMapper;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatSession;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntime;
import com.adcage.acaicodefree.runtime.CodeGenerationRuntimeRouter;
import com.adcage.acaicodefree.config.properties.WorkspaceProperties;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.ModelConfigService;
import com.adcage.acaicodefree.legacy.workflow.config.WorkflowProperties;
import com.adcage.acaicodefree.legacy.workflow.service.WorkflowCodeGeneratorService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@SpringBootTest(properties = "grpc.server.port=0")
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

    @Resource
    private CodeGenerationRuntimeRouter codeGenerationRuntimeRouter;

    @MockBean
    private AiCodeGeneratorFacade aiCodeGeneratorFacade;

    @MockBean
    private WorkflowCodeGeneratorService workflowCodeGeneratorService;

    @MockBean
    private StreamHandlerExecutor streamHandlerExecutor;

    @MockBean
    private AgentRunService agentRunService;

    @MockBean
    private ModelConfigService modelConfigService;

    private User loginUser;
    private App testApp;
    private ChatSession testSession;

    @BeforeEach
    void setUp() {
        ensureChatSchema();
        workflowProperties.setEnabled(false);
        workflowProperties.setMode("legacy");
        ReflectionTestUtils.setField(codeGenerationRuntimeRouter, "runtimeName", "python-agent");
        ReflectionTestUtils.setField(codeGenerationRuntimeRouter, "runtimes",
                List.of(new StubRuntime("python-agent", Flux.just("python_start", "python_completed"))));
        when(agentRunService.createAgentRun(anyLong(), anyLong(), anyLong(), anyString())).thenReturn(999L);
        when(agentRunService.createAgentRun(anyLong(), anyLong(), anyLong(), anyString(), any(), any(), any())).thenReturn(999L);
        when(modelConfigService.getDefaultEnabledModelConfig(anyLong())).thenReturn(null);
        when(streamHandlerExecutor.handle(any(), any(), any())).thenAnswer(invocation -> invocation.getArgument(1));

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
    void chatToGenCodeWhenJavaAgentShouldFailFast() {
        ReflectionTestUtils.setField(codeGenerationRuntimeRouter, "runtimeName", "java-agent");

        BusinessException exception = assertThrows(BusinessException.class,
                () -> appService.chatToGenCode(testApp.getId(), testSession.getId(), "帮我做一个官网", loginUser));

        org.junit.jupiter.api.Assertions.assertTrue(exception.getMessage().contains("Java AI runtime 已禁用"));
        verify(workflowCodeGeneratorService, never()).executeWorkflowWithFlux(anyLong(), anyString());
    }

    @Test
    void chatToGenCodeWhenPythonAgentShouldNotUseWorkflowService() {
        ReflectionTestUtils.setField(codeGenerationRuntimeRouter, "runtimeName", "python-agent");

        List<String> result = appService.chatToGenCode(testApp.getId(), testSession.getId(), "帮我做一个单页", loginUser)
                .collectList()
                .block();

        assertEquals(List.of("python_start", "python_completed"), result);
        verify(workflowCodeGeneratorService, never()).executeWorkflowWithFlux(anyLong(), anyString());
    }

    private record StubRuntime(String name, Flux<String> stream) implements CodeGenerationRuntime {
        @Override
        public String getName() {
            return name;
        }

        @Override
        public Flux<String> stream(CodeGenerationRequest request) {
            return stream;
        }
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
