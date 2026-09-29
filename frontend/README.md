# ArchiGen AI — Frontend

Vue 3 single-page interface for the Architecture Diagram Generator, styled with
the [IBM Carbon Design System](https://carbondesignsystem.com/) (v11).
Diagrams render in the browser with [PlantUML](https://plantuml.com/) (the
default output format) and [Mermaid](https://mermaid.js.org/).

## Requirements

- Node.js `^22.18.0 || >=24.12.0` (see `package.json` → `engines`)
- npm

## Install

```sh
npm install
```

> The Carbon and Mermaid packages are declared in `package.json` but may still
> need to be fetched the first time you run this.

## Run

```sh
npm run dev      # dev server on http://localhost:5173
npm run build    # production bundle into dist/
npm run preview  # serve the built bundle
npm run lint     # oxlint + eslint
npm run format   # prettier
```

## Talking to the backend

In development Vite proxies `/api/*` to the FastAPI service on
`http://localhost:8000`, stripping the `/api` prefix, so the backend can expose
the endpoints at the root (`/health`, `/generate`, `/history`). See the proxy
block in `vite.config.js`.

Configuration is via Vite env vars — copy `.env.example` to `.env` and adjust:

| Variable               | Default                             | Purpose                                                |
| ---------------------- | ----------------------------------- | ------------------------------------------------------ |
| `VITE_API_BASE_URL`    | `/api`                              | Base URL for API calls.                                |
| `VITE_USE_MOCK`        | `false`                             | Serve canned data from `src/api/mock.js` (no backend). |
| `VITE_PLANTUML_SERVER` | `https://www.plantuml.com/plantuml` | PlantUML server used to render diagrams in the browser. |

To review the UI without the backend:

```sh
VITE_USE_MOCK=true npm run dev
```

## API contract

These shapes are documented as JSDoc typedefs in `src/api/types.js`.

| Endpoint        | Method | Response                                   |
| --------------- | ------ | ------------------------------------------ |
| `/health`       | GET    | `HealthResponse`                           |
| `/generate`     | POST   | `GenerateResponse`, given a `GenerateRequest` |
| `/history`      | GET    | `HistoryEntry[]`                           |

`GenerateRequest`:

```jsonc
{
  "mode": "text",            // text | story | code | folder
  "content": "…",            // description, story, code, or folder path
  "diagram_type": "class",   // class | flowchart | sequence | er | component | deployment | state
  "format": "plantuml",      // plantuml | mermaid | structurizr | graphviz
  "use_ai": true,            // optional — LLM semantic enrichment
  "use_rag": false           // optional — retrieve similar examples
}
```

`GenerateResponse`:

```jsonc
{
  "format": "mermaid",
  "diagram_type": "class",
  "dsl": "classDiagram\n  …",
  "graph": {
    "title": "Order Management",
    "nodes": 4,
    "edges": 3,
    "classes": 3,
    "interfaces": 1,
    "contexts": ["Api", "Domain", "Infrastructure", "Payments"]
  },
  "files": [],
  "warnings": []
}
```

## Layout

```
src/
├── App.vue                     # shell: header, status bar, view switching
├── main.js                     # boots Vue + imports Carbon styles
├── api/
│   ├── client.js               # fetch wrapper, base URL, mock switch
│   ├── mock.js                 # canned responses for VITE_USE_MOCK
│   ├── plantuml.js             # PlantUML source → server URL encoding
│   └── types.js                # JSDoc typedefs for the API contract
├── components/
│   ├── AboutPanel.vue
│   ├── AppHeader.vue           # Carbon UI Shell header
│   ├── DslViewer.vue           # source view with copy + download
│   ├── HistoryPanel.vue        # recent generations table
│   ├── InlineNotification.vue  # reusable Carbon notification
│   ├── InputPanel.vue          # input modes, options, generate action
│   ├── MermaidDiagram.vue      # renders Mermaid source
│   ├── PlantUmlDiagram.vue     # renders PlantUML source
│   ├── ResultPanel.vue         # diagram / source / details tabs
│   └── StatusBar.vue           # /health status + theme switcher
├── composables/
│   └── useTheme.js             # Carbon theme zones (white / g10 / g90 / g100)
└── styles/
    └── app.css                 # layout on top of Carbon tokens
```
