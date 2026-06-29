// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 GET /file/chat-attachment/&#42;&#42; */
export async function serveChatAttachment(options?: { [key: string]: any }) {
  return request<string>('/file/chat-attachment/**', {
    method: 'GET',
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /file/upload/avatar */
export async function uploadAvatar(body: {}, options?: { [key: string]: any }) {
  return request<API.BaseResponseString>('/file/upload/avatar', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    data: body,
    ...(options || {}),
  })
}

/** 此处后端没有提供注释 POST /file/upload/chat-attachment */
export async function uploadChatAttachment(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.uploadChatAttachmentParams,
  options?: { [key: string]: any }
) {
  return request<API.BaseResponseListChatAttachmentInfo>('/file/upload/chat-attachment', {
    method: 'POST',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}
