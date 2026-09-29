"""FastAPI backend for the ArchiGen AI frontend.

Run with::

    uvicorn src.api.main:app --reload --port 8000

Endpoints are mounted at the root (`/health`, `/generate`, `/history`); the Vite
dev server proxies `/api/*` here and strips the prefix, so the frontend needs no
extra configuration.
"""
