<script setup>
defineProps({
  health: { type: Object, default: null },
})
</script>

<template>
  <div class="app-split app-split--wide-first">
    <section class="app-panel">
      <h2 class="app-panel__title">About ArchiGen AI</h2>
      <p class="app-panel__hint">
        ArchiGen AI turns a description, a user story, a code snippet, or a whole repository into an
        architecture diagram. Structural facts are extracted deterministically; a local language
        model is used only for the subjective parts (naming contexts, summarising responsibilities).
      </p>

      <h3 class="app-panel__title" style="margin-top: 1.5rem">Pipeline</h3>
      <ol class="app-link-list">
        <li>Ingest — files are traversed and parsed with tree-sitter (Java + Python).</li>
        <li>
          Graph — classes and interfaces become nodes; inheritance, implementation, composition and
          dependency become typed edges.
        </li>
        <li>Enrich — the configured LLM assigns bounded-context names and one-line responsibilities.</li>
        <li>
          Export — the graph is rendered to PlantUML, Mermaid, Structurizr DSL, or Graphviz DOT, and
          PlantUML is the default visualization.
        </li>
      </ol>
    </section>

    <section class="app-panel">
      <h2 class="app-panel__title">Backend</h2>
      <p class="app-panel__hint">
        This UI talks to the FastAPI service documented in the project README.
      </p>
      <ul class="app-link-list">
        <li><code>GET /health</code> — service and model status</li>
        <li><code>POST /generate</code> — build a diagram</li>
        <li><code>GET /history</code> — recent generations</li>
      </ul>

      <h3 class="app-panel__title" style="margin-top: 1.5rem">Runtime</h3>
      <ul class="app-link-list">
        <li>Model: {{ health?.model ?? 'unknown' }}</li>
        <li>LLM: {{ health?.llm ? 'configured' : 'not configured' }}</li>
        <li>RAG: {{ health?.rag ? 'enabled' : 'disabled' }}</li>
        <li>CUDA: {{ health?.cuda ? 'available' : 'not available' }}</li>
      </ul>
    </section>
  </div>
</template>
