<template>
  <div id="homePage">
    <section class="hero-section">
      <div class="hero-bg-glow"></div>
      <div class="hero-bg-glow-2"></div>
      <div class="hero-content">
        <div class="hero-label">
          <span class="hero-label-dot"></span>
          创作 · 由 AI 驱动
        </div>
        <h1 class="hero-title">设计从未如此<br><span class="text-cta">简单而强大</span></h1>
        <p class="hero-subtitle">用对话驱动创意，从网站到幻灯片，<br>让 AI 帮你把想法变成真实可用的作品。</p>

        <div class="search-container">
          <a-textarea
            v-model:value="searchText"
            placeholder="描述你想要的应用，例如：帮我创建一个极简风格的个人博客..."
            :auto-size="{ minRows: 3, maxRows: 6 }"
            class="search-textarea"
          />
          <div class="search-actions">
            <div class="search-actions-left">
              <a-tooltip title="在生成器中上传参考文件">
                <a-button type="text" class="action-btn" @click="goToGenerate">
                  <template #icon><Paperclip :size="16" /></template>
                  上传
                </a-button>
              </a-tooltip>
              <a-tooltip title="AI 帮你优化提示词，生成更精准的代码">
                <a-button
                  type="text"
                  class="action-btn"
                  :disabled="!searchText.trim()"
                  :loading="enhancing"
                  @click="doEnhance"
                >
                  <template #icon><Sparkles :size="16" /></template>
                  优化
                </a-button>
              </a-tooltip>
            </div>
            <a-button type="primary" shape="circle" class="send-btn" @click="doGenerate" :loading="loading">
              <template #icon><ArrowUp :size="20" /></template>
            </a-button>
          </div>
        </div>

        <div class="style-templates">
          <div
            v-for="tpl in styleTemplates"
            :key="tpl.value"
            :class="['style-tag', { 'style-tag-active': selectedStyle === tpl.value }]"
            @click="selectedStyle = tpl.value"
          >
            {{ tpl.label }}
          </div>
        </div>

        <div class="tag-suggestions">
          <span v-for="tag in suggestions" :key="tag" class="suggestion-chip" @click="searchText = tag">
            {{ tag }}
          </span>
        </div>
      </div>
    </section>

    <div class="hero-transition"></div>

    <section class="features-section">
      <div class="section-inner">
        <div class="features-top">
          <div class="features-top-left">
            <h2 class="features-heading">为创作者而生<br>不止于 <span class="text-cta">AI 设计</span></h2>
            <p class="section-subheading" style="text-align: left; margin-bottom: 0;">强大的 AI 驱动，让创意变为现实。</p>
          </div>
          <div class="features-top-right">
            <div class="big-stat">
              <div class="big-stat-num">12K+</div>
              <div class="big-stat-label">已创建应用</div>
            </div>
            <div class="big-stat">
              <div class="big-stat-num">5K+</div>
              <div class="big-stat-label">已部署项目</div>
            </div>
          </div>
        </div>

        <div class="bento-grid">
          <div class="bento-card bento-span-2">
            <div class="bento-icon"><Sparkles :size="28" /></div>
            <h3 class="bento-title">AI 智能生成</h3>
            <p class="bento-desc">一句话描述需求即可生成完整设计页面与应用内容，从想法到作品只需几分钟</p>
          </div>
          <div class="bento-card brand-card">
            <div class="bento-icon"><Layers :size="28" /></div>
            <h3 class="bento-title">多模式支持</h3>
            <p class="bento-desc">单文件、多文件、Vue 工程三种模式，灵活适配各种场景</p>
          </div>
          <div class="bento-card dark-card">
            <div class="bento-icon"><Eye :size="28" /></div>
            <h3 class="bento-title">实时预览</h3>
            <p class="bento-desc">生成过程中实时预览效果，边看边调，所见即所得</p>
          </div>
          <div class="bento-card">
            <div class="bento-icon"><Rocket :size="28" /></div>
            <h3 class="bento-title">一键部署</h3>
            <p class="bento-desc">部署上线，即刻分享你的作品给全世界</p>
          </div>
          <div class="bento-card">
            <div class="bento-icon"><Palette :size="28" /></div>
            <h3 class="bento-title">风格模板</h3>
            <p class="bento-desc">极简、商务、科技等多种风格，一键切换</p>
          </div>
          <div class="bento-card">
            <div class="bento-icon"><GitBranch :size="28" /></div>
            <h3 class="bento-title">版本管理</h3>
            <p class="bento-desc">自动记录版本，随时回退到任意历史版本</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 生成器场景演示 -->
    <div class="demo-scene-label">✦ 生成器 · 创作台</div>
    <div class="generator-bg">
      <div class="generator">
        <div class="gen-topbar">
          <h3 class="gen-title">个人博客 · 创作台</h3>
          <div class="gen-topbar-actions">
            <button class="gen-btn">⬇ 下载</button>
            <button class="gen-btn primary">☁ 部署</button>
          </div>
        </div>
        <div class="gen-main">
          <div class="gen-chat">
            <div class="gen-chat-msgs">
              <div class="msg-row">
                <div class="msg-avatar ai">AI</div>
                <div class="msg-bubble">你好！我来帮你创建个人博客。想要什么风格？</div>
              </div>
              <div class="msg-row user">
                <div class="msg-avatar user">M</div>
                <div class="msg-bubble">极简暖色调吧。</div>
              </div>
              <div class="msg-row">
                <div class="msg-avatar ai">AI</div>
                <div class="msg-bubble">好的！让我生成一个极简暖色的个人博客。需要创建首页、文章页和关于页。</div>
              </div>
            </div>
            <div class="gen-input-area">
              <input type="text" placeholder="描述你要修改的内容..." disabled />
              <button class="gen-send" disabled>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              </button>
            </div>
          </div>
          <div class="gen-preview">
            <div class="gen-preview-toolbar">
              <div class="gen-preview-tab-group">
                <button class="gen-preview-tab active">桌面端</button>
                <button class="gen-preview-tab">移动端</button>
              </div>
              <button class="gen-btn" style="padding:4px 8px; font-size:12px;">⟳</button>
            </div>
            <div class="gen-preview-canvas">
              <div class="gen-preview-inner">
                <div class="preview-nav">
                  <span class="preview-logo">My Blog</span>
                  <div class="preview-nav-links">
                    <span>首页</span>
                    <span>文章</span>
                    <span class="preview-nav-active">关于</span>
                  </div>
                </div>
                <div class="preview-hero">
                  <div class="preview-hero-title">你好，我是小林</div>
                  <div class="preview-hero-desc">独立设计师 & 前端开发者。用简洁的设计语言，讲述有趣的故事。</div>
                </div>
                <div class="preview-cards">
                  <div class="preview-card">
                    <div class="preview-card-label">最新</div>
                    <div class="preview-card-title">设计中的留白</div>
                    <div class="preview-card-meta">3天前</div>
                  </div>
                  <div class="preview-card">
                    <div class="preview-card-label">项目</div>
                    <div class="preview-card-title">原象 Morpha 改版</div>
                    <div class="preview-card-meta">进行中</div>
                  </div>
                  <div class="preview-card highlight">
                    <div class="preview-card-label">探索</div>
                    <div class="preview-card-title">色彩系统入门</div>
                    <div class="preview-card-meta">阅读 →</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <section class="steps-section">
      <div class="section-inner">
        <h2 class="section-heading">三步创建你的应用</h2>

        <div class="steps-row">
          <div class="step-item">
            <div class="step-number">1</div>
            <div class="step-icon"><MessageSquare :size="24" /></div>
            <h3 class="step-title">描述需求</h3>
            <p class="step-desc">输入你想要的应用描述，选择喜欢的风格模板</p>
          </div>

          <div class="step-arrow"><ChevronRight :size="24" /></div>

          <div class="step-item">
            <div class="step-number">2</div>
            <div class="step-icon"><Cpu :size="24" /></div>
            <h3 class="step-title">AI 生成</h3>
            <p class="step-desc">AI 智能理解需求，自动生成完整代码</p>
          </div>

          <div class="step-arrow"><ChevronRight :size="24" /></div>

          <div class="step-item">
            <div class="step-number">3</div>
            <div class="step-icon"><Globe :size="24" /></div>
            <h3 class="step-title">预览部署</h3>
            <p class="step-desc">实时预览效果，一键部署上线</p>
          </div>
        </div>
      </div>
    </section>

    <section class="showcase-section">
      <div class="section-inner">
        <h2 class="section-heading">精选案例</h2>
        <p class="section-subheading">看看大家都在创作什么</p>

        <div class="showcase-grid" v-if="goodAppList.length > 0">
          <AppCard
            v-for="item in goodAppList"
            :key="item.id"
            :app="item"
            :showTime="false"
            tagPosition="top-right"
            :coverHeight="180"
          >
            <template #tags>
              <a-tag color="purple" v-if="(item.priority ?? 0) >= 99">精选</a-tag>
              <a-tag color="success" v-if="item.deployKey" size="small">已部署</a-tag>
            </template>
          </AppCard>
        </div>

        <div class="showcase-empty" v-else-if="!goodLoading">
          <Eye :size="32" />
          <p>暂无精选案例，快来创建第一个作品吧</p>
        </div>

        <div class="showcase-footer" v-if="goodTotal > goodAppList.length">
          <a-button class="load-more-btn" @click="loadMoreGood" :loading="goodLoading"> 加载更多 </a-button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  Paperclip,
  Sparkles,
  ArrowUp,
  Layers,
  Eye,
  Palette,
  Rocket,
  GitBranch,
  MessageSquare,
  Cpu,
  Globe,
  ChevronRight,
} from '@lucide/vue'
import { addApp, listGoodAppVoByPage, enhancePrompt } from '@/api/appController'
import AppCard from '@/components/AppCard.vue'
import { sanitizeAiServiceError } from '@/utils/appGenerator'

