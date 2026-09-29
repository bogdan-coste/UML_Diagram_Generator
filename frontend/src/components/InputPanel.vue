<script setup>
import { computed, reactive } from 'vue'
import { ArrowRight20 } from '@carbon/icons-vue'

import InlineNotification from './InlineNotification.vue'

const props = defineProps({
  generating: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['generate'])

const MODES = [
  { id: 'text', label: 'Natural language' },
  { id: 'story', label: 'User story' },
  { id: 'code', label: 'Source code' },
  { id: 'folder', label: 'Folder' },
]

const DIAGRAM_TYPES = [
  { id: 'class', label: 'Class diagram' },
  { id: 'flowchart', label: 'Flowchart' },
  { id: 'sequence', label: 'Sequence diagram' },
  { id: 'er', label: 'Entity-relationship diagram' },
  { id: 'component', label: 'Component diagram' },
  { id: 'deployment', label: 'Deployment diagram' },
  { id: 'state', label: 'State diagram' },
]

const FORMATS = [
  { id: 'plantuml', label: 'PlantUML' },
  { id: 'mermaid', label: 'Mermaid' },
  { id: 'structurizr', label: 'Structurizr DSL' },
  { id: 'graphviz', label: 'Graphviz DOT' },
]

const COPY = {
  text: {
    label: 'System description',
    placeholder: 'Describe the system, e.g. "A checkout service with an order controller, an order service backed by a repository, and a payment gateway …"',
  },
  story: {
    label: 'User story',
    placeholder: 'As a returning customer I want to save my cart so that I can resume checkout on another device.',
  },
  code: {
    label: 'Source code',
    placeholder: 'Paste Python or Java source. Classes, interfaces and their relationships are extracted with tree-sitter.',
  },
  folder: {
    label: 'Repository path',
    placeholder: '/path/to/project',
  },
}

const form = reactive({
  mode: 'text',
  content: '',
  diagramType: 'class',
  format: 'plantuml',
  useAi: true,
  useRag: false,
})

const copy = computed(() => COPY[form.mode] ?? COPY.text)
const isFolderMode = computed(() => form.mode === 'folder')
const canSubmit = computed(() => form.content.trim().length > 0 && !props.generating)

function setMode(id) {
  if (form.mode !== id) {
    form.mode = id
    form.content = ''
  }
}

function submit() {
  if (!canSubmit.value) return
  emit('generate', {
    mode: form.mode,
    content: form.content.trim(),
    diagram_type: form.diagramType,
    format: form.format,
    use_ai: form.useAi,
    use_rag: form.useRag,
  })
}
</script>

<template>
  <section class="app-panel">
    <h2 class="app-panel__title">Input</h2>
    <p class="app-panel__hint">
      Describe the architecture, paste code, or point at a repository. The pipeline analyses it and
      emits a diagram in the format you choose.
    </p>

    <div class="app-switcher" role="tablist" aria-label="Input mode">
      <button
        v-for="mode in MODES"
        :key="mode.id"
        class="app-switcher__btn"
        :class="{ 'app-switcher__btn--active': form.mode === mode.id }"
        type="button"
        role="tab"
        :aria-selected="form.mode === mode.id"
        @click="setMode(mode.id)"
      >
        {{ mode.label }}
      </button>
    </div>

    <div class="app-stack">
      <div class="cds--form-item">
        <label class="cds--label" for="input-content">{{ copy.label }}</label>

        <div v-if="isFolderMode" class="cds--text-input__field-wrapper">
          <input
            id="input-content"
            v-model="form.content"
            class="cds--text-input"
            type="text"
            :placeholder="copy.placeholder"
            :disabled="generating"
          />
        </div>

        <div v-else class="cds--text-area__wrapper">
          <textarea
            id="input-content"
            v-model="form.content"
            class="cds--text-area"
            :class="{ 'app-textarea--code': form.mode === 'code' }"
            :placeholder="copy.placeholder"
            :disabled="generating"
            rows="12"
          ></textarea>
        </div>
      </div>

      <div class="app-field-grid">
        <div class="cds--select">
            <label class="cds--label" for="diagram-type">Diagram type</label>
            <div class="cds--select-input__wrapper">
              <select
                id="diagram-type"
                v-model="form.diagramType"
                class="cds--select-input"
                :disabled="generating"
              >
                <option v-for="t in DIAGRAM_TYPES" :key="t.id" class="cds--select-option" :value="t.id">
                  {{ t.label }}
                </option>
              </select>
              <svg class="cds--select__arrow" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M8 11L3 6l.7-.7L8 9.6l4.3-4.3L13 6z" />
              </svg>
            </div>
          </div>

        <div class="cds--select">
          <label class="cds--label" for="output-format">Output format</label>
          <div class="cds--select-input__wrapper">
              <select
                id="output-format"
                v-model="form.format"
                class="cds--select-input"
                :disabled="generating"
              >
                <option v-for="f in FORMATS" :key="f.id" class="cds--select-option" :value="f.id">
                  {{ f.label }}
                </option>
              </select>
              <svg class="cds--select__arrow" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M8 11L3 6l.7-.7L8 9.6l4.3-4.3L13 6z" />
              </svg>
            </div>
          </div>
      </div>

      <div class="app-checkbox-row">
        <div class="cds--form-item cds--checkbox-wrapper">
          <input id="use-ai" v-model="form.useAi" class="cds--checkbox" type="checkbox" :disabled="generating" />
          <label class="cds--checkbox-label" for="use-ai">
            <span class="cds--checkbox-label-text">AI enrichment (LLM)</span>
          </label>
        </div>

        <div class="cds--form-item cds--checkbox-wrapper">
          <input id="use-rag" v-model="form.useRag" class="cds--checkbox" type="checkbox" :disabled="generating" />
          <label class="cds--checkbox-label" for="use-rag">
            <span class="cds--checkbox-label-text">Retrieve similar examples (RAG)</span>
          </label>
        </div>
      </div>
    </div>

    <InlineNotification v-if="error" kind="error" title="Generation failed" :subtitle="error" />

    <div class="app-form-actions">
      <button
        class="cds--btn cds--btn--primary"
        type="button"
        :disabled="!canSubmit"
        @click="submit"
      >
        <span>{{ generating ? 'Generating…' : 'Generate diagram' }}</span>
        <ArrowRight20 class="cds--btn__icon" />
      </button>

      <div v-if="generating" class="cds--loading cds--loading--small">
        <svg class="cds--loading__svg" viewBox="0 0 100 100" role="progressbar">
          <title>Generating diagram</title>
          <circle class="cds--loading__background" cx="50" cy="50" r="44" />
          <circle class="cds--loading__stroke" cx="50" cy="50" r="44" />
        </svg>
      </div>
    </div>
  </section>
</template>
