CREATE DATABASE IF NOT EXISTS ac_ai_code_free;

USE ac_ai_code_free;

-- 用户表
CREATE TABLE IF NOT EXISTS user
(
    id            BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    userAccount   VARCHAR(256)                           NOT NULL COMMENT '账号',
    userPassword  VARCHAR(512)                           NOT NULL COMMENT '密码',
    userName      VARCHAR(256)                           NULL COMMENT '用户昵称',
    userAvatar    VARCHAR(512)                           NULL COMMENT '用户头像',
    userProfile   VARCHAR(1024)                          NULL COMMENT '用户简介',
    userRole      VARCHAR(256) DEFAULT 'user'            NOT NULL COMMENT '用户角色：user/admin',
    editTime      DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '编辑时间',
    createTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete      TINYINT      DEFAULT 0                 NOT NULL COMMENT '是否删除',
    -- 会员相关信息，后续可以尝试单开表
    vipExpireTime DATETIME                               NULL COMMENT '会员过期时间',
    vipCode       VARCHAR(128)                           NULL COMMENT '会员兑换码',
    vipNumber     BIGINT                                 NULL COMMENT '会员编号',
    -- 用户邀请相关信息，后续可以尝试单开表
    shareCode     VARCHAR(20)                            NULL COMMENT '分享码',
    inviteUser    BIGINT                                 NULL COMMENT '邀请用户',
    UNIQUE KEY uk_userAccount (userAccount),
    INDEX idx_userName (userName)
) COMMENT '用户' COLLATE = utf8mb4_unicode_ci;


-- 应用表
CREATE TABLE app
(
    id           BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    appName      VARCHAR(256)                       NULL COMMENT '应用名称',
    cover        VARCHAR(512)                       NULL COMMENT '应用封面',
    initPrompt   TEXT                               NULL COMMENT '应用初始化的 prompt',
    codeGenType   VARCHAR(64)                        NULL COMMENT '代码生成类型（枚举）',
    styleTemplate VARCHAR(64)                        NULL COMMENT '风格模板',
    deployKey     VARCHAR(64)                        NULL COMMENT '部署标识',
    deployedTime DATETIME                           NULL COMMENT '部署时间',
    -- 99为精选应用，用于主页展示高质量的应用，使用整型而不是用枚举利于拓展
    priority     INT      DEFAULT 0                 NOT NULL COMMENT '优先级',
    userId       BIGINT                             NOT NULL COMMENT '创建用户id',
    editTime     DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '编辑时间',
    createTime   DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime   DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete     TINYINT  DEFAULT 0                 NOT NULL COMMENT '是否删除',
    UNIQUE KEY uk_deployKey (deployKey), -- 确保部署标识唯一
    INDEX idx_appName (appName),         -- 提升基于应用名称的查询性能
    INDEX idx_userId (userId)            -- 提升基于用户 ID 的查询性能
) COMMENT '应用' COLLATE = utf8mb4_unicode_ci;

-- 对话会话表
CREATE TABLE IF NOT EXISTS chat_session
(
    id              BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    appId           BIGINT                               NOT NULL COMMENT '应用id',
    userId          BIGINT                               NOT NULL COMMENT '创建用户id',
    title           VARCHAR(256)                         NULL COMMENT '会话标题',
    messageCount    INT        DEFAULT 0                 NOT NULL COMMENT '消息数',
    modelName       VARCHAR(128)                         NULL COMMENT '模型名称',
    lastMessageTime DATETIME                             NULL COMMENT '最后消息时间',
    createTime      DATETIME   DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime      DATETIME   DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete        TINYINT    DEFAULT 0                 NOT NULL COMMENT '是否删除',
    INDEX idx_userId_appId_updateTime (userId, appId, updateTime),
    INDEX idx_appId_lastMessageTime (appId, lastMessageTime)
) COMMENT '对话会话' COLLATE = utf8mb4_unicode_ci;

