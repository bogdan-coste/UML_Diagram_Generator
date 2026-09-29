<script setup>
import { computed } from 'vue'
import { Renew20 } from '@carbon/icons-vue'

const props = defineProps({
  health: { type: Object, default: null },
  error: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  mock: { type: Boolean, default: false },
  theme: { type: String, default: 'white' },
  themes: { type: Array, default: () => [] },
})

const emit = defineEmits(['refresh', 'set-theme'])

const statusTag = computed(() => {
  if (props.loading) return { kind: 'gray', label: 'Checking…' }
  if (props.error) return { kind: 'red', label: 'API offline' }
  const status = props.health?.status
  if (status === 'ok') return { kind: 'green', label: 'Healthy' }
  if (status) return { kind: 'cool-gray', label: status[0].toUpperCase() + status.slice(1) }
  return { kind: 'gray', label: 'Unknown' }
})

const meta = computed(() => {
  const h = props.health
  if (!h) return props.error || 'Waiting for the API …'
  const parts = [
    `finetuned ${h.finetuned ? `ready (${h.finetuned_model ?? 'unknown'})` : 'missing'}`,
    // The model name is only meaningful once an endpoint is configured; showing
    // it bare next to `finetuned` reads as "the model in use", which it is not.
    `llm ${h.llm ? `${h.model} configured` : 'not configured'}`,
    `rag ${h.rag ? 'on' : 'off'}`,
    `cuda ${h.cuda ? 'available' : 'none'}`,
  ]
  if (h.version) parts.push(`v${h.version}`)
  return parts.join('  ·  ')
})
</script>

<template>
  <div class="app-statusbar">
    <span class="cds--tag" :class="`cds--tag--${statusTag.kind}`">
      <span class="cds--tag__label">{{ statusTag.label }}</span>
    </span>

    <span v-if="mock" class="cds--tag cds--tag--magenta">
      <span class="cds--tag__label">Mock data</span>
    </span>

    <span class="app-statusbar__meta">{{ meta }}</span>

    <span class="app-statusbar__spacer" />

    <div class="cds--select cds--select--inline app-statusbar__theme">
      <label class="cds--label" for="theme-select">Theme</label>
      <div class="cds--select-input__wrapper">
        <select
          id="theme-select"
          class="cds--select-input"
          :value="theme"
          @change="emit('set-theme', $event.target.value)"
        >
          <option v-for="t in themes" :key="t.id" class="cds--select-option" :value="t.id">
            {{ t.label }}
          </option>
        </select>
        <svg class="cds--select__arrow" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M8 11L3 6l.7-.7L8 9.6l4.3-4.3L13 6z" />
        </svg>
      </div>
    </div>

    <button
      class="cds--btn cds--btn--ghost cds--btn--sm cds--btn--icon-only"
      type="button"
      title="Refresh system status"
      @click="emit('refresh')"
    >
      <Renew20 />
    </button>
  </div>
</template>
