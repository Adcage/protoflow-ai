<template>
  <a-config-provider :locale="zhCN" :theme="darkTheme">
    <RouterView />
  </a-config-provider>
</template>

<script lang="ts" setup>
import { RouterView } from 'vue-router'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { theme } from 'ant-design-vue'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#22C55E',
    colorBgContainer: '#1E293B',
    colorBgElevated: '#334155',
    colorBgLayout: '#0F172A',
    colorBorder: '#475569',
    colorText: '#F8FAFC',
    colorTextSecondary: '#94A3B8',
    borderRadius: 8,
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
  },
}
</script>
