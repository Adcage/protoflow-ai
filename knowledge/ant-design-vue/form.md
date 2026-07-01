# Form 表单

## 基本用法

使用 `v-model` 进行双向绑定，通过 `rules` 定义校验规则：

```vue
<template>
  <a-form
    :model="formState"
    :rules="rules"
    ref="formRef"
    @finish="onSubmit"
  >
    <a-form-item label="用户名" name="username">
      <a-input v-model:value="formState.username" />
    </a-form-item>
    <a-form-item label="密码" name="password">
      <a-input-password v-model:value="formState.password" />
    </a-form-item>
    <a-form-item>
      <a-button type="primary" html-type="submit">提交</a-button>
    </a-form-item>
  </a-form>
</template>

<script setup>
import { ref, reactive } from 'vue'

const formRef = ref()
const formState = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6位' }],
}

const onSubmit = () => {
  console.log('提交', formState)
}
</script>
```

## 表单布局

`layout` 属性支持 `horizontal`（默认）、`vertical`、`inline` 三种布局：

```vue
<a-form layout="vertical">
  <!-- label 在输入框上方 -->
</a-form>

<a-form layout="inline">
  <!-- 所有表单项水平排列 -->
</a-form>
```

## 表单校验

支持内置校验规则和自定义校验函数：

```javascript
const rules = {
  email: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '邮箱格式不正确' },
  ],
  age: [
    { type: 'number', min: 0, max: 150, message: '年龄不合法' },
  ],
  phone: [
    {
      validator: async (_rule, value) => {
        if (!value) return Promise.reject('请输入手机号')
        if (!/^1[3-9]\d{9}$/.test(value)) return Promise.reject('手机号格式不正确')
        return Promise.resolve()
      },
    },
  ],
}
```

## 动态增减表单项

使用 `v-for` 配合动态数据实现：

```vue
<template>
  <a-form :model="formState">
    <a-form-item
      v-for="(item, index) in formState.users"
      :key="index"
      :label="`用户 ${index + 1}`"
      :name="['users', index, 'name']"
    >
      <a-input v-model:value="item.name" />
      <a-button @click="removeUser(index)" danger>删除</a-button>
    </a-form-item>
    <a-button @click="addUser">添加用户</a-button>
  </a-form>
</template>

<script setup>
import { reactive } from 'vue'

const formState = reactive({
  users: [{ name: '' }],
})

const addUser = () => {
  formState.users.push({ name: '' })
}

const removeUser = (index) => {
  formState.users.splice(index, 1)
}
</script>
```
