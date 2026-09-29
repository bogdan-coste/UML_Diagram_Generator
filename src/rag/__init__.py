"""
RAG (Retrieval-Augmented Generation) Knowledge Base for diagram generation.

Stores canonical AST representations of diagrams and source code in a
ChromaDB vector database, enabling semantic retrieval of similar
architectural patterns to improve diagram generation accuracy.

Architecture:
  1. Canonical AST — a JSON-serializable representation of a diagram's
     structural elements (entities, relationships, contexts).
  2. Embedding — sentence-transformers model converts AST text to vector.
  3. ChromaDB — persistent vector store with metadata filtering.
  4. Retrieval — given a query (text or graph), returns top-k similar
     diagram ASTs for few-shot prompting or pattern suggestion.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from src.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, ENABLE_RAG


# ---------------------------------------------------------------------------
# Canonical AST: a language-agnostic representation of a diagram
# ---------------------------------------------------------------------------
CANONICAL_AST_VERSION = "1.0"

def graph_to_canonical_ast(graph: nx.DiGraph) -> Dict[str, Any]:
    """Convert an enriched NetworkX graph into a canonical AST (JSON dict).

    The canonical AST captures:
      - entities (nodes with type, context, methods, responsibility)
      - relationships (edges with type)
      - metadata (graph title, source, timestamp)

    This is the common interchange format for the RAG knowledge base,
    dataset generation, and SLM few-shot prompts.
    """
    entities = []
    for node_id, data in sorted(graph.nodes(data=True), key=lambda n: str(n[0])):
        entities.append({
            "id": node_id,
            "name": data.get("name", node_id),
            "type": data.get("type", "class"),
            "context": data.get("context", "Default Package"),
            "responsibility": data.get("responsibility", ""),
            "methods": [
                {
                    "name": m.get("name", "?"),
                    "return_type": m.get("return_type", ""),
                    "params": m.get("params", []),
                }
                for m in data.get("methods", [])
            ],
            "superclass": data.get("superclass", ""),
            "interfaces": data.get("interfaces", []),
        })

    relationships = []
    for src, dst, edata in sorted(
        graph.edges(data=True), key=lambda e: (str(e[0]), str(e[1]))
    ):
        relationships.append({
            "from": src,
            "to": dst,
            "type": edata.get("edge_type", "dependency"),
            "description": edata.get("description", ""),
        })

    return {
        "canonical_ast_version": CANONICAL_AST_VERSION,
        "title": graph.graph.get("title", "Untitled"),
        "source": graph.graph.get("source", "unknown"),
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "entities": entities,
        "relationships": relationships,
    }


def canonical_ast_to_text(ast: Dict[str, Any]) -> str:
    """Convert a canonical AST into a compact text representation for embedding.

    Format: "TITLE: [title]. Entities: Name1 (class, Context1): does X
             [methods: run(id): Result, stop(): void]; ...
             Relationships: A -> B (dependency)"
    """
    lines = [f"TITLE: {ast.get('title', 'Untitled')}."]

    ent_lines = []
    for ent in ast.get("entities", []):
        # Full signatures, not just names: `to_plantuml` renders each method's
        # return type and parameters, so emitting only the name would ask the
        # model to produce information it was never given.
        methods = ", ".join(
            f"{m['name']}({', '.join(m.get('params', []))}): {m.get('return_type', 'void')}"
            for m in ent.get("methods", [])
        )
        parts = [f"{ent['name']} ({ent['type']}, {ent['context']})"]
        if ent.get("responsibility"):
            parts.append(f": {ent['responsibility']}")
        if methods:
            parts.append(f" [methods: {methods}]")
        ent_lines.append("".join(parts))
    lines.append("Entities: " + "; ".join(ent_lines))

    rel_lines = []
    for rel in ast.get("relationships", []):
        rel_lines.append(f"{rel['from']} -> {rel['to']} ({rel['type']})")
    if rel_lines:
        lines.append("Relationships: " + "; ".join(rel_lines))

    return ". ".join(lines)


# ---------------------------------------------------------------------------
# ChromaDB-backed vector store
# ---------------------------------------------------------------------------
_chroma_client = None
_embedding_fn = None


def _get_chroma():
    """Lazy-init ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            persist_dir = os.path.abspath(CHROMA_PERSIST_DIR)
            os.makedirs(persist_dir, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=persist_dir)
        except ImportError:
            raise ImportError(
                "chromadb is not installed. Install with: pip install chromadb"
            )
    return _chroma_client


