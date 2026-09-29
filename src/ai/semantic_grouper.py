from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from src.llm.factory import build_llm_client, try_build_llm_client

if TYPE_CHECKING:
    from src.llm.llm_client import LLMClient

FALLBACK_CONTEXT = "Default Package"


def suggest_context_name(
    class_names: list[str], llm: LLMClient | None = None
) -> str:
    """
    Ask the LLM to name the architectural context of a group of related classes.
    Falls back to "Default Package" if the LLM is unavailable.
    """
    if not class_names:
        return FALLBACK_CONTEXT

    prompt = (
        "Given these connected classes, suggest a concise architectural "
        "layer or bounded context name (e.g., 'Security Context', "
        "'User Domain', 'Persistence Layer'). Return ONLY the name, "
        "no explanation.\n\n"
        f"Classes: {', '.join(class_names)}"
    )

    try:
        result = (llm or build_llm_client()).ask_llm(prompt)
    except Exception:
        return FALLBACK_CONTEXT

    cleaned = (result or "").strip()
    return cleaned or FALLBACK_CONTEXT


def enrich_graph_with_contexts(
    graph: nx.DiGraph, llm: LLMClient | None = None
) -> None:
    client = llm if llm is not None else try_build_llm_client()

    for component in nx.weakly_connected_components(graph):
        subgraph = graph.subgraph(component)
        class_names = [str(n) for n in subgraph.nodes()]

        context = suggest_context_name(class_names, llm=client)
        for node in subgraph.nodes():
            graph.nodes[node]["context"] = context