const router = useRouter()
const searchText = ref('')
const loading = ref(false)
const enhancing = ref(false)
const goodLoading = ref(false)
const selectedStyle = ref('')

const styleTemplates = [
  { label: '极简', value: 'minimal' },
  { label: '商务', value: 'business' },
  { label: '科技', value: 'tech' },
  { label: '活泼', value: 'playful' },
  { label: '暗黑', value: 'dark' },
]

const suggestions = ['波普风电商页面', '企业官网', '电商运营后台', '暗黑话题社区']

const goodAppList = ref<API.AppVO[]>([])
const goodTotal = ref(0)

const goodSearchParams = ref<API.AppQueryRequest>({
  pageNum: 1,
  pageSize: 20,
})

const loadGoodApps = async (append = false) => {
  goodLoading.value = true
  try {
    const res = await listGoodAppVoByPage(goodSearchParams.value)
    const pageData = res.data?.data
    if (res.data?.code === 0 && pageData) {
      if (append) {
        goodAppList.value.push(...(pageData.records || []))
      } else {
        goodAppList.value = pageData.records || []
      }
      goodTotal.value = pageData.totalRow || 0
    }
  } finally {
    goodLoading.value = false
  }
}

const loadMoreGood = () => {
  goodSearchParams.value.pageNum = (goodSearchParams.value.pageNum ?? 1) + 1
  loadGoodApps(true)
}

