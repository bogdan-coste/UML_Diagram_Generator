from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm.llm_client import LLMClient


def build_llm_client(system_prompt: str = "") -> LLMClient:
    from src.llm.llm_client import LLMClient as _LLMClient
    from src.schemas.models import LLMParameters

    return _LLMClient(LLMParameters(), system_prompt=system_prompt)


def try_build_llm_client(system_prompt: str = "") -> LLMClient | None:
    try:
        return build_llm_client(system_prompt)
    except Exception:
        return None
