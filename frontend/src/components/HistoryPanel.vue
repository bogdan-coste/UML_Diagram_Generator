<script setup>
import { Renew20 } from '@carbon/icons-vue'

import InlineNotification from './InlineNotification.vue'

defineProps({
  entries: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'select'])

function formatTime(iso) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? (iso ?? '—') : date.toLocaleString()
}
</script>

<template>
  <section class="app-panel">
    <div class="app-row" style="justify-content: space-between">
      <div>
        <h2 class="app-panel__title">Recent generations</h2>
        <p class="app-panel__hint" style="margin-bottom: 0">
          The most recent diagrams produced by this instance.
        </p>
      </div>
      <button class="cds--btn cds--btn--ghost cds--btn--sm" type="button" :disabled="loading" @click="emit('refresh')">
        <span>Refresh</span>
        <Renew20 class="cds--btn__icon" />
      </button>
    </div>

    <InlineNotification v-if="error" kind="error" title="Could not load history" :subtitle="error" />

    <div v-if="loading" class="app-loading-block">
      <div class="cds--loading cds--loading--small">
        <svg class="cds--loading__svg" viewBox="0 0 100 100" role="progressbar">
          <title>Loading history</title>
          <circle class="cds--loading__background" cx="50" cy="50" r="44" />
          <circle class="cds--loading__stroke" cx="50" cy="50" r="44" />
        </svg>
      </div>
      <span>Loading …</span>
    </div>

    <div v-else-if="!entries.length" class="app-empty" style="margin-top: 1.5rem">
      <p class="app-empty__title">Nothing here yet</p>
      <p class="app-empty__text">Generate a diagram and it will show up in this list.</p>
    </div>

    <div v-else class="cds--data-table-container" style="margin-top: 1.5rem">
      <table class="cds--data-table">
        <thead>
          <tr>
            <th scope="col"><span class="cds--table-header-label">When</span></th>
            <th scope="col"><span class="cds--table-header-label">Title</span></th>
            <th scope="col"><span class="cds--table-header-label">Input</span></th>
            <th scope="col"><span class="cds--table-header-label">Diagram</span></th>
            <th scope="col"><span class="cds--table-header-label">Format</span></th>
            <th scope="col"><span class="cds--table-header-label">Size</span></th>
            <th scope="col"><span class="cds--table-header-label">Open</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="entry.id">
            <td>{{ formatTime(entry.timestamp) }}</td>
            <td>{{ entry.title || '—' }}</td>
            <td>{{ entry.mode }}</td>
            <td>{{ entry.diagram_type }}</td>
            <td>{{ entry.format }}</td>
            <td>{{ entry.nodes ?? '—' }} / {{ entry.edges ?? '—' }}</td>
            <td>
              <button
                class="cds--btn cds--btn--ghost cds--btn--sm"
                type="button"
                :disabled="!entry.result"
                @click="emit('select', entry)"
              >
                Open
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
