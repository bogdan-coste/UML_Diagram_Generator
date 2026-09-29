<script setup>
import { computed, ref, watch } from 'vue'

import InlineNotification from './InlineNotification.vue'
import MermaidDiagram from './MermaidDiagram.vue'
import PlantUmlDiagram from './PlantUmlDiagram.vue'
import DslViewer from './DslViewer.vue'

const props = defineProps({
  result: { type: Object, default: null },
  generating: { type: Boolean, default: false },
})

const VIEWS = [
  { id: 'diagram', label: 'Diagram' },
  { id: 'source', label: 'DSL source' },
  { id: 'details', label: 'Details' },
]

const FORMAT_META = {
  mermaid: { label: 'Mermaid', filename: 'architecture.mmd' },
  plantuml: { label: 'PlantUML', filename: 'architecture.puml' },
  structurizr: { label: 'Structurizr DSL', filename: 'workspace.dsl' },
  graphviz: { label: 'Graphviz DOT', filename: 'architecture.dot' },
}

const active = ref('diagram')

watch(
  () => props.result,
  () => {
    active.value = 'diagram'
  },
)

const meta = computed(() => FORMAT_META[props.result?.format] ?? FORMAT_META.plantuml)

const isMermaid = computed(() => props.result?.format === 'mermaid')

const isPlantUml = computed(() => props.result?.format === 'plantuml')

const stats = computed(() => {
  const g = props.result?.graph ?? {}
  return [
    { label: 'Nodes', value: g.nodes ?? '—' },
    { label: 'Edges', value: g.edges ?? '—' },
    { label: 'Classes', value: g.classes ?? '—' },
    { label: 'Interfaces', value: g.interfaces ?? '—' },
    { label: 'Contexts', value: g.contexts ? g.contexts.length : '—' },
  ]
})

const contexts = computed(() => props.result?.graph?.contexts ?? [])
const files = computed(() => props.result?.files ?? [])
const warnings = computed(() => props.result?.warnings ?? [])
</script>

<template>
  <section class="app-panel">
    <div class="app-row">
      <div>
        <h2 class="app-panel__title">{{ result?.graph?.title || 'Output' }}</h2>
        <p v-if="result" class="app-panel__hint" style="margin-bottom: 0">
          {{ meta.label }} · {{ result.diagram_type }} diagram
        </p>
        <p v-else class="app-panel__hint" style="margin-bottom: 0">
          Generated diagrams appear here.
        </p>
      </div>
    </div>

    <div v-if="!result" style="margin-top: 1.5rem">
      <div v-if="generating" class="app-loading-block">
        <div class="cds--loading cds--loading--small">
          <svg class="cds--loading__svg" viewBox="0 0 100 100" role="progressbar">
            <title>Generating</title>
            <circle class="cds--loading__background" cx="50" cy="50" r="44" />
            <circle class="cds--loading__stroke" cx="50" cy="50" r="44" />
          </svg>
        </div>
        <span>Analysing input and building the graph …</span>
      </div>

      <div v-else class="app-empty">
        <p class="app-empty__title">No diagram yet</p>
        <p class="app-empty__text">
          Choose an input mode, describe the system, then select
          <strong>Generate diagram</strong>. The result will render here.
        </p>
      </div>
    </div>

    <template v-else>
      <div class="app-switcher" role="tablist" aria-label="Result views" style="margin-top: 1.5rem">
        <button
          v-for="view in VIEWS"
          :key="view.id"
          class="app-switcher__btn"
          :class="{ 'app-switcher__btn--active': active === view.id }"
          type="button"
          role="tab"
          :aria-selected="active === view.id"
          @click="active = view.id"
        >
          {{ view.label }}
        </button>
      </div>

      <!-- Diagram -->
      <div v-if="active === 'diagram'">
        <PlantUmlDiagram v-if="isPlantUml" :code="result.dsl" />
        <MermaidDiagram v-else-if="isMermaid" :code="result.dsl" />
        <InlineNotification
          v-else
          kind="info"
          low-contrast
          title="Preview is only available for PlantUML and Mermaid"
          :subtitle="`${meta.label} diagrams are exported as source. Copy or download it from the “DSL source” tab.`"
        />
      </div>

      <!-- DSL source -->
      <DslViewer
        v-else-if="active === 'source'"
        :code="result.dsl"
        :filename="meta.filename"
        :language="result.format"
      />

      <!-- Details -->
      <div v-else class="app-stack">
        <div class="app-stats">
          <div v-for="stat in stats" :key="stat.label" class="app-stat">
            <div class="app-stat__value">{{ stat.value }}</div>
            <div class="app-stat__label">{{ stat.label }}</div>
          </div>
        </div>

        <div v-if="contexts.length">
          <h3 class="app-panel__title">Detected contexts</h3>
          <div class="app-tag-row">
            <span v-for="ctx in contexts" :key="ctx" class="cds--tag cds--tag--cool-gray">
              <span class="cds--tag__label">{{ ctx }}</span>
            </span>
          </div>
        </div>

        <div v-if="files.length">
          <h3 class="app-panel__title">Analysed files</h3>
          <ul class="app-link-list app-mono">
            <li v-for="file in files" :key="file">{{ file }}</li>
          </ul>
        </div>

        <InlineNotification
          v-for="(warning, index) in warnings"
          :key="index"
          kind="warning"
          low-contrast
          title="Warning"
          :subtitle="warning"
        />
      </div>
    </template>
  </section>
</template>