const doGenerate = async () => {
  if (!searchText.value) {
    message.warning('请输入需求提示词')
    return
  }
  loading.value = true
  try {
    const res = await addApp({
      initPrompt: searchText.value,
      styleTemplate: selectedStyle.value || undefined,
    })
    if (res.data?.code === 0) {
      router.push(`/app/generate/${res.data.data}`)
    } else {
      message.error('创建失败，' + res.data?.message)
    }
  } catch (e: unknown) {
    message.error('操作失败，' + (e instanceof Error ? e.message : String(e)))
  } finally {
    loading.value = false
  }
}

const RISK_REJECTION_KEYWORDS = [
  'the request was rejected',
  'considered high risk',
  '内容安全',
  '内容违规',
]

const looksLikeRiskRejection = (text: string) =>
  RISK_REJECTION_KEYWORDS.some((kw) => text.toLowerCase().includes(kw.toLowerCase()))

const doEnhance = async () => {
  const prompt = searchText.value.trim()
  if (!prompt) {
    message.warning('请先输入需求描述')
    return
  }
  if (looksLikeRiskRejection(prompt)) {
    message.error('当前输入包含安全拦截信息，请重新输入需求描述')
    return
  }
  enhancing.value = true
  try {
    const res = await enhancePrompt({ prompt })
    if (res.data?.code === 0) {
      const enhanced = res.data?.data
      if (enhanced && enhanced.trim() && !looksLikeRiskRejection(enhanced)) {
        searchText.value = enhanced
        message.success('提示词优化完成')
      } else if (enhanced && looksLikeRiskRejection(enhanced)) {
        message.error('提示词被内容安全策略拦截，请修改后重试')
      } else {
        message.warning('AI 未返回有效的优化结果，请重试或直接发送')
      }
    } else {
      message.error('优化失败，' + sanitizeAiServiceError(res.data?.message))
    }
  } catch (e: unknown) {
    message.error('优化失败，' + sanitizeAiServiceError(e instanceof Error ? e.message : String(e)))
  } finally {
    enhancing.value = false
  }
}

