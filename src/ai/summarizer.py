from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from src.llm.factory import build_llm_client, try_build_llm_client

if TYPE_CHECKING:
    from src.llm.llm_client import LLMClient

MIN_METHODS_FOR_SUMMARY = 5

def summarize_class(
    node_name: str, methods: list[str], llm: LLMClient | None = None
) -> str:

    if len(methods) < MIN_METHODS_FOR_SUMMARY:
        return ""

    prompt = (
        f"Class: {node_name}\n"
        f"Methods: {', '.join(methods)}\n\n"
        "Summarize this class's responsibility in ONE short sentence."
    )

    try:
        result = (llm or build_llm_client()).ask_llm(prompt)
    except Exception:
        return ""

    return (result or "").strip()


def enrich_graph_with_summaries(
    graph: nx.DiGraph, llm: LLMClient | None = None
) -> None:

    client = llm if llm is not None else try_build_llm_client()

    for node_id in graph.nodes():
        node = graph.nodes[node_id]
        methods = node.get("methods", [])
        method_names = [m.get("name", "") for m in methods]
        summary = summarize_class(str(node_id), method_names, llm=client)
        if summary:
            node["responsibility"] = summary
