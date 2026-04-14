import test from 'node:test'
import assert from 'node:assert/strict'

const BASE_URL = process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8700/api'

async function postJson(path, body, cookie) {
  const headers = { 'Content-Type': 'application/json' }
  if (cookie) {
    headers.Cookie = cookie
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  const text = await response.text()
  let data
  try {
    data = JSON.parse(text)
  } catch {
    data = { raw: text }
  }
  return { response, data }
}

async function getJson(path, cookie) {
  const headers = {}
  if (cookie) {
    headers.Cookie = cookie
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'GET',
    headers,
  })
  const text = await response.text()
  let data
  try {
    data = JSON.parse(text)
  } catch {
    data = { raw: text }
  }
  return { response, data }
}

test('前端到后端聊天链路端到端：登录 -> 应用 -> 会话 -> SSE -> 历史', async () => {
  const suffix = `${Date.now()}_${Math.floor(Math.random() * 100000)}`
  const userAccount = `e2e_front_${suffix}`
  const userPassword = '12345678'

  const registerRes = await postJson('/user/register', {
    userAccount,
    userPassword,
    checkPassword: userPassword,
  })
  assert.equal(registerRes.data.code, 0, `注册失败: ${JSON.stringify(registerRes.data)}`)

  const loginRes = await postJson('/user/login', {
    userAccount,
    userPassword,
  })
  assert.equal(loginRes.data.code, 0, `登录失败: ${JSON.stringify(loginRes.data)}`)
  const cookie = loginRes.response.headers.get('set-cookie')
  assert.ok(cookie, '登录后未拿到会话 Cookie')

  const addAppRes = await postJson(
    '/app/add',
    {
      initPrompt: '请生成一个按钮页面',
      codeGenType: 'single_file',
      appName: 'E2E-前后端链路测试应用',
    },
    cookie,
  )
  assert.equal(addAppRes.data.code, 0, `创建应用失败: ${JSON.stringify(addAppRes.data)}`)
  const appId = addAppRes.data.data
  assert.ok(appId, '创建应用未返回 appId')

  try {
    const createSessionRes = await postJson('/app/chat/session/create', { appId }, cookie)
    assert.equal(createSessionRes.data.code, 0, `创建会话失败: ${JSON.stringify(createSessionRes.data)}`)
    const sessionId = String(createSessionRes.data.data)
    assert.ok(/^\d+$/.test(sessionId), '创建会话未返回合法 sessionId')

    const sseResponse = await fetch(
      `${BASE_URL}/app/chat/gen/code/stream?appId=${appId}&sessionId=${sessionId}&message=${encodeURIComponent('请生成一个蓝色按钮')}`,
      {
        method: 'GET',
        headers: { Cookie: cookie },
      },
    )
    assert.equal(sseResponse.status, 200, `SSE 响应码异常: ${sseResponse.status}`)
    const contentType = sseResponse.headers.get('content-type') || ''
    if (!contentType.includes('text/event-stream')) {
      const abnormalBody = await sseResponse.text()
      assert.fail(`SSE Content-Type 异常: ${contentType}; body: ${abnormalBody}`)
    }

    const reader = sseResponse.body?.getReader()
    assert.ok(reader, 'SSE 响应流为空')
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let hasMeta = false
    const deadline = Date.now() + 30000

    while (Date.now() < deadline && !hasMeta) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      hasMeta = buffer.includes('event:meta') && buffer.includes(`"sessionId":${sessionId}`)
    }
    await reader.cancel()
    assert.equal(hasMeta, true, `SSE 首帧 meta 缺失，收到内容: ${buffer}`)

    const listSessionRes = await getJson(`/app/chat/session/list?appId=${appId}`, cookie)
    assert.equal(listSessionRes.data.code, 0, `会话列表查询失败: ${JSON.stringify(listSessionRes.data)}`)
    const currentSession = (listSessionRes.data.data || []).find((item) => String(item.id) === sessionId)
    assert.ok(currentSession, '会话列表中不存在刚创建的会话')

    await new Promise((resolve) => setTimeout(resolve, 500))
    const historyRes = await postJson(
      '/app/chat/history/page',
      {
        appId,
        sessionId,
        pageNum: 1,
        pageSize: 20,
      },
      cookie,
    )
    assert.equal(historyRes.data.code, 0, `历史分页查询失败: ${JSON.stringify(historyRes.data)}`)
    const records = historyRes.data?.data?.records || []
    assert.ok(records.length >= 1, '历史消息为空，至少应包含用户消息')
    assert.equal(records[0].messageType, 'user', '首条历史消息应为用户消息')
  } finally {
    await postJson('/app/delete', { id: appId }, cookie)
    await postJson('/user/logout', {}, cookie)
  }
})
