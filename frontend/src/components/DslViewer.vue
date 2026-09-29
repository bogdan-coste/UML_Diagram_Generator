<script setup>
import { computed, ref } from 'vue'
import { Copy20, Checkmark20, Download20 } from '@carbon/icons-vue'

const props = defineProps({
  code: { type: String, default: '' },
  language: { type: String, default: 'text' },
  filename: { type: String, default: 'diagram.txt' },
})

const copied = ref(false)
let resetTimer = null

async function copy() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    clearTimeout(resetTimer)
    resetTimer = setTimeout(() => (copied.value = false), 2000)
  } catch {
    // Clipboard API is unavailable (e.g. insecure context) — ignore.
  }
}

const hasCode = computed(() => props.code.trim().length > 0)

function download() {
  const blob = new Blob([props.code], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = props.filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="app-code">
    <div class="app-code__bar">
      <span class="app-code__lang">{{ filename }}</span>
      <div class="app-code__actions">
        <button
          class="cds--btn cds--btn--ghost cds--btn--sm cds--btn--icon-only"
          type="button"
          :disabled="!hasCode"
          :title="copied ? 'Copied' : 'Copy to clipboard'"
          @click="copy"
        >
          <Checkmark20 v-if="copied" />
          <Copy20 v-else />
        </button>
        <button
          class="cds--btn cds--btn--ghost cds--btn--sm cds--btn--icon-only"
          type="button"
          :disabled="!hasCode"
          title="Download"
          @click="download"
        >
          <Download20 />
        </button>
      </div>
    </div>
    <pre class="app-code__body"><code>{{ code }}</code></pre>
  </div>
</template>
