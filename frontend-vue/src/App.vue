<template>
  <a-config-provider :locale="zhCN" :theme="warmTheme">
    <RouterView />
  </a-config-provider>
</template>

<script lang="ts" setup>
import { RouterView } from 'vue-router'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

const warmTheme = {
  token: {
    colorPrimary: '#C85A3E',
    colorInfo: '#5B8BA9',
    colorSuccess: '#4A9D6B',
    colorWarning: '#D4944C',
    colorError: '#C85A3E',
    colorTextBase: '#1C1815',
    colorBgBase: '#FDF9F5',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#FDF9F5',
    colorBorder: '#E8E0D8',
    colorBorderSecondary: '#F0EBE5',
    borderRadius: 6,
    borderRadiusLG: 10,
    borderRadiusSM: 4,
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: 14,
    controlHeight: 36,
  },
}
</script>
