package com.adcage.acaicodefree.controller;

import cn.hutool.json.JSONUtil;
import com.adcage.acaicodefree.constant.AppConstant;
import com.adcage.acaicodefree.constant.UserConstant;
import com.adcage.acaicodefree.grpc.client.GrpcPythonAgentRuntime;
import com.adcage.acaicodefree.model.entity.App;
import com.adcage.acaicodefree.model.entity.ChatHistory;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.runtime.CodeGenerationRequest;
import com.adcage.acaicodefree.mapper.AppMapper;
import com.adcage.acaicodefree.mapper.ChatHistoryMapper;
import com.adcage.acaicodefree.mapper.ChatSessionMapper;
import com.adcage.acaicodefree.mapper.UserMapper;
import com.adcage.acaicodefree.service.AgentRunService;
import com.adcage.acaicodefree.service.UserService;
import com.mybatisflex.core.query.QueryWrapper;
import jakarta.annotation.Resource;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import reactor.core.publisher.Flux;

import java.time.LocalDateTime;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.ByteArrayInputStream;
import java.util.List;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipEntry;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("local")
class AppChatE2ETest {

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
    private GrpcPythonAgentRuntime grpcPythonAgentRuntime;

    @MockBean
    private AgentRunService agentRunService;

    @MockBean
    private UserService userService;

    private User loginUser;

    private App testApp;

    @BeforeEach
    void setUp() {
        ensureChatSchema();
        when(agentRunService.createAgentRun(anyLong(), anyLong(), anyLong(), anyString())).thenReturn(999L);
        String suffix = String.valueOf(System.nanoTime());
        User user = User.builder()
                .userAccount("e2e_user_" + suffix)
                .userPassword("e2e_password_hash")
                .userName("E2E测试用户")
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
                .appName("E2E会话应用")
                .initPrompt("生成一个简单页面")
                .codeGenType(CodeGenTypeEnum.SINGLE_FILE.getValue())
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
    void chatFullChain_shouldCreateSessionStreamPersistAndQuery() throws Exception {
        when(grpcPythonAgentRuntime.getName()).thenReturn("python-agent");
        when(grpcPythonAgentRuntime.stream(any(CodeGenerationRequest.class)))
                .thenReturn(Flux.just("<div>", "hello</div>"));

        MvcResult createSessionResult = mockMvc.perform(post("/app/chat/session/create")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + "}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();

        Long sessionId = JSONUtil.parseObj(createSessionResult.getResponse().getContentAsString()).getLong("data");
        Assertions.assertNotNull(sessionId);

        MvcResult createSessionResult2 = mockMvc.perform(post("/app/chat/session/create")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + "}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        Long sessionId2 = JSONUtil.parseObj(createSessionResult2.getResponse().getContentAsString()).getLong("data");
        Assertions.assertNotNull(sessionId2);
        Assertions.assertNotEquals(sessionId, sessionId2);

        MvcResult streamResult = mockMvc.perform(post("/app/chat/gen/code/stream")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + ",\"sessionId\":" + sessionId + ",\"message\":\"请生成一个按钮\"}"))
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(streamResult))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    String sse = result.getResponse().getContentAsString();
                    Assertions.assertTrue(sse.contains("event:meta"));
                    Assertions.assertTrue(sse.contains("\"sessionId\":" + sessionId));
                    Assertions.assertTrue(sse.contains("event:done"));
                });

