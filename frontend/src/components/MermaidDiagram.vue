<script setup>
import { computed, ref, watch } from 'vue'

import { useTheme } from '../composables/useTheme'
import InlineNotification from './InlineNotification.vue'

const props = defineProps({
  code: { type: String, default: '' },
})

const { theme } = useTheme()

const svg = ref('')
const error = ref('')

const hasCode = computed(() => props.code.trim().length > 0)

// Loaded on demand: Mermaid is large, and it is only needed for the Mermaid
// output format. Importing lazily also keeps a broken/missing Mermaid install
// from taking the whole application down with it.
let mermaidPromise = null
function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import('mermaid').then((mod) => mod.default ?? mod)
  }
  return mermaidPromise
}

/** Read a Carbon design token so Mermaid inherits the active theme. */
function token(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function buildConfig() {
  return {
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    themeVariables: {
      fontFamily: "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
      fontSize: '14px',
      background: token('--cds-layer-01', '#ffffff'),
      primaryColor: token('--cds-layer-accent-01', '#e8e8e8'),
      primaryTextColor: token('--cds-text-primary', '#161616'),
      primaryBorderColor: token('--cds-border-strong-01', '#8d8d8d'),
      secondaryColor: token('--cds-layer-02', '#f4f4f4'),
      tertiaryColor: token('--cds-layer-01', '#ffffff'),
      lineColor: token('--cds-border-strong-01', '#8d8d8d'),
      textColor: token('--cds-text-primary', '#161616'),
      nodeBorder: token('--cds-border-strong-01', '#8d8d8d'),
      clusterBkg: token('--cds-layer-02', '#f4f4f4'),
      clusterBorder: token('--cds-border-subtle-01', '#e0e0e0'),
    },
  }
}

async function render() {
  error.value = ''
  svg.value = ''

  const source = props.code?.trim()
  if (!source) return

  try {
    const mermaid = await loadMermaid()
    mermaid.initialize(buildConfig())
    const id = `archigen-diagram-${Math.random().toString(36).slice(2, 10)}`
    const { svg: rendered } = await mermaid.render(id, source)
    svg.value = rendered
  } catch (err) {
    error.value = err?.message ? String(err.message) : String(err)
  }
}

watch([() => props.code, theme], render, { immediate: true })
</script>

<template>
  <div>
    <InlineNotification
      v-if="error"
      kind="warning"
      title="The Mermaid diagram could not be rendered"
      :subtitle="error"
    />

    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-if="svg" class="app-diagram" v-html="svg" />

    <div v-else-if="!error && hasCode" class="app-loading-block">
      <div class="cds--loading cds--loading--small">
        <svg class="cds--loading__svg" viewBox="0 0 100 100" role="progressbar">
          <title>Rendering diagram</title>
          <circle class="cds--loading__background" cx="50" cy="50" r="44" />
          <circle class="cds--loading__stroke" cx="50" cy="50" r="44" />
        </svg>
      </div>
      <span>Rendering diagram …</span>
    </div>
  </div>
</template>