const goToGenerate = () => {
  if (searchText.value.trim()) {
    doGenerate()
  } else {
    message.info('请先输入需求描述，或直接在生成器页面操作')
  }
}

onMounted(() => {
  loadGoodApps()
})
</script>

<style scoped>
#homePage {
  min-height: 100vh;
  background: var(--color-background);
}

.hero-section {
  position: relative;
  min-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3xl) var(--space-lg);
  overflow: hidden;
  background: var(--color-hero-bg);
}

.hero-bg-glow {
  position: absolute;
  top: -20%;
  right: -10%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(200, 90, 62, 0.10) 0%, transparent 65%);
  pointer-events: none;
}

.hero-bg-glow-2 {
  position: absolute;
  bottom: -15%;
  left: -10%;
  width: 450px;
  height: 450px;
  background: radial-gradient(circle, rgba(212, 148, 76, 0.07) 0%, transparent 65%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 1;
  max-width: 800px;
  width: 100%;
  text-align: center;
}

.hero-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px 6px 10px;
  background: rgba(200, 90, 62, 0.15);
  border: 1px solid rgba(200, 90, 62, 0.2);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-cta);
  margin-bottom: 32px;
  backdrop-filter: blur(4px);
}

.hero-label-dot {
  width: 6px;
  height: 6px;
  background: var(--color-cta);
  border-radius: 50%;
  animation: hero-pulse 2s infinite;
}

@keyframes hero-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.hero-title {
  font-family: var(--font-heading);
  font-size: 60px;
  font-weight: 700;
  color: var(--color-text-on-dark);
  line-height: 1.1;
  margin-bottom: var(--space-md);
  letter-spacing: -1.5px;
}

.text-cta {
  color: var(--color-cta);
}

.hero-subtitle {
  font-size: 18px;
  color: var(--color-text-on-dark-secondary);
  margin-bottom: var(--space-2xl);
  line-height: 1.65;
  font-weight: 300;
}

.search-container {
  background: rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-xl);
  padding: var(--space-md);
  transition: all 0.3s;
}

.search-container:focus-within {
  border-color: rgba(200, 90, 62, 0.3);
  background: rgba(255, 255, 255, 0.1);
}

.search-textarea {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: var(--color-text-on-dark) !important;
  font-size: 16px;
  resize: none;
  padding: var(--space-sm) var(--space-sm);
}

.search-textarea::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.search-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-sm);
  padding: 0 var(--space-sm);
}

.search-actions-left {
  display: flex;
  gap: var(--space-xs);
}

.action-btn {
  color: rgba(255, 255, 255, 0.35) !important;
  font-size: 13px;
}

.action-btn:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.6) !important;
  background: rgba(255, 255, 255, 0.06) !important;
}

.send-btn {
  width: 44px;
  height: 44px;
  background: var(--color-cta) !important;
  border-color: var(--color-cta) !important;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(200, 90, 62, 0.3);
}

.send-btn:hover {
  background: var(--color-cta-hover) !important;
  border-color: var(--color-cta-hover) !important;
  transform: scale(1.05);
}

.style-templates {
  display: flex;
  justify-content: center;
  gap: var(--space-sm);
  margin-top: var(--space-lg);
  flex-wrap: wrap;
}

.style-tag {
  padding: 6px 20px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.4);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  user-select: none;
}

.style-tag:hover {
  border-color: rgba(200, 90, 62, 0.3);
  color: rgba(255, 255, 255, 0.7);
}

.style-tag-active {
  border-color: var(--color-cta);
  color: var(--color-cta);
  background: rgba(200, 90, 62, 0.12);
}

