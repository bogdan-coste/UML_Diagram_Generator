"""LLM access layer.

``LLMClient`` is imported from ``src.llm.llm_client`` directly (rather than
re-exported here) so that importing this package does not require ``openai`` to
be installed.
"""

from src.llm.factory import build_llm_client, try_build_llm_client

__all__ = ["build_llm_client", "try_build_llm_client"]
