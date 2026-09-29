<script setup>
import { onMounted, ref } from 'vue'

import AboutPanel from './components/AboutPanel.vue'
import AppHeader from './components/AppHeader.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import InputPanel from './components/InputPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import StatusBar from './components/StatusBar.vue'

import { api, usingMock } from './api/client'
import { useTheme } from './composables/useTheme'

const NAV_ITEMS = [
  { id: 'generate', label: 'Generate' },
  { id: 'history', label: 'History' },
  { id: 'about', label: 'About' },
]

const view = ref('generate')

const { theme, themes, setTheme } = useTheme()

const health = ref(null)
const healthError = ref('')
const healthLoading = ref(false)

const result = ref(null)
const generateError = ref('')
const generating = ref(false)

const history = ref([])
const historyLoading = ref(false)
const historyError = ref('')

async function loadHealth() {
  healthLoading.value = true
  healthError.value = ''
  try {
    health.value = await api.health()
  } catch (err) {
    health.value = null
    healthError.value = err?.message || 'Unable to reach the API'
  } finally {
    healthLoading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    history.value = await api.history(20)
  } catch (err) {
    history.value = []
    historyError.value = err?.message || 'Unable to load history'
  } finally {
    historyLoading.value = false
  }
}

async function handleGenerate(payload) {
  generating.value = true
  generateError.value = ''
  try {
    result.value = await api.generate(payload)
    view.value = 'generate'
    loadHistory()
  } catch (err) {
    generateError.value = err?.message || 'Generation failed'
  } finally {
    generating.value = false
  }
}

function openHistoryEntry(entry) {
  if (entry?.result) {
    result.value = entry.result
    view.value = 'generate'
  }
}

onMounted(() => {
  loadHealth()
  loadHistory()
})
</script>

<template>
  <div class="app-shell">
    <AppHeader :items="NAV_ITEMS" :active="view" @navigate="view = $event" />

    <main class="app-main">
      <div class="app-main__inner">
        <div class="app-lead">
          <h1 class="app-lead__title">Architecture <strong>Diagram Generator</strong></h1>
          <p class="app-lead__subtitle">
            Describe a system, paste code, or point at a repository, and get a diagram you can read,
            copy, and download — rendered in the browser as PlantUML or Mermaid, or exported as
            Structurizr DSL or Graphviz DOT.
          </p>
        </div>

        <StatusBar
          :health="health"
          :error="healthError"
          :loading="healthLoading"
          :mock="usingMock"
          :theme="theme"
          :themes="themes"
          @refresh="loadHealth"
          @set-theme="setTheme"
        />

        <div v-if="view === 'generate'" class="app-split">
          <InputPanel :generating="generating" :error="generateError" @generate="handleGenerate" />
          <ResultPanel :result="result" :generating="generating" />
        </div>

        <HistoryPanel
          v-else-if="view === 'history'"
          :entries="history"
          :loading="historyLoading"
          :error="historyError"
          @refresh="loadHistory"
          @select="openHistoryEntry"
        />

        <AboutPanel v-else :health="health" />
      </div>
    </main>
  </div>
</template>
