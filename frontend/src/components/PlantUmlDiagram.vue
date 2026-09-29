<script setup>
import { computed, ref, watch } from 'vue'

import { encodePlantUml, plantUmlServer, plantUmlSvgUrl } from '../api/plantuml'
import InlineNotification from './InlineNotification.vue'

const props = defineProps({
  code: { type: String, default: '' },
})

const url = ref('')
const error = ref('')
const imageFailed = ref(false)

const hasCode = computed(() => props.code.trim().length > 0)

async function encode() {
  error.value = ''
  imageFailed.value = false
  url.value = ''

  if (!hasCode.value) return

  try {
    url.value = plantUmlSvgUrl(await encodePlantUml(props.code))
  } catch (err) {
    error.value = err?.message || String(err)
  }
}

watch(() => props.code, encode, { immediate: true })
</script>

<template>
  <div>
    <InlineNotification
      v-if="error"
      kind="warning"
      title="PlantUML preview unavailable"
      :subtitle="error"
    />

    <div v-else-if="imageFailed" class="app-diagram">
      <p class="app-empty__text" style="margin: 0">
        The PlantUML server could not render this diagram. Copy the source from the “DSL source”
        tab and render it locally.
      </p>
    </div>

    <template v-else-if="url">
      <div class="app-diagram">
        <img
          :src="url"
          alt="Rendered PlantUML diagram"
          loading="lazy"
          @error="imageFailed = true"
        />
      </div>
      <p class="app-panel__hint" style="margin: 1rem 0 0">
        Rendered by {{ plantUmlServer }} — set VITE_PLANTUML_SERVER to a local instance to keep the
        source on your machine.
      </p>
    </template>

    <div v-else class="app-loading-block">
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

<style scoped>
.app-diagram img {
  max-inline-size: 100%;
  block-size: auto;
}
</style>
