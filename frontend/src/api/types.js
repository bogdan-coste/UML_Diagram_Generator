/**
 * Shared data shapes exchanged with the ArchiGen REST API.
 *
 * These are JSDoc typedefs (this project is plain JavaScript) so editors and
 * `jsconfig.json` can still offer completion. Keep them in sync with
 * `src/api/schemas.py` on the backend.
 *
 * @typedef {'text' | 'story' | 'code' | 'folder'} InputMode
 *   How the user supplied the description of the system.
 *
 * @typedef {'class' | 'flowchart' | 'sequence' | 'er' | 'component' | 'deployment' | 'state'} DiagramType
 *
 * @typedef {'mermaid' | 'plantuml' | 'structurizr' | 'graphviz'} OutputFormat
 *
 * @typedef {Object} GenerateRequest
 * @property {InputMode}    mode          Input mode.
 * @property {string}       content       Free text, user story, source code, or a folder path.
 * @property {DiagramType}  diagram_type  Requested diagram kind.
 * @property {OutputFormat} format        Requested DSL dialect.
 * @property {boolean}      [use_ai]      Enable LLM semantic enrichment.
 * @property {boolean}      [use_rag]     Enable RAG retrieval (requires an indexed vector store).
 *
 * @typedef {Object} GraphSummary
 * @property {string}   [title]
 * @property {number}   nodes
 * @property {number}   edges
 * @property {number}   [classes]
 * @property {number}   [interfaces]
 * @property {string[]} [contexts]
 *
 * @typedef {Object} GenerateResponse
 * @property {OutputFormat}   format
 * @property {DiagramType}    diagram_type
 * @property {string}         dsl             Rendered DSL source.
 * @property {GraphSummary}   graph           Statistics about the generated graph.
 * @property {string[]}       [files]         Files parsed (folder/code modes).
 * @property {string[]}       [warnings]
 *
 * @typedef {Object} HealthResponse
 * @property {'ok' | 'degraded' | 'error'} status
 * @property {string}  model      LLM model in use (e.g. `gpt-4o-mini`).
 * @property {boolean} llm        Whether an LLM endpoint is configured.
 * @property {boolean} rag        Whether RAG retrieval is enabled.
 * @property {boolean} cuda       Whether a CUDA device is available.
 * @property {string}  [version]
 *
 * @typedef {Object} HistoryEntry
 * @property {string}      id
 * @property {string}      timestamp   ISO-8601 timestamp.
 * @property {InputMode}   mode
 * @property {DiagramType} diagram_type
 * @property {OutputFormat} format
 * @property {string}      [title]
 * @property {number}      [nodes]
 * @property {number}      [edges]
 * @property {GenerateResponse} [result]  Present when the backend caches full results.
 */

export {}
