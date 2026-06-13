// @ts-ignore
/* eslint-disable */
import request from '@/request'

/** 此处后端没有提供注释 GET /workflow/sse/execute */
export async function execute(
  // 叠加生成的Param类型 (非body参数swagger默认没有生成对象)
  params: API.executeParams,
  options?: { [key: string]: any }
) {
  return request<API.ServerSentEventString[]>('/workflow/sse/execute', {
    method: 'GET',
    params: {
      ...params,
    },
    ...(options || {}),
  })
}
