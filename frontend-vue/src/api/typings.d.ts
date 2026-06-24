declare namespace API {
  type App = {
    id?: number
    appName?: string
    cover?: string
    initPrompt?: string
    codeGenType?: string
    generationMode?: string
    styleTemplate?: string
    deployKey?: string
    deployedTime?: string
    priority?: number
    userId?: number
    editTime?: string
    createTime?: string
    updateTime?: string
    isDelete?: number
    isTestApp?: number
  }

  type AppAddRequest = {
    initPrompt?: string
    codeGenType?: string
    generationMode?: string
    styleTemplate?: string
    isTestApp?: boolean
  }

  type AppAdminUpdateRequest = {
    id?: number
    appName?: string
    cover?: string
    priority?: number
  }

  type AppDeployRequest = {
    appId?: number
  }

  type AppEditRequest = {
    id?: number
    appName?: string
  }

  type AppQueryRequest = {
    pageNum?: number
    pageSize?: number
    sortField?: string
    sortOrder?: string
    id?: number
    appName?: string
    initPrompt?: string
    codeGenType?: string
    deployKey?: string
    priority?: number
    userId?: number
    userName?: string
    onlyFeatured?: boolean
    isTestApp?: boolean
  }

  type AppVersionVO = {
    id?: number
    appId?: number
    versionNo?: number
    status?: string
    createTime?: string
  }

  type AppVO = {
    id?: number
    appName?: string
    cover?: string
    initPrompt?: string
    codeGenType?: string
    generationMode?: string
    artifactFormat?: string
    previewUrl?: string
    styleTemplate?: string
    deployKey?: string
    deployedTime?: string
    priority?: number
    userId?: number
    createTime?: string
    updateTime?: string
    isTestApp?: number
    user?: UserVO
    coverTaskStatus?: string
    coverRetryCount?: number
    coverErrorMessage?: string
  }

  type BaseResponseApp = {
    code?: number
    data?: App
    message?: string
  }

  type BaseResponseAppVO = {
    code?: number
    data?: AppVO
    message?: string
  }

  type BaseResponseBoolean = {
    code?: number
    data?: boolean
    message?: string
  }

  type BaseResponseListAppVersionVO = {
    code?: number
    data?: AppVersionVO[]
    message?: string
  }

  type BaseResponseListChatSessionVO = {
    code?: number
    data?: ChatSessionVO[]
    message?: string
  }

  type BaseResponseLoginUserVO = {
    code?: number
    data?: LoginUserVO
    message?: string
  }

  type BaseResponseLong = {
    code?: number
    data?: number
    message?: string
  }

  type BaseResponseModelConfigRuntimeVO = {
    code?: number
    data?: ModelConfigRuntimeVO
    message?: string
  }

  type BaseResponseModelConfigVO = {
    code?: number
    data?: ModelConfigVO
    message?: string
  }

  type BaseResponsePageApp = {
    code?: number
    data?: PageApp
    message?: string
  }

  type BaseResponsePageAppVO = {
    code?: number
    data?: PageAppVO
    message?: string
  }

  type BaseResponsePageChatHistoryVO = {
    code?: number
    data?: PageChatHistoryVO
    message?: string
  }

  type BaseResponsePageModelConfigVO = {
    code?: number
    data?: PageModelConfigVO
    message?: string
  }

  type BaseResponsePageUser = {
    code?: number
    data?: PageUser
    message?: string
  }

  type BaseResponsePageUserVO = {
    code?: number
    data?: PageUserVO
    message?: string
  }

  type BaseResponseString = {
    code?: number
    data?: string
    message?: string
  }

  type BaseResponseUsageStatsVO = {
    code?: number
    data?: UsageStatsVO
    message?: string
  }

  type BaseResponseUser = {
    code?: number
    data?: User
    message?: string
  }

  type BaseResponseUserVO = {
    code?: number
    data?: UserVO
    message?: string
  }

  type ChatHistoryQueryRequest = {
    pageNum?: number
    pageSize?: number
    sortField?: string
    sortOrder?: string
    appId?: number
    sessionId?: number
  }

  type ChatHistoryVO = {
    id?: number
    sessionId?: number
    seqNo?: number
    message?: string
    messageType?: string
    status?: string
    appId?: number
    userId?: number
    modelName?: string
    inputTokens?: number
    outputTokens?: number
    latencyMs?: number
    requestId?: string
    extra?: string
    toolEvents?: ToolEventVO[]
    createTime?: string
  }

  type ChatSessionCreateRequest = {
    appId?: number
  }

  type ChatSessionRenameRequest = {
    sessionId?: number
    title?: string
  }

  type ChatSessionVO = {
    id?: number
    appId?: number
    userId?: number
    title?: string
    messageCount?: number
    modelName?: string
    lastMessageTime?: string
    createTime?: string
    updateTime?: string
  }

  type chatToGenCodeParams = {
    appId: number
    sessionId?: number
    message: string
  }

  type DailyUsageVO = {
    date?: string
    inputTokens?: number
    outputTokens?: number
    messages?: number
  }

  type DeleteRequest = {
    id?: number
  }

  type downloadAppProjectParams = {
    appId: number
  }

  type executeParams = {
    appId: number
    message: string
  }

  type getAppByIdParams = {
    id: number
  }

  type getAppVOByIdByAdminParams = {
    id: number
  }

  type getAppVOByIdParams = {
    id: number
  }

  type getModelConfigVOByIdParams = {
    id: number
  }

  type getRuntimeConfigParams = {
    id: number
    configVersion: number
  }

  type getUserByIdParams = {
    id: number
  }

  type getUserVOByIdParams = {
    id: number
  }

  type listChatSessionParams = {
    appId: number
  }

  type listVersionsParams = {
    appId: number
    limit?: number
  }

  type LoginUserVO = {
    id?: number
    userAccount?: string
    userName?: string
    userAvatar?: string
    userProfile?: string
    userRole?: string
    createTime?: string
    updateTime?: string
  }

  type ModelConfigAddRequest = {
    provider?: string
    modelName?: string
    baseUrl?: string
    apiKeyCipher?: string
    temperature?: number
    maxTokens?: number
  }

  type ModelConfigEditRequest = {
    id?: number
    provider?: string
    modelName?: string
    baseUrl?: string
    apiKeyCipher?: string
    temperature?: number
    maxTokens?: number
    enabled?: number
    isDefault?: number
  }

  type ModelConfigQueryRequest = {
    pageNum?: number
    pageSize?: number
    sortField?: string
    sortOrder?: string
    provider?: string
    modelName?: string
    enabled?: number
  }

  type ModelConfigRuntimeVO = {
    provider?: string
    modelName?: string
    baseUrl?: string
    apiKey?: string
  }

  type ModelConfigVO = {
    id?: number
    userId?: number
    provider?: string
    modelName?: string
    baseUrl?: string
    temperature?: number
    maxTokens?: number
    configVersion?: number
    enabled?: number
    isDefault?: number
    createTime?: string
    updateTime?: string
  }

  type PageApp = {
    records?: App[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type PageAppVO = {
    records?: AppVO[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type PageChatHistoryVO = {
    records?: ChatHistoryVO[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type PageModelConfigVO = {
    records?: ModelConfigVO[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type PageUser = {
    records?: User[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type PageUserVO = {
    records?: UserVO[]
    pageNumber?: number
    pageSize?: number
    totalPage?: number
    totalRow?: number
    optimizeCountQuery?: boolean
  }

  type ServerSentEventString = true

  type ToolEventVO = {
    type?: string
    text?: string
  }

  type UsageStatsVO = {
    totalInputTokens?: number
    totalOutputTokens?: number
    totalMessages?: number
    totalApps?: number
    totalSessions?: number
    avgLatencyMs?: number
    recentDailyUsage?: DailyUsageVO[]
  }

  type User = {
    id?: number
    userAccount?: string
    userPassword?: string
    userName?: string
    userAvatar?: string
    userProfile?: string
    userRole?: string
    editTime?: string
    createTime?: string
    updateTime?: string
    isDelete?: number
    vipExpireTime?: string
    vipCode?: string
    vipNumber?: number
    shareCode?: string
    inviteUser?: number
  }

  type UserAddRequest = {
    userName?: string
    userAccount?: string
    userAvatar?: string
    userProfile?: string
    userRole?: string
  }

  type UserEditRequest = {
    userName?: string
    userAvatar?: string
    userProfile?: string
  }

  type UserLoginRequest = {
    userAccount?: string
    userPassword?: string
  }

  type UserQueryRequest = {
    pageNum?: number
    pageSize?: number
    sortField?: string
    sortOrder?: string
    id?: number
    userName?: string
    userAccount?: string
    userProfile?: string
    userRole?: string
  }

  type UserRegisterRequest = {
    userAccount?: string
    userPassword?: string
    checkPassword?: string
  }

  type UserUpdateRequest = {
    id?: number
    userName?: string
    userAvatar?: string
    userProfile?: string
    userRole?: string
  }

  type UserVO = {
    id?: number
    userAccount?: string
    userName?: string
    userAvatar?: string
    userProfile?: string
    userRole?: string
    createTime?: string
  }
}