        MvcResult listResult = mockMvc.perform(get("/app/chat/session/list")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .param("appId", String.valueOf(testApp.getId())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();

        String listBody = listResult.getResponse().getContentAsString();
        String title1 = null;
        String title2 = null;
        Integer messageCount1 = null;
        for (Object item : JSONUtil.parseObj(listBody).getJSONArray("data")) {
            if (item == null) {
                continue;
            }
            Long id = JSONUtil.parseObj(item).getLong("id");
            if (sessionId.equals(id)) {
                title1 = JSONUtil.parseObj(item).getStr("title");
                messageCount1 = JSONUtil.parseObj(item).getInt("messageCount");
            }
            if (sessionId2.equals(id)) {
                title2 = JSONUtil.parseObj(item).getStr("title");
            }
        }
        Assertions.assertNotNull(title1);
        Assertions.assertNotNull(title2);
        Assertions.assertEquals(1, messageCount1);
        Assertions.assertNotEquals(title1, title2, "新建会话标题不应重复");

        mockMvc.perform(post("/app/chat/history/page")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
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

    @Test
    void chatFullChain_vueProject_shouldUseJsonSseAndPersistReadableHistory() throws Exception {
        testApp.setCodeGenType(CodeGenTypeEnum.VUE_PROJECT.getValue());
        appMapper.update(testApp);

        String toolArguments = "{\"relativeFilePath\":\"src/main.js\"}";
        when(grpcPythonAgentRuntime.getName()).thenReturn("python-agent");
        when(grpcPythonAgentRuntime.stream(any(CodeGenerationRequest.class)))
                .thenReturn(Flux.just(
                        "{\"type\":\"ai_response\",\"data\":\"开始生成 Vue 工程\"}",
                        "{\"type\":\"tool_request\",\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":" + JSONUtil.quote(toolArguments) + "}",
                        "{\"type\":\"tool_executed\",\"id\":\"t1\",\"name\":\"writeFile\",\"arguments\":" + JSONUtil.quote(toolArguments) + ",\"result\":\"文件写入成功：src/main.js\"}"
                ));

        MvcResult createSessionResult = mockMvc.perform(post("/app/chat/session/create")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + "}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        Long sessionId = JSONUtil.parseObj(createSessionResult.getResponse().getContentAsString()).getLong("data");
        Assertions.assertNotNull(sessionId);

        MvcResult streamResult = mockMvc.perform(post("/app/chat/gen/code/stream")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + ",\"sessionId\":" + sessionId + ",\"message\":\"请生成一个 Vue 首页\"}"))
                .andExpect(request().asyncStarted())
                .andReturn();

        mockMvc.perform(asyncDispatch(streamResult))
                .andExpect(status().isOk())
                .andExpect(result -> {
                    String sse = result.getResponse().getContentAsString();
                    Assertions.assertTrue(sse.contains("event:meta"));
                    Assertions.assertTrue(sse.contains("event:done"));
                    Assertions.assertTrue(sse.contains("\\\"type\\\":\\\"ai_response\\\""));
                    Assertions.assertTrue(sse.contains("\\\"type\\\":\\\"tool_request\\\""));
                    Assertions.assertTrue(sse.contains("\\\"type\\\":\\\"tool_executed\\\""));
                });

        mockMvc.perform(post("/app/chat/history/page")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
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
    }

    @Test
    void deploy_shouldReturnStaticUrlWithPortAndContextPath() throws Exception {
        Path outputDir = Path.of(AppConstant.CODE_OUTPUT_ROOT_DIR)
                .resolve(CodeGenTypeEnum.SINGLE_FILE.getValue() + "_" + testApp.getId());
        Files.createDirectories(outputDir);
        Files.writeString(outputDir.resolve("index.html"), "<html><body>ok</body></html>", StandardCharsets.UTF_8);

        mockMvc.perform(post("/app/deploy")
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"appId\":" + testApp.getId() + "}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data").value(org.hamcrest.Matchers.startsWith("http://localhost:8700/api/static/")));
    }

    @Test
    void downloadProject_shouldReturnZipBinary() throws Exception {
        Path outputDir = Path.of(AppConstant.CODE_OUTPUT_ROOT_DIR)
                .resolve(CodeGenTypeEnum.SINGLE_FILE.getValue() + "_" + testApp.getId());
        Files.createDirectories(outputDir);
        Files.writeString(outputDir.resolve("index.html"), "<html><body>download</body></html>", StandardCharsets.UTF_8);
        Files.writeString(outputDir.resolve(".env"), "SECRET=1", StandardCharsets.UTF_8);

        MvcResult mvcResult = mockMvc.perform(get("/app/download/{appId}", testApp.getId())
                        .sessionAttr(UserConstant.USER_LOGIN_STATE, loginUser))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Type", "application/zip"))
                .andReturn();

        byte[] zipBytes = mvcResult.getResponse().getContentAsByteArray();
        Assertions.assertTrue(zipBytes.length > 0);
        boolean containsIndex = false;
        boolean containsEnv = false;
        try (ZipInputStream zipInputStream = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
            ZipEntry zipEntry;
            while ((zipEntry = zipInputStream.getNextEntry()) != null) {
                if (zipEntry.getName().endsWith("index.html")) {
                    containsIndex = true;
                }
                if (zipEntry.getName().contains(".env")) {
                    containsEnv = true;
                }
            }
        }
        Assertions.assertTrue(containsIndex);
        Assertions.assertFalse(containsEnv);
    }
}
