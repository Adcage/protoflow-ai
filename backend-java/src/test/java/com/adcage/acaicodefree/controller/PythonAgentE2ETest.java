package com.adcage.acaicodefree.controller;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.ai.model.message.AiResponseMessage;
import com.adcage.acaicodefree.ai.model.message.ToolExecutedMessage;
import com.adcage.acaicodefree.ai.model.message.ToolRequestMessage;
import com.adcage.acaicodefree.grpc.client.GrpcPythonAgentRuntime;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.mapper.UserMapper;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.UserService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("local")
@TestPropertySource(properties = {
        "agent.runtime=python-agent"
})
class PythonAgentE2ETest {

    @Resource
    private MockMvc mockMvc;

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
    private AgentRunService agentRunService;

    @MockBean
    private UserService userService;

    @MockBean
    private GrpcPythonAgentRuntime grpcPythonAgentRuntime;

    private User loginUser;

    private App testApp;

    @BeforeEach
    void setUp() throws Exception {
        ensureChatSchema();

        when(agentRunService.createAgentRun(anyLong(), anyLong(), anyLong(), anyString())).thenReturn(999L);
        when(grpcPythonAgentRuntime.getName()).thenReturn("python-agent");
        when(grpcPythonAgentRuntime.stream(any(CodeGenerationRequest.class))).thenReturn(Flux.just(
                JSONUtil.toJsonStr(new AiResponseMessage("开始生成 Vue 工程")),
                JSONUtil.toJsonStr(new ToolRequestMessage("tool-1", "write_file", "{\"path\":\"src/App.vue\"}")),
                JSONUtil.toJsonStr(new ToolExecutedMessage("tool-1", "write_file", "{\"path\":\"src/App.vue\"}", "写入成功: src/App.vue")),
                JSONUtil.toJsonStr(new AiResponseMessage("completed"))
        ));

        String suffix = String.valueOf(System.nanoTime());
        User user = User.builder()
                .userAccount("pyagent_e2e_" + suffix)
                .userPassword("e2e_password_hash")
                .userName("Python Agent E2E测试用户")
                .userRole(UserConstant.DEFAULT_ROLE)
                .editTime(LocalDateTime.now())
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .isDelete(0)
                .build();
        userMapper.insert(user);
        this.loginUser = user;

        when(userService.getLoginUser(any())).thenReturn(loginUser);
        when(userService.getLoginUserPermitNull(any())).thenReturn(loginUser);
        when(userService.getById(loginUser.getId())).thenReturn(loginUser);

        App app = App.builder()
                .appName("Python Agent E2E应用")
                .initPrompt("生成一个Vue首页")
                .codeGenType(CodeGenTypeEnum.VUE_PROJECT.getValue())
                .isTestApp(0)
                .userId(user.getId())
                .priority(0)
                .editTime(LocalDateTime.now())
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .isDelete(0)
                .build();
        appMapper.insert(app);
        this.testApp = app;
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
                  isDelete TINYINT DEFAULT 0 NOT NULL,
                  INDEX idx_userId_appId_updateTime (userId, appId, updateTime),
                  INDEX idx_appId_lastMessageTime (appId, lastMessageTime)
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
                  latencyMs INT NULL,
                  requestId VARCHAR(64) NULL,
                  extra JSON NULL,
                  createTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                  updateTime DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP,
                  isDelete TINYINT DEFAULT 0 NOT NULL,
                  UNIQUE KEY uk_sessionId_seqNo (sessionId, seqNo),
                  INDEX idx_sessionId_createTime (sessionId, createTime),
                  INDEX idx_userId_appId_createTime (userId, appId, createTime),
                  INDEX idx_appId_createTime (appId, createTime)
                )
                """);
        ensureHistoryColumn("sessionId", "ALTER TABLE chat_history ADD COLUMN sessionId BIGINT NOT NULL DEFAULT 0");
        ensureHistoryColumn("seqNo", "ALTER TABLE chat_history ADD COLUMN seqNo INT NOT NULL DEFAULT 0");
        ensureHistoryColumn("status", "ALTER TABLE chat_history ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'success'");
        ensureHistoryColumn("modelName", "ALTER TABLE chat_history ADD COLUMN modelName VARCHAR(128) NULL");
        ensureHistoryColumn("latencyMs", "ALTER TABLE chat_history ADD COLUMN latencyMs INT NULL");
        ensureHistoryColumn("requestId", "ALTER TABLE chat_history ADD COLUMN requestId VARCHAR(64) NULL");
        ensureHistoryColumn("extra", "ALTER TABLE chat_history ADD COLUMN extra JSON NULL");
    }

    private void ensureHistoryColumn(String columnName, String alterSql) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'chat_history' AND column_name = ?",
                Long.class,
                columnName
        );
        if (count == null || count == 0) {
            jdbcTemplate.execute(alterSql);
        }
    }

    @Test
    void pythonAgentFullChain_shouldStreamAndPersistHistory() throws Exception {
        MvcResult createSessionResult = mockMvc.perform(post("/app/chat/session/create")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + "}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();

        Long sessionId = JSONUtil.parseObj(createSessionResult.getResponse().getContentAsString()).getLong("data");
        Assertions.assertNotNull(sessionId);

        MvcResult streamResult = mockMvc.perform(post("/app/chat/gen/code/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + ",\"sessionId\":" + sessionId + ",\"message\":\"请生成一个Vue首页\"}"))
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(streamResult))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    String sse = result.getResponse().getContentAsString();
                    Assertions.assertTrue(sse.contains("event:meta"), "应包含 meta 事件");
                    Assertions.assertTrue(sse.contains("\"sessionId\":" + sessionId), "meta 应包含 sessionId");
                    Assertions.assertTrue(sse.contains("event:done"), "应包含 done 事件");
                    Assertions.assertTrue(sse.contains("ai_response"), "应包含 ai_response 类型");
                    Assertions.assertTrue(sse.contains("tool_request"), "应包含 tool_request 类型");
                    Assertions.assertTrue(sse.contains("tool_executed"), "应包含 tool_executed 类型");
                    Assertions.assertTrue(sse.contains("write_file"), "tool 事件应包含工具名称");
                    Assertions.assertTrue(sse.contains("src/App.vue"), "tool 事件应包含文件路径");
                });

        mockMvc.perform(post("/app/chat/history/page")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + ",\"sessionId\":" + sessionId + ",\"pageNum\":1,\"pageSize\":10}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.totalRow").value(1))
                .andExpect(jsonPath("$.data.records[0].messageType").value("user"));

        List<ChatHistory> historyList = chatHistoryMapper.selectListByQuery(QueryWrapper.create()
                .eq("sessionId", sessionId)
                .orderBy("seqNo", true));
        Assertions.assertEquals(1, historyList.size());
        Assertions.assertEquals(1, historyList.get(0).getSeqNo());
    }
}
