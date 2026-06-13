// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 POST /model-config/add */
export async function addModelConfig(body: API.ModelConfigAddRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseLong>('/model-config/add', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/delete */
export async function deleteModelConfig(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/model-config/delete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/edit */
export async function editModelConfig(body: API.ModelConfigEditRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/model-config/edit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /model-config/get/vo */
export async function getModelConfigVoById(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getModelConfigVOByIdParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseModelConfigVO>('/model-config/get/vo', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 GET /model-config/internal/runtime */
export async function getRuntimeConfig(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.getRuntimeConfigParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseModelConfigRuntimeVO>('/model-config/internal/runtime', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/list/page/vo */
export async function listModelConfigVoByPage(body: API.ModelConfigQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageModelConfigVO>('/model-config/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/my/list/page/vo */
export async function listMyModelConfigVoByPage(body: API.ModelConfigQueryRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponsePageModelConfigVO>('/model-config/my/list/page/vo', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/set/default */
export async function setDefault(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/model-config/set/default', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /model-config/toggle/enabled */
export async function toggleEnabled(body: API.DeleteRequest, options?: { [key: string]: any }) {
  return request<API.BaseResponseBoolean>('/model-config/toggle/enabled', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}
