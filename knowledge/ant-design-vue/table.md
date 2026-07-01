# Table 表格

## 基本用法

```vue
<template>
  <a-table :columns="columns" :data-source="data" />
</template>

<script setup>
const columns = [
  { title: '姓名', dataIndex: 'name', key: 'name' },
  { title: '年龄', dataIndex: 'age', key: 'age' },
  { title: '地址', dataIndex: 'address', key: 'address' },
]

const data = [
  { key: '1', name: '张三', age: 32, address: '北京市朝阳区' },
  { key: '2', name: '李四', age: 28, address: '上海市浦东新区' },
]
</script>
```

## 分页配置

`pagination` 属性接受对象或布尔值。设为 `false` 可隐藏分页。

```vue
<template>
  <a-table
    :columns="columns"
    :data-source="data"
    :pagination="{ pageSize: 10, showSizeChanger: true, showQuickJumper: true }"
  />
</template>
```

常用分页配置项：
- `pageSize`: 每页条数，默认 10
- `current`: 当前页码
- `total`: 数据总数
- `showSizeChanger`: 是否显示 pageSize 切换器
- `showQuickJumper`: 是否可以快速跳转至某页
- `onChange`: 页码改变的回调
- `onShowSizeChange`: pageSize 变化的回调

## 远程数据加载

当配合分页使用时，需要监听 `change` 事件来获取远程数据：

```vue
<template>
  <a-table
    :columns="columns"
    :data-source="data"
    :pagination="pagination"
    :loading="loading"
    @change="handleTableChange"
  />
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

const data = ref([])
const loading = ref(false)
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
})

const fetchData = async (params) => {
  loading.value = true
  const res = await api.getList({
    page: params.current,
    pageSize: params.pageSize,
  })
  data.value = res.data.list
  pagination.total = res.data.total
  loading.value = false
}

const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  fetchData(pagination)
}

onMounted(() => fetchData(pagination))
</script>
```

## 行选择

```vue
<template>
  <a-table
    :columns="columns"
    :data-source="data"
    :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
  />
</template>

<script setup>
import { ref } from 'vue'

const selectedRowKeys = ref([])

const onSelectChange = (keys) => {
  selectedRowKeys.value = keys
}
</script>
```

## 自定义行样式

使用 `customRow` 设置行属性：

```vue
<template>
  <a-table
    :columns="columns"
    :data-source="data"
    :custom-row="customRow"
  />
</template>

<script setup>
const customRow = (record) => ({
  onClick: () => {
    console.log('点击行', record)
  },
})
</script>
```
