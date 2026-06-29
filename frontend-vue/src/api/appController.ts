// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 POST /app/add */
export async function addApp(body: API.AppAddRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/app/add', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/add/test */
export async function addTestApp(body: API.AppAddRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/app/add/test', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/admin/get/vo */
export async function getAppVoByIdByAdmin(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getAppVOByIdByAdminParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAppVO>('/app/admin/get/vo', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/admin/list/page/vo */
export async function listAppVoByPageByAdmin(body: API.AppQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageAppVO>('/app/admin/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/categories */
export async function listCategories(options?: { [key: string]: any }) {
  return request<API.BaseResponseListString>('/app/categories', {
    method: 'GET',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/chat/gen/active */
export async function getActiveGeneration(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getActiveGenerationParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseMapStringObject>('/app/chat/gen/active', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/gen/code/stream */
export async function chatToGenCode(body: API.ChatCodeGenRequest, options?: { [key: string]: any }) {
  return request<API.ServerSentEventString[]>('/app/chat/gen/code/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/gen/code/stream/resume */
export async function resumeGeneration(body: Record<string, any>, options?: { [key: string]: any }) {
  return request<API.ServerSentEventString[]>('/app/chat/gen/code/stream/resume', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/history/page */
export async function listChatHistoryByPage(body: API.ChatHistoryQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageChatHistoryVO>('/app/chat/history/page', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/session/create */
export async function createChatSession(body: API.ChatSessionCreateRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/app/chat/session/create', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/session/delete */
export async function deleteSession(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/chat/session/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/chat/session/list */
export async function listChatSession(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.listChatSessionParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListChatSessionVO>('/app/chat/session/list', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/chat/session/rename */
export async function renameSession(body: API.ChatSessionRenameRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/chat/session/rename', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/delete */
export async function deleteApp(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/delete/admin */
export async function deleteAppByAdmin(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/delete/admin', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/deploy */
export async function deployApp(body: API.AppDeployRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseString>('/app/deploy', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/download/${param0} */
export async function downloadAppProject(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.downloadAppProjectParams,
  options?: { [key: string]: any }
) {
  const { appId: param0, ...queryParams } = params
  return request<any>(`/app/download/${param0}`, {
    method: 'GET',
    params: { ...queryParams },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/edit */
export async function editApp(body: API.AppEditRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/edit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/enhance-prompt */
export async function enhancePrompt(body: Record<string, any>, options?: { [key: string]: any }) {
  return request<API.BaseResponseString>('/app/enhance-prompt', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/fork */
export async function forkApp(body: Record<string, any>, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/app/fork', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/get */
export async function getAppById(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getAppByIdParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseApp>('/app/get', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /app/get/vo */
export async function getAppVoById(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getAppVOByIdParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseAppVO>('/app/get/vo', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/good/list/page/vo */
export async function listGoodAppVoByPage(body: API.AppQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageAppVO>('/app/good/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/list/page */
export async function listAppByPage(body: API.AppQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageApp>('/app/list/page', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/marketplace/list/page/vo */
export async function listMarketplaceAppVoByPage(body: API.MarketplaceQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageMarketplaceAppVO>('/app/marketplace/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/my/list/page/vo */
export async function listMyAppVoByPage(body: API.AppQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageAppVO>('/app/my/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/publish */
export async function publishApp(body: Record<string, any>, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/publish', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/unpublish */
export async function unpublishApp(body: Record<string, any>, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/unpublish', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /app/update */
export async function updateApp(body: API.AppAdminUpdateRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/app/update', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}