-- 对话历史表
CREATE TABLE IF NOT EXISTS chat_history
(
    id           BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    sessionId    BIGINT                               NOT NULL COMMENT '会话id',
    seqNo        INT                                  NOT NULL COMMENT '会话内消息序号，从1开始',
    message      MEDIUMTEXT                           NOT NULL COMMENT '消息',
    messageType  VARCHAR(32)                          NOT NULL COMMENT 'user/ai/system/tool',
    status       VARCHAR(16) DEFAULT 'success'        NOT NULL COMMENT '消息状态：success/failed',
    appId        BIGINT                               NOT NULL COMMENT '应用id',
    userId       BIGINT                               NOT NULL COMMENT '创建用户id',
    modelName    VARCHAR(128)                         NULL COMMENT '模型名称',
    inputTokens  INT        DEFAULT 0                 NOT NULL COMMENT '输入 token 数',
    outputTokens INT        DEFAULT 0                 NOT NULL COMMENT '输出 token 数',
    latencyMs    INT                                  NULL COMMENT '响应耗时（毫秒）',
    requestId    VARCHAR(64)                          NULL COMMENT '请求追踪id',
    extra        JSON                                 NULL COMMENT '扩展字段（错误信息、工具调用等）',
    createTime   DATETIME   DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime   DATETIME   DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete     TINYINT    DEFAULT 0                 NOT NULL COMMENT '是否删除',
    UNIQUE KEY uk_sessionId_seqNo (sessionId, seqNo), -- 确保同一会话内消息顺序唯一
    INDEX idx_sessionId_createTime (sessionId, createTime),
    INDEX idx_userId_appId_createTime (userId, appId, createTime),
    INDEX idx_appId_createTime (appId, createTime)
) COMMENT '对话历史' COLLATE = utf8mb4_unicode_ci;

-- 模型配置表
CREATE TABLE IF NOT EXISTS model_config
(
    id            BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    userId        BIGINT       NOT NULL COMMENT '用户id',
    provider      VARCHAR(64)  NOT NULL COMMENT '模型提供商',
    modelName     VARCHAR(128) NOT NULL COMMENT '模型名称',
    baseUrl       VARCHAR(512) NOT NULL COMMENT 'API 基础地址',
    apiKeyCipher  TEXT         NOT NULL COMMENT 'API 密钥（加密存储）',
    temperature   DOUBLE       DEFAULT 0.7 COMMENT '温度参数',
    maxTokens     INT          DEFAULT 8192 COMMENT '最大 token 数',
    configVersion INT          DEFAULT 1     NOT NULL COMMENT '配置版本号',
    enabled       TINYINT      DEFAULT 1     NOT NULL COMMENT '是否启用',
    isDefault     TINYINT      DEFAULT 0     NOT NULL COMMENT '是否为默认配置',
    createTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete      TINYINT      DEFAULT 0     NOT NULL COMMENT '是否删除',
    INDEX idx_user_default (userId, isDefault),
    INDEX idx_user_enabled (userId, enabled)
) COMMENT '模型配置' COLLATE = utf8mb4_unicode_ci;

-- Agent 运行记录表
CREATE TABLE IF NOT EXISTS agent_run
(
    id            BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    appId         BIGINT       NOT NULL COMMENT '应用id',
    sessionId     BIGINT       NOT NULL COMMENT '会话id',
    userId        BIGINT       NOT NULL COMMENT '用户id',
    runtime       VARCHAR(64)  NOT NULL COMMENT '运行时类型',
    modelConfigId BIGINT       NULL COMMENT '模型配置id',
    configVersion INT          NULL COMMENT '配置版本号',
    status        VARCHAR(32)  NOT NULL COMMENT '运行状态',
    workspacePath VARCHAR(1024) NULL COMMENT '工作区路径',
    errorMessage  TEXT         NULL COMMENT '错误信息',
    latencyMs     INT          DEFAULT 0 COMMENT '耗时（毫秒）',
    createTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime    DATETIME     DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete      TINYINT      DEFAULT 0     NOT NULL COMMENT '是否删除',
    INDEX idx_app_status (appId, status),
    INDEX idx_session_time (sessionId, createTime)
) COMMENT 'Agent 运行记录' COLLATE = utf8mb4_unicode_ci;

-- 应用版本表
CREATE TABLE IF NOT EXISTS app_version
(
    id           BIGINT AUTO_INCREMENT COMMENT 'id' PRIMARY KEY,
    appId        BIGINT        NOT NULL COMMENT '应用id',
    agentRunId   BIGINT        NOT NULL COMMENT 'Agent 运行id',
    versionNo    INT           NOT NULL COMMENT '版本号',
    sourcePath   VARCHAR(1024) NOT NULL COMMENT '源码路径',
    buildPath    VARCHAR(1024) NULL COMMENT '构建输出路径',
    status       VARCHAR(32)   NOT NULL COMMENT '版本状态',
    createTime   DATETIME      DEFAULT CURRENT_TIMESTAMP NOT NULL COMMENT '创建时间',
    updateTime   DATETIME      DEFAULT CURRENT_TIMESTAMP NOT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    isDelete     TINYINT       DEFAULT 0     NOT NULL COMMENT '是否删除',
    UNIQUE KEY uk_app_version (appId, versionNo),
    INDEX idx_app_status (appId, status)
) COMMENT '应用版本' COLLATE = utf8mb4_unicode_ci;