.tag-suggestions {
  display: flex;
  justify-content: center;
  gap: var(--space-sm);
  margin-top: var(--space-md);
  flex-wrap: wrap;
}

.suggestion-chip {
  padding: 6px 16px;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition-normal);
  border: 1px solid var(--color-border);
}

.suggestion-chip:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-cta);
  color: var(--color-cta);
}

.hero-transition {
  height: 60px;
  background: linear-gradient(180deg, var(--color-hero-bg), var(--color-background));
}

/* ═══ 生成器场景演示 ═══ */
.demo-scene-label {
  text-align: center;
  padding: 32px 24px 12px;
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.generator-bg {
  background: var(--color-surface-hover);
  padding: 32px 24px 64px;
}

.generator {
  max-width: 1200px;
  margin: 0 auto;
}

.gen-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--color-border);
}

.gen-title {
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
}

.gen-topbar-actions {
  display: flex;
  gap: 8px;
}

.gen-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-body);
}

.gen-btn:hover {
  border-color: var(--color-cta);
  color: var(--color-cta);
}

.gen-btn.primary {
  background: var(--color-cta);
  color: white;
  border-color: var(--color-cta);
}

.gen-btn.primary:hover {
  background: var(--color-cta-hover);
}

.gen-main {
  display: flex;
  height: 560px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--color-surface);
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--color-border);
}

.gen-chat {
  width: 380px;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
}

.gen-chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.msg-row.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}

.msg-avatar.ai {
  background: var(--color-cta-light);
  color: var(--color-cta);
}

.msg-avatar.user {
  background: var(--color-primary);
  color: white;
}

.msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
  background: var(--color-surface-hover);
  color: var(--color-text);
  border-left: 3px solid var(--color-cta);
}

.msg-row.user .msg-bubble {
  background: var(--color-primary);
  color: white;
  border-left: none;
}

.gen-input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.gen-input-area input {
  flex: 1;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-text);
  outline: none;
  background: var(--color-background);
  transition: border-color var(--transition-normal);
}

.gen-input-area input:focus {
  border-color: var(--color-cta);
}

.gen-send {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--color-cta);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background var(--transition-normal);
}

.gen-send:hover {
  background: var(--color-cta-hover);
}

.gen-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-surface-hover);
}

.gen-preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.gen-preview-tab-group {
  display: flex;
  gap: 2px;
  background: var(--color-surface-hover);
  padding: 3px;
  border-radius: var(--radius-sm);
}

.gen-preview-tab {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  border-radius: 3px;
  cursor: pointer;
  font-family: var(--font-body);
}

.gen-preview-tab.active {
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: var(--shadow-sm);
}

.gen-preview-canvas {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.gen-preview-inner {
  width: 100%;
  max-width: 480px;
  aspect-ratio: 4/3;
  background: #fcf9f6;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  padding: 28px;
}

.preview-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 20px;
}

.preview-logo {
  font-family: var(--font-heading);
  font-weight: 700;
  font-size: 17px;
  color: var(--color-text);
}

.preview-nav-links {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.preview-nav-active {
  color: var(--color-cta);
  font-weight: 500;
}

.preview-hero {
  margin-bottom: 20px;
}

.preview-hero-title {
  font-family: var(--font-heading);
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 6px;
}

.preview-hero-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
  max-width: 360px;
}

.preview-cards {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
}

.preview-card {
  background: var(--color-surface-hover);
  border-radius: var(--radius-md);
  padding: 14px;
}

.preview-card-label {
  font-size: 11px;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.preview-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.preview-card-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 4px;
}

.preview-card.highlight {
  background: var(--color-cta-light);
}

.preview-card.highlight .preview-card-label {
  color: var(--color-cta);
  font-weight: 500;
}

.preview-card.highlight .preview-card-meta {
  color: var(--color-cta);
  opacity: 0.7;
}

.features-section,
.steps-section,
.showcase-section {
  padding: var(--space-3xl) var(--space-lg);
}

.section-inner {
  max-width: 1200px;
  margin: 0 auto;
}

.features-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 48px;
}

.features-heading {
  font-family: var(--font-heading);
  font-size: 40px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1.1;
  color: var(--color-text);
  margin-bottom: 8px;
}

.features-top-right {
  display: flex;
  gap: 32px;
}

.big-stat {
  text-align: left;
}

