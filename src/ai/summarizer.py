"""
Use the local SLM to generate one-sentence responsibility labels
for complex classes.
"""

import networkx as nx

from src.ai.ollama_client import query_ollama

# Minimum number of methods before we bother the SLM for a summary.
MIN_METHODS_FOR_SUMMARY = 5


def summarize_class(node_name: str, methods: list[str]) -> str:
    """
    Ask the SLM for a one-sentence responsibility summary of a class.
    Returns an empty string on failure.
    """
    if len(methods) < MIN_METHODS_FOR_SUMMARY:
        return ""

    prompt = (
        f"Class: {node_name}\n"
        f"Methods: {', '.join(methods)}\n\n"
        "Summarize this class's responsibility in ONE short sentence."
    )

    result = query_ollama(prompt)
    return result if result else ""


def enrich_graph_with_summaries(graph: nx.DiGraph) -> None:
    """
    For each node in the graph with enough methods, query the SLM for a
    responsibility summary and store it as a 'responsibility' attribute.
    """
    for node_id in graph.nodes():
        node = graph.nodes[node_id]
        methods = node.get("methods", [])
        method_names = [m.get("name", "") for m in methods]
        summary = summarize_class(str(node_id), method_names)
        if summary:
            node["responsibility"] = summary
