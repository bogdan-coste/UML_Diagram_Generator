/**
 * Canned responses used when `VITE_USE_MOCK=true`.
 *
 * This lets the UI run without the FastAPI backend so the layout and
 * interactions can be reviewed locally. It is development-only data — it
 * never talks to an LLM and never parses any source code.
 */

/** @type {import('./types').HealthResponse} */
export const MOCK_HEALTH = {
  status: 'ok',
  model: 'gpt-4o-mini',
  llm: true,
  rag: false,
  cuda: false,
  finetuned: false,
  finetuned_adapter: null,
  finetuned_model: null,
  version: '0.1.0-mock',
}

const MERMAID = `classDiagram
    class OrderController {
        +placeOrder(cartId) Order
        +cancelOrder(orderId) void
    }
    class OrderService {
        +createOrder(cart) Order
        +cancelOrder(orderId) void
    }
    class OrderRepository {
        +save(order) Order
        +findById(id) Order
    }
    class PaymentGateway {
        <<interface>>
        +charge(amount) Receipt
    }
    OrderController --> OrderService : uses
    OrderService --> OrderRepository : uses
    OrderService --> PaymentGateway : uses
`

const PLANTUML = `@startuml
title Order Management
skinparam classAttributeIconSize 0

interface PaymentGateway {
  +charge(amount) : Receipt
}

class OrderController {
  +placeOrder(cartId) : Order
  +cancelOrder(orderId) : void
}

class OrderService {
  +createOrder(cart) : Order
  +cancelOrder(orderId) : void
}

class OrderRepository {
  +save(order) : Order
  +findById(id) : Order
}

OrderController ..> OrderService : uses
OrderService ..> OrderRepository : uses
OrderService ..> PaymentGateway : uses
@enduml
`

const STRUCTURIZR = `workspace "Order Management" "Auto-generated from source code analysis." {
    model {
        api = softwareSystem "Api" {
            orderController = container "OrderController"
        }
        domain = softwareSystem "Domain" {
            orderService = container "OrderService"
        }
        infrastructure = softwareSystem "Infrastructure" {
            orderRepository = container "OrderRepository"
        }
        payments = softwareSystem "Payments" {
            paymentGateway = container "PaymentGateway"
        }

        orderController -> orderService "uses"
        orderService -> orderRepository "uses"
        orderService -> paymentGateway "uses"
    }

    views {
        container api "Containers" {
            include *
            autolayout lr
        }
    }
}
`

const GRAPHVIZ = `digraph Architecture {
  label="Order Management";
  labelloc=t;
  node [shape=record, fontname="Helvetica"];

  "OrderController" [label="{OrderController|+ placeOrder(cartId)\\l+ cancelOrder(orderId)\\l}"];
  "OrderService" [label="{OrderService|+ createOrder(cart)\\l+ cancelOrder(orderId)\\l}"];
  "OrderRepository" [label="{OrderRepository|+ save(order)\\l+ findById(id)\\l}"];
  "PaymentGateway" [shape=record, style=dashed, label="{\\<\\<interface\\>\\>\\nPaymentGateway|+ charge(amount)\\l}"];

  "OrderController" -> "OrderService" [label="uses"];
  "OrderService" -> "OrderRepository" [label="uses"];
  "OrderService" -> "PaymentGateway" [label="uses"];
}
`

const DSL_BY_FORMAT = {
  mermaid: MERMAID,
  plantuml: PLANTUML,
  structurizr: STRUCTURIZR,
  graphviz: GRAPHVIZ,
}

const SAMPLE_FILES = [
  'demo_project/src/main/java/com/example/web/OrderController.java',
  'demo_project/src/main/java/com/example/service/OrderService.java',
  'demo_project/src/main/java/com/example/repo/OrderRepository.java',
  'demo_project/src/main/java/com/example/payments/PaymentGateway.java',
]

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Build a fake `GenerateResponse` for the given request.
 *
 * @param {import('./types').GenerateRequest} payload
 * @returns {Promise<import('./types').GenerateResponse>}
 */
export async function mockGenerate(payload) {
  // Simulate the latency of the real pipeline so loading states are visible.
  await wait(700)

  const format = DSL_BY_FORMAT[payload?.format] ? payload.format : 'plantuml'
  const warnings = payload?.use_rag
    ? ['RAG retrieval was requested but the vector store is not indexed in mock mode.']
    : []

  const result = {
    format,
    diagram_type: payload?.diagram_type || 'class',
    dsl: DSL_BY_FORMAT[format],
    graph: {
      title: 'Order Management',
      nodes: 4,
      edges: 3,
      classes: 3,
      interfaces: 1,
      contexts: ['Api', 'Domain', 'Infrastructure', 'Payments'],
    },
    files: payload?.mode === 'folder' || payload?.mode === 'code' ? SAMPLE_FILES : [],
    warnings,
  }

  return result
}

/** @type {import('./types').HistoryEntry[]} */
export const MOCK_HISTORY = [
  {
    id: 'mock-3',
    timestamp: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
    mode: 'folder',
    diagram_type: 'class',
    format: 'mermaid',
    title: 'Order Management',
    nodes: 4,
    edges: 3,
  },
  {
    id: 'mock-2',
    timestamp: new Date(Date.now() - 1000 * 60 * 52).toISOString(),
    mode: 'code',
    diagram_type: 'component',
    format: 'plantuml',
    title: 'Payments Service',
    nodes: 7,
    edges: 9,
  },
  {
    id: 'mock-1',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    mode: 'text',
    diagram_type: 'flowchart',
    format: 'graphviz',
    title: 'Checkout Flow',
    nodes: 5,
    edges: 6,
  },
]
