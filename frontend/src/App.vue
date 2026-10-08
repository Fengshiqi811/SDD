<template>
  <div class="od-app">
    <!-- ① 顶部操作栏 -->
    <header class="topbar">
      <div class="topbar__brand">
        <span class="topbar__logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>
        </span>
        <div class="topbar__titles">
          <h1 class="topbar__title">智能日报生成器</h1>
          <span class="topbar__sub">PageDailyReport · 采集明细 · 筛选 · 预览 · 导出</span>
        </div>
      </div>
      <span class="topbar__spacer"></span>
      <div class="topbar__actions">
        <button @click="handleRefresh" class="btn btn--default" :class="{ 'btn--loading': loading }" type="button" :disabled="loading">
          <span v-if="loading" class="btn__spin" aria-hidden="true"></span>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
          刷新
        </button>
        <button @click="handleCopyMd" class="btn btn--default" type="button" :disabled="!reportContent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2"/></svg>
          复制 Markdown
        </button>
        <button @click="handleExportHtml" class="btn btn--primary" type="button" :disabled="!reportContent">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M5 21h14"/></svg>
          导出 HTML
        </button>
      </div>
    </header>

    <!-- ② 筛选控制区 -->
    <section class="filterbar" aria-label="筛选控制区">
      <div class="field field--date">
        <span class="field__label">日期<span class="req" aria-hidden="true">*</span><span class="visually-hidden">（必填）</span></span>
        <input type="date" v-model="targetDate" />
      </div>
      <div class="field field--members">
        <span class="field__label">团队成员</span>
        <input v-model="memberName" type="text" placeholder="输入成员姓名" />
      </div>
      <div class="filterbar__spacer"></div>
      <div class="filterbar__meta">
        <span class="status-chip" :class="statusChipClass">
          <span class="status-chip__dot" aria-hidden="true"></span>
          采集状态：{{ loading ? '采集中...' : statusText }}
        </span>
      </div>
    </section>

    <!-- 告警提示 -->
    <div v-if="errorMsg" class="banners">
      <div class="alert alert--error" role="alert">
        <span class="alert__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/></svg>
        </span>
        <div class="alert__body">
          <div class="alert__title">数据加载失败</div>
          <div class="alert__desc">{{ errorMsg }}</div>
        </div>
        <button class="alert__close" type="button" aria-label="关闭" @click="errorMsg = ''">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>
    </div>

    <!-- ③ 原始数据区（左） ④ 日报成品预览区（右） -->
    <main class="workspace">
      <section class="pane" aria-label="原始数据区">
        <div class="pane__head">
          <h3 class="pane__title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h14"/></svg>
            原始数据
          </h3>
          <div class="source-pills" aria-hidden="true">
            <span class="source-pill source-pill--github">GitHub</span>
            <span class="source-pill source-pill--lark">飞书任务</span>
            <span class="source-pill source-pill--msg">飞书消息</span>
          </div>
          <span class="pane__spacer"></span>
          <span class="pane__hint">JSON 采集明细</span>
        </div>
        <div class="pane__body">
          <div v-if="loading" class="loading-mask">
            <div class="loading-box">
              <div class="spinner" aria-hidden="true"></div>
              <span>正在采集数据…</span>
            </div>
          </div>
          <pre v-if="rawData" class="raw-json">{{ rawData }}</pre>
          <div v-else class="state">
            <div class="state__art state__art--brand" aria-hidden="true">
              <svg viewBox="0 0 64 64" fill="none">
                <rect x="10" y="14" width="44" height="36" rx="6" stroke="currentColor" stroke-width="2.2"/>
                <path d="M18 24h28M18 32h20M18 40h24" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
                <circle cx="46" cy="18" r="8" fill="#1476ff" stroke="none"/>
                <path d="M43.5 18.2l2 2 3.5-3.8" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="state__title">等待采集</div>
            <p class="state__desc">选择日期后点击「刷新」，这里会展示 GitHub Commit、飞书任务与消息的原始明细。</p>
          </div>
        </div>
      </section>

      <section class="pane" aria-label="日报成品预览区">
        <div class="pane__head">
          <h3 class="pane__title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>
            日报预览
          </h3>
          <span class="pane__spacer"></span>
          <span class="pane__hint">Markdown / HTML</span>
        </div>
        <div class="pane__body pane__body--pad">
          <div v-if="loading" class="loading-mask">
            <div class="loading-box">
              <div class="spinner" aria-hidden="true"></div>
              <span>正在生成日报…</span>
            </div>
          </div>
          <div v-if="reportContent" class="markdown" v-html="renderMarkdown(reportContent)"></div>
          <div v-else class="state">
            <div class="state__art state__art--preview" aria-hidden="true">
              <svg viewBox="0 0 64 64" fill="none">
                <path d="M16 12h24l10 10v30a4 4 0 0 1-4 4H16a4 4 0 0 1-4-4V16a4 4 0 0 1 4-4z" stroke="currentColor" stroke-width="2.2"/>
                <path d="M40 12v10h10" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>
                <path d="M22 30h20M22 38h16M22 46h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
                <circle cx="48" cy="46" r="9" fill="#5cb300" stroke="none"/>
                <path d="M44.8 46.2l2.4 2.4 4.4-5" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="state__title">今日无预览</div>
            <p class="state__desc">日报成品会在这里渲染。生成后可一键复制 Markdown 或导出 HTML 文件。</p>
            <div class="state__actions">
              <button class="btn btn--primary" type="button" @click="handleRefresh" :disabled="loading">
                立即生成
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <div class="toast-host" aria-live="polite">
    <div v-if="toastMsg" class="toast toast--success">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
      {{ toastMsg }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import axios from 'axios'

const targetDate = ref('')
const memberName = ref('')
const rawData = ref('')
const reportContent = ref('')
const loading = ref(false)
const errorMsg = ref('')
const statusText = ref('—')
const toastMsg = ref('')
let toastTimer = null

const statusChipClass = computed(() => {
  if (loading.value) return 'status-chip--loading'
  if (statusText.value === '失败') return 'status-chip--err'
  if (statusText.value === '采集完成') return 'status-chip--ok'
  return 'status-chip--idle'
})

const showToast = (msg) => {
  toastMsg.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMsg.value = ''
  }, 2200)
}

const renderMarkdown = (mdText) => {
  if (!mdText) return ''
  return marked.parse(mdText)
}

const handleRefresh = async () => {
  errorMsg.value = ''
  if (!targetDate.value) {
    errorMsg.value = '请选择日期'
    return
  }
  loading.value = true
  statusText.value = '请求中'
  try {
    const res = await axios.post('/api/report', {
      date: targetDate.value,
      member: memberName.value
    })
    rawData.value = JSON.stringify(res.data, null, 2)
    reportContent.value = res.data.data
    statusText.value = '采集完成'
  } catch (err) {
    console.error(err)
    errorMsg.value = '数据采集失败，请确认后端服务已经启动'
    statusText.value = '失败'
  } finally {
    loading.value = false
  }
}

const handleCopyMd = async () => {
  if (!reportContent.value) return
  await navigator.clipboard.writeText(reportContent.value)
  showToast('Markdown 已复制到剪贴板')
}

const handleExportHtml = () => {
  if (!reportContent.value) return
  const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>日报导出</title></head><body>${renderMarkdown(reportContent.value)}</body></html>`
  const blob = new Blob([html], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'daily-report.html'
  a.click()
  URL.revokeObjectURL(url)
  showToast('HTML 已导出')
}
</script>
