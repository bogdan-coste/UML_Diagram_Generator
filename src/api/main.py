"""FastAPI application for ArchiGen AI.

Endpoints are exposed at the root. In development the Vite server proxies
``/api/*`` here and strips the prefix (see ``frontend/vite.config.js``), so the
frontend's default ``VITE_API_BASE_URL`` works with no configuration.

Run with::

    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.config import ENABLE_RAG
from src.schemas.models import LLMParameters

from .pipeline import (
    RAG_NOT_WIRED_WARNING,
    GraphBuild,
    PipelineError,
    build_from_code,
    build_from_folder,
    build_from_text,
    enrich,
    render,
    summarise,
)
from .schemas import GenerateRequest, GenerateResponse, HealthResponse, HistoryEntry
from .store import HistoryStore

VERSION = "0.2.0"

# Default allow-list: the Vite dev server. Override with a comma-separated
# API_CORS_ORIGINS when the frontend is served from somewhere else.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _cuda_available() -> bool:
    """Report CUDA availability without making torch a hard dependency.

    torch is only installed for the fine-tuning workflow, so the API must run
    without it.
    """
    try:
        import torch
    except ImportError:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - a broken driver must not fail /health
        return False


def _llm_configured() -> bool:
    """Whether an LLM endpoint is configured.

    A configuration check rather than a live probe: /health is called on every
    page load and must not block on a network round-trip.
    """
    params = LLMParameters()
    if params.llm_api_key:
        return True
    # A self-hosted endpoint (vLLM, llama.cpp, anything OpenAI-compatible with a
    # stub key) may not require a key, so a non-default base URL counts too.
    return params.llm_base_url.rstrip("/") != _OPENAI_DEFAULT_BASE_URL


def _build(payload: GenerateRequest) -> GraphBuild:
    if payload.mode == "folder":
        return build_from_folder(payload.content)
    if payload.mode == "code":
        return build_from_code(payload.content)
    return build_from_text(payload.content, is_story=payload.mode == "story")


def create_app() -> FastAPI:
    """Application factory, so tests can build an app without the module-level one."""
    app = FastAPI(
        title="ArchiGen AI",
        version=VERSION,
        description=(
            "Generate software architecture diagrams from source code or a "
            "natural-language description."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv("API_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    history = HistoryStore(maxlen=int(os.getenv("HISTORY_LIMIT", "50")))

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Service status. Always answered, even when nothing else works."""
        params = LLMParameters()
        llm_configured = _llm_configured()
        return HealthResponse(
            # The static pipeline needs no model, so a missing LLM degrades the
            # service rather than erroring.
            status="ok" if llm_configured else "degraded",
            model=params.llm_model,
            llm=llm_configured,
            rag=ENABLE_RAG,
            cuda=_cuda_available(),
            version=VERSION,
        )

    @app.post("/generate", response_model=GenerateResponse)
    def generate(payload: GenerateRequest) -> GenerateResponse:
        """Build a graph from the request and render it to the requested format."""
        try:
            build = _build(payload)
        except PipelineError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        warnings = list(build.warnings)

        if payload.use_ai:
            enrich(build.graph, warnings)
        if payload.use_rag:
            warnings.append(RAG_NOT_WIRED_WARNING)

        dsl, effective_type = render(
            build.graph, payload.format, payload.diagram_type, warnings
        )

        response = GenerateResponse(
            format=payload.format,
            diagram_type=effective_type,
            dsl=dsl,
            graph=summarise(build.graph),
            files=build.files,
            warnings=warnings,
        )

        history.add(
            HistoryEntry(
                id=uuid.uuid4().hex[:12],
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                mode=payload.mode,
                diagram_type=response.diagram_type,
                format=response.format,
                title=response.graph.title,
                nodes=response.graph.nodes,
                edges=response.graph.edges,
                result=response,
            )
        )
        return response

    @app.get("/history", response_model=list[HistoryEntry])
    def list_history(limit: int = Query(default=10, ge=1, le=200)) -> list[HistoryEntry]:
        """Most recent generations, newest first."""
        return history.recent(limit)

    return app


app = create_app()
