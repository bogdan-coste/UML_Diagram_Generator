"""Request and response models for the ArchiGen REST API.

These mirror the JSDoc typedefs in ``frontend/src/api/types.js``. The frontend is
plain JavaScript, so nothing enforces the match at build time — keep the two
files in sync by hand when either side changes.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# How the user described the system.
InputMode = Literal["text", "story", "code", "folder"]

# Requested diagram kind. Not every kind is renderable by every exporter; see
# `pipeline.SUPPORTED_DIAGRAM_TYPES`.
DiagramType = Literal[
    "class", "flowchart", "sequence", "er", "component", "deployment", "state"
]

# Output DSL dialect.
OutputFormat = Literal["mermaid", "plantuml", "structurizr", "graphviz"]

HealthStatus = Literal["ok", "degraded", "error"]


class GenerateRequest(BaseModel):
    """Payload for ``POST /generate``."""

    mode: InputMode
    content: str = Field(
        min_length=1,
        description=(
            "Free text, user story, source code, or a path to a local directory, "
            "depending on `mode`."
        ),
    )
    diagram_type: DiagramType = "class"
    format: OutputFormat = "plantuml"
    use_ai: bool = Field(
        default=False,
        description="Run LLM enrichment (context naming, responsibilities).",
    )
    use_rag: bool = Field(
        default=False,
        description="Request RAG retrieval (see the warning in the response).",
    )


class GraphSummary(BaseModel):
    """Statistics about the graph that produced the diagram."""

    title: str | None = None
    nodes: int
    edges: int
    classes: int | None = None
    interfaces: int | None = None
    contexts: list[str] | None = None


class GenerateResponse(BaseModel):
    """Payload returned by ``POST /generate``."""

    format: OutputFormat
    diagram_type: DiagramType
    dsl: str
    graph: GraphSummary
    files: list[str] = Field(
        default_factory=list,
        description="Source files parsed, for `folder` and `code` modes.",
    )
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Payload returned by ``GET /health``."""

    status: HealthStatus
    model: str
    llm: bool = Field(
        description=(
            "Whether an LLM endpoint is configured. This is a configuration "
            "check, not a live reachability probe — /health must stay fast."
        )
    )
    rag: bool
    cuda: bool
    version: str | None = None


class HistoryEntry(BaseModel):
    """One row of ``GET /history``."""

    id: str
    timestamp: str = Field(description="ISO-8601 timestamp.")
    mode: InputMode
    diagram_type: DiagramType
    format: OutputFormat
    title: str | None = None
    nodes: int | None = None
    edges: int | None = None
    result: GenerateResponse | None = Field(
        default=None,
        description="Full response, so the UI can restore a past diagram.",
    )
