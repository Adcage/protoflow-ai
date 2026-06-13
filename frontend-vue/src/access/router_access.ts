import { useLoginUserStore } from '@/stores/LoginUser.ts'
import { message } from 'ant-design-vue'
import router from '@/router'

let firstFetchLoginUser = true

const needLoginPaths = ['/app/my', '/app/generate', '/user/profile', '/user/usage', '/model/config']

router.beforeEach(async (to, from, next) => {
  const loginUserStore = useLoginUserStore()
  let loginUser = loginUserStore.loginUser
  if (firstFetchLoginUser) {
    await loginUserStore.fetchLoginUser()
    loginUser = loginUserStore.loginUser
    firstFetchLoginUser = false
  }
  const toUrl = to.fullPath
  const isLoggedIn = loginUser.userName !== '未登录'

  if (toUrl.startsWith('/admin')) {
    if (!isLoggedIn) {
      message.error('未登录，请先登录')
      next(`/user/login?redirect=${to.fullPath}`)
      return
    }
    if (loginUser.userRole !== 'admin') {
      message.error('没有权限')
      next(from.fullPath)
      return
    }
  }

  if (needLoginPaths.some((p) => toUrl.startsWith(p))) {
    if (!isLoggedIn) {
      message.warning('请先登录')
      next(`/user/login?redirect=${to.fullPath}`)
      return
    }
  }

  next()
})