def _get_embedding_fn():
    """Lazy-init the sentence-transformers embedding function."""
    global _embedding_fn
    if _embedding_fn is None:
        try:
            import chromadb.utils.embedding_functions as embedding_functions
            _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
    return _embedding_fn


_COLLECTION_NAME = "diagram_asts"


def _get_collection():
    """Get or create the ChromaDB collection for diagram ASTs."""
    client = _get_chroma()
    ef = _get_embedding_fn()
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "Canonical diagram ASTs for RAG"},
    )


def add_to_knowledge_base(
    graph: nx.DiGraph,
    diagram_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Store a graph's canonical AST in the RAG knowledge base.

    Args:
        graph: Enriched NetworkX DiGraph.
        diagram_id: Unique ID (auto-generated if None).
        metadata: Additional metadata tags (e.g., language, project).

    Returns:
        The diagram_id used for storage.
    """
    if not ENABLE_RAG:
        return diagram_id or "rag_disabled"

    ast = graph_to_canonical_ast(graph)
    text = canonical_ast_to_text(ast)
    doc_id = diagram_id or f"diag_{hash(text) & 0x7FFFFFFF:08x}"

    collection = _get_collection()
    meta = {
        "title": ast["title"],
        "entity_count": ast["entity_count"],
        "relationship_count": ast["relationship_count"],
        "canonical_ast": json.dumps(ast, ensure_ascii=False),
    }
    if metadata:
        meta.update({k: str(v) for k, v in metadata.items()})

    # Upsert: overwrite if same ID
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[meta],
    )
    return doc_id


def query_knowledge_base(
    query: str,
    n_results: int = 5,
    filter_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve similar diagram ASTs from the RAG knowledge base.

    Args:
        query: Natural language query describing desired architecture.
        n_results: Number of top results to return.
        filter_meta: Optional ChromaDB metadata filter dict.

    Returns:
        List of result dicts with keys: id, distance, metadata, ast (parsed JSON).
    """
    if not ENABLE_RAG:
        return []

    collection = _get_collection()
    where = filter_meta or None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        dist = results["distances"][0][i] if results["distances"] else -1.0

        ast = None
        if meta and "canonical_ast" in meta:
            try:
                ast = json.loads(meta["canonical_ast"])
            except json.JSONDecodeError:
                pass

        output.append({
            "id": doc_id,
            "distance": dist,
            "document": results["documents"][0][i] if results["documents"] else "",
            "metadata": meta,
            "ast": ast,
        })

    return output


def graph_to_rag_query(graph: nx.DiGraph) -> str:
    """Convert a partial/in-progress graph into a natural language query
    suitable for the RAG knowledge base.

    This is used during diagram generation to find similar completed
    diagrams that can guide the SLM.
    """
    ast = graph_to_canonical_ast(graph)
    return canonical_ast_to_text(ast)


def clear_knowledge_base() -> int:
    """Delete all entries from the RAG knowledge base. Returns count deleted."""
    if not ENABLE_RAG:
        return 0
    try:
        client = _get_chroma()
        client.delete_collection(_COLLECTION_NAME)
        global _chroma_client
        _chroma_client = None  # force re-init
        return 1  # collection deleted
    except Exception:
        return 0


def is_rag_available() -> bool:
    """Check whether ChromaDB and sentence-transformers are importable."""
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Knowledge base seeding with canonical patterns
# ---------------------------------------------------------------------------
def seed_knowledge_base() -> int:
    """Seed the knowledge base with common architectural patterns.

    Returns the number of patterns seeded.
    """
    if not ENABLE_RAG:
        return 0

    patterns = []

    # Pattern 1: Layered Architecture (Controller → Service → Repository)
    g1 = nx.DiGraph()
    g1.graph["title"] = "Layered Architecture"
    g1.graph["source"] = "seed_pattern"
    g1.add_node("Controller", name="Controller", type="class", context="API Layer",
                 responsibility="Handle HTTP requests", methods=[
                     {"name": "handleRequest", "return_type": "Response", "params": ["Request"]}
                 ], fields=[], constructor_params=[], imports=[], package="API Layer",
                 superclass="", interfaces=[])
    g1.add_node("Service", name="Service", type="class", context="Business Layer",
                 responsibility="Business logic", methods=[
                     {"name": "execute", "return_type": "Result", "params": ["Input"]}
                 ], fields=[], constructor_params=[], imports=[], package="Business Layer",
                 superclass="", interfaces=[])
    g1.add_node("Repository", name="Repository", type="interface", context="Persistence Layer",
                 responsibility="Data access", methods=[
                     {"name": "find", "return_type": "Entity", "params": ["ID"]}
                 ], fields=[], constructor_params=[], imports=[], package="Persistence Layer",
                 superclass="", interfaces=[])
    g1.add_edge("Controller", "Service", edge_type="dependency")
    g1.add_edge("Service", "Repository", edge_type="dependency")
    patterns.append(g1)

    # Pattern 2: Microservices with API Gateway
    g2 = nx.DiGraph()
    g2.graph["title"] = "Microservices with API Gateway"
    g2.graph["source"] = "seed_pattern"
    g2.add_node("APIGateway", name="APIGateway", type="class", context="Gateway Layer",
                 responsibility="Route requests to microservices", methods=[
                     {"name": "route", "return_type": "void", "params": ["Request"]}
                 ], fields=[], constructor_params=[], imports=[], package="Gateway Layer",
                 superclass="", interfaces=[])
    g2.add_node("UserService", name="UserService", type="class", context="User Domain",
                 responsibility="Manage user accounts", methods=[
                     {"name": "getUser", "return_type": "User", "params": ["ID"]}
                 ], fields=[], constructor_params=[], imports=[], package="User Domain",
                 superclass="", interfaces=[])
    g2.add_node("OrderService", name="OrderService", type="class", context="Order Domain",
                 responsibility="Process orders", methods=[
                     {"name": "placeOrder", "return_type": "Order", "params": ["Cart"]}
                 ], fields=[], constructor_params=[], imports=[], package="Order Domain",
                 superclass="", interfaces=[])
    g2.add_edge("APIGateway", "UserService", edge_type="dependency")
    g2.add_edge("APIGateway", "OrderService", edge_type="dependency")
    patterns.append(g2)

    # Pattern 3: Observer / Event-Driven
    g3 = nx.DiGraph()
    g3.graph["title"] = "Event-Driven Architecture"
    g3.graph["source"] = "seed_pattern"
    g3.add_node("EventPublisher", name="EventPublisher", type="class", context="Event Layer",
                 responsibility="Publish domain events", methods=[
                     {"name": "publish", "return_type": "void", "params": ["Event"]}
                 ], fields=[], constructor_params=[], imports=[], package="Event Layer",
                 superclass="", interfaces=[])
    g3.add_node("EventListener", name="EventListener", type="interface", context="Event Layer",
                 responsibility="Handle domain events", methods=[
                     {"name": "onEvent", "return_type": "void", "params": ["Event"]}
                 ], fields=[], constructor_params=[], imports=[], package="Event Layer",
                 superclass="", interfaces=[])
    g3.add_node("EventHandler", name="EventHandler", type="class", context="Business Layer",
                 responsibility="Process business events", methods=[
                     {"name": "handle", "return_type": "void", "params": ["Event"]}
                 ], fields=[], constructor_params=[], imports=[], package="Business Layer",
                 superclass="", interfaces=["EventListener"])
    g3.add_edge("EventPublisher", "EventListener", edge_type="dependency")
    g3.add_edge("EventHandler", "EventListener", edge_type="implementation")
    patterns.append(g3)

    # Pattern 4: MVC
    g4 = nx.DiGraph()
    g4.graph["title"] = "Model-View-Controller"
    g4.graph["source"] = "seed_pattern"
    g4.add_node("Controller", name="Controller", type="class", context="Web Layer",
                 responsibility="Handle user input", methods=[
                     {"name": "handleInput", "return_type": "void", "params": ["Input"]}
                 ], fields=[], constructor_params=[], imports=[], package="Web Layer",
                 superclass="", interfaces=[])
    g4.add_node("Model", name="Model", type="class", context="Domain Layer",
                 responsibility="Business data and rules", methods=[
                     {"name": "getState", "return_type": "State", "params": []}
                 ], fields=[], constructor_params=[], imports=[], package="Domain Layer",
                 superclass="", interfaces=[])
    g4.add_node("View", name="View", type="class", context="Presentation Layer",
                 responsibility="Render UI", methods=[
                     {"name": "render", "return_type": "void", "params": ["Model"]}
                 ], fields=[], constructor_params=[], imports=[], package="Presentation Layer",
                 superclass="", interfaces=[])
    g4.add_edge("Controller", "Model", edge_type="dependency")
    g4.add_edge("View", "Model", edge_type="dependency")
    patterns.append(g4)

    # Pattern 5: Hexagonal (Ports & Adapters)
    g5 = nx.DiGraph()
    g5.graph["title"] = "Hexagonal Architecture (Ports & Adapters)"
    g5.graph["source"] = "seed_pattern"
    g5.add_node("ApplicationCore", name="ApplicationCore", type="class", context="Core Domain",
                 responsibility="Core business logic", methods=[
                     {"name": "process", "return_type": "Result", "params": ["Command"]}
                 ], fields=[], constructor_params=[], imports=[], package="Core Domain",
                 superclass="", interfaces=[])
    g5.add_node("InputPort", name="InputPort", type="interface", context="Ports",
                 responsibility="Primary port for driving the application", methods=[
                     {"name": "handle", "return_type": "void", "params": ["Request"]}
                 ], fields=[], constructor_params=[], imports=[], package="Ports",
                 superclass="", interfaces=[])
    g5.add_node("OutputPort", name="OutputPort", type="interface", context="Ports",
                 responsibility="Secondary port for driven operations", methods=[
                     {"name": "save", "return_type": "void", "params": ["Entity"]}
                 ], fields=[], constructor_params=[], imports=[], package="Ports",
                 superclass="", interfaces=[])
    g5.add_node("RESTAdapter", name="RESTAdapter", type="class", context="Adapters",
                 responsibility="HTTP input adapter", methods=[
                     {"name": "handleRequest", "return_type": "Response", "params": ["Request"]}
                 ], fields=[], constructor_params=[], imports=[], package="Adapters",
                 superclass="", interfaces=["InputPort"])
    g5.add_node("DBAdapter", name="DBAdapter", type="class", context="Adapters",
                 responsibility="Database output adapter", methods=[
                     {"name": "save", "return_type": "void", "params": ["Entity"]}
                 ], fields=[], constructor_params=[], imports=[], package="Adapters",
                 superclass="", interfaces=["OutputPort"])
    g5.add_edge("ApplicationCore", "InputPort", edge_type="dependency")
    g5.add_edge("ApplicationCore", "OutputPort", edge_type="dependency")
    g5.add_edge("RESTAdapter", "InputPort", edge_type="implementation")
    g5.add_edge("RESTAdapter", "ApplicationCore", edge_type="dependency")
    g5.add_edge("DBAdapter", "OutputPort", edge_type="implementation")
    patterns.append(g5)

    seeded = 0
    for i, g in enumerate(patterns):
        try:
            add_to_knowledge_base(g, diagram_id=f"seed_pattern_{i:03d}")
            seeded += 1
        except Exception:
            pass

    return seeded