.big-stat-num {
  font-family: var(--font-heading);
  font-size: 36px;
  font-weight: 700;
  color: var(--color-cta);
  line-height: 1;
}

.big-stat-label {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.section-heading {
  font-family: var(--font-heading);
  font-size: 36px;
  font-weight: 700;
  color: var(--color-text);
  text-align: center;
  margin-bottom: var(--space-sm);
  letter-spacing: -0.8px;
}

.section-subheading {
  font-size: 16px;
  color: var(--color-text-secondary);
  text-align: center;
  margin-bottom: var(--space-2xl);
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.bento-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  transition: all var(--transition-normal);
  cursor: default;
}

.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-cta-light);
}

.bento-card.brand-card {
  background: var(--color-cta);
  color: white;
}

.bento-card.brand-card .bento-title,
.bento-card.brand-card .bento-desc {
  color: white;
}

.bento-card.brand-card .bento-desc {
  color: rgba(255, 255, 255, 0.7);
}

.bento-card.brand-card .bento-icon {
  background: rgba(255, 255, 255, 0.12);
  color: white;
}

.bento-card.dark-card {
  background: var(--color-secondary);
  color: white;
}

.bento-card.dark-card .bento-title {
  color: white;
}

.bento-card.dark-card .bento-desc {
  color: rgba(255, 255, 255, 0.55);
}

.bento-card.dark-card .bento-icon {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.7);
}

.bento-span-2 {
  grid-column: span 2;
}

.bento-span-full {
  grid-column: span 4;
}

.bento-icon {
  color: var(--color-cta);
  margin-bottom: var(--space-md);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: var(--color-cta-lighter);
  border-radius: var(--radius-md);
}

.bento-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-sm);
}

.bento-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.65;
}

.steps-row {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: var(--space-md);
  margin-top: var(--space-2xl);
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  flex: 1;
  max-width: 280px;
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-cta);
  color: #fff;
  font-family: var(--font-heading);
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-md);
  box-shadow: 0 4px 12px rgba(200, 90, 62, 0.25);
}

.step-icon {
  color: var(--color-cta);
  margin-bottom: var(--space-md);
}

.step-title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-sm);
}

.step-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.step-arrow {
  color: var(--color-text-muted);
  display: flex;
  align-items: center;
  padding-top: 60px;
}

.showcase-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-lg);
}

.showcase-footer {
  text-align: center;
  margin-top: var(--space-xl);
}

.load-more-btn {
  background: var(--color-surface) !important;
  border-color: var(--color-border) !important;
  color: var(--color-text-secondary) !important;
  transition: all var(--transition-normal);
}

.load-more-btn:hover {
  border-color: var(--color-cta) !important;
  color: var(--color-cta) !important;
}

@media (max-width: 1024px) {
  .hero-title {
    font-size: 48px;
  }

  .features-top {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-lg);
  }

  .bento-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .bento-span-2 {
    grid-column: span 2;
  }

  .bento-span-full {
    grid-column: span 2;
  }

  .showcase-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .gen-main {
    flex-direction: column;
    height: auto;
  }

  .gen-chat {
    width: 100%;
    min-width: unset;
    border-right: none;
    border-bottom: 1px solid var(--color-border);
    max-height: 300px;
  }

  .gen-preview {
    min-height: 400px;
  }
}

@media (max-width: 768px) {
  .hero-section {
    min-height: auto;
    padding: var(--space-2xl) var(--space-md);
  }

  .hero-title {
    font-size: 36px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .bento-grid {
    grid-template-columns: 1fr;
  }

  .bento-span-2,
  .bento-span-full {
    grid-column: span 1;
  }

  .steps-row {
    flex-direction: column;
    align-items: center;
  }

  .step-arrow {
    transform: rotate(90deg);
    padding-top: 0;
    padding: var(--space-sm) 0;
  }

  .showcase-grid {
    grid-template-columns: 1fr;
  }

  .section-heading {
    font-size: 28px;
  }

  .features-section,
  .steps-section,
  .showcase-section {
    padding: var(--space-2xl) var(--space-md);
  }
}

@media (max-width: 375px) {
  .hero-title {
    font-size: 28px;
  }

  .style-templates {
    gap: var(--space-xs);
  }

  .style-tag {
    padding: 4px 12px;
    font-size: 13px;
  }
}
</style>
