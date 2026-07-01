# Composition API

## setup 函数

`setup` 是组合式 API 的入口。在 `<script setup>` 中，所有顶层绑定自动暴露给模板：

```vue
<script setup>
import { ref, computed } from 'vue'

const count = ref(0)
const doubled = computed(() => count.value * 2)

function increment() {
  count.value++
}
</script>

<template>
  <p>{{ count }} × 2 = {{ doubled }}</p>
  <button @click="increment">+1</button>
</template>
```

## ref 和 reactive

- `ref`: 用于基本类型和对象，通过 `.value` 访问
- `reactive`: 用于对象，直接访问属性

```javascript
import { ref, reactive } from 'vue'

// ref
const count = ref(0)
console.log(count.value) // 0
count.value++

// reactive
const state = reactive({
  name: '张三',
  age: 28,
})
console.log(state.name) // '张三'
state.age = 29
```

在模板中 ref 会自动解包，不需要 `.value`。

## computed

`computed` 创建响应式计算值，自动追踪依赖：

```javascript
import { ref, computed } from 'vue'

const firstName = ref('张')
const lastName = ref('三')
const fullName = computed(() => `${firstName.value}${lastName.value}`)

// computed 是只读的，修改会报警告
// fullName.value = '李四' // ❌ 不允许

// 可写 computed
const fullNameWritable = computed({
  get: () => `${firstName.value}${lastName.value}`,
  set: (val) => {
    firstName.value = val[0]
    lastName.value = val.slice(1)
  },
})
```

## watch 和 watchEffect

```javascript
import { ref, watch, watchEffect } from 'vue'

const count = ref(0)

// watch: 明确指定监听源
watch(count, (newVal, oldVal) => {
  console.log(`count 从 ${oldVal} 变为 ${newVal}`)
})

// watchEffect: 自动追踪依赖
watchEffect(() => {
  console.log(`当前 count = ${count.value}`)
})

// 深层监听
const state = reactive({ nested: { count: 0 } })
watch(() => state.nested, (newVal) => {
  console.log('nested 变化', newVal)
}, { deep: true })

// 立即执行
watch(count, (val) => {
  console.log('立即执行', val)
}, { immediate: true })
```

## 生命周期

`<script setup>` 中的生命周期钩子：

```javascript
import { onMounted, onUpdated, onUnmounted } from 'vue'

onMounted(() => {
  console.log('组件已挂载')
})

onUpdated(() => {
  console.log('组件已更新')
})

onUnmounted(() => {
  console.log('组件已卸载')
})
```

对应关系：
- `created` → 直接在 `setup` 中写代码（不需要钩子）
- `mounted` → `onMounted`
- `updated` → `onUpdated`
- `destroyed` → `onUnmounted`
