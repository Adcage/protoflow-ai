import axios from 'axios'
import { message } from 'ant-design-vue'
import router from '@/router'

// 创建 Axios 实例
const myAxios = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 60000,
  withCredentials: true,
})

// 全局请求拦截器
myAxios.interceptors.request.use(
  function (config) {
    // Do something before request is sent
    return config
  },
  function (error) {
    // Do something with request error
    return Promise.reject(error)
  },
)

// 全局响应拦截器
myAxios.interceptors.response.use(
  async function (response) {
    const { data } = response
    // 未登录
    if (data.code === 40100) {
      // 不是获取用户信息的请求，并且用户目前不是已经在用户登录页面，则跳转到登录页面
      if (
        !response.request.responseURL.includes('user/get/login') &&
        !window.location.pathname.includes('/user/login')
      ) {
        message.warning('请先登录')
        await router.push({
          path: '/user/login',
          query: {
            redirect: window.location.pathname,
          },
        })
      }
    }
    return response
  },
  function (error) {
    if (error.response?.status === 429) {
      message.warning('请求过于频繁，请稍后再试')
      return Promise.reject(error)
    }
    if (error.code === 'ERR_CONNECTION_REFUSED') {
      message.error('后端服务未启动，请检查服务状态')
    }
    return Promise.reject(error)
  },
)

export default myAxios
