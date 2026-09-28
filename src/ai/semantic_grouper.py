"""
Use the local SLM to suggest architectural-layer / bounded-context names
for clusters of connected classes.
"""

import networkx as nx

from src.ai.ollama_client import query_ollama


def suggest_context_name(class_names: list[str]) -> str:
    """
    Ask the SLM to name the architectural context of a group of related classes.
    Falls back to "Default Package" if the SLM is unavailable.
    """
    if not class_names:
        return "Default Package"

    prompt = (
        "Given these connected classes, suggest a concise architectural "
        "layer or bounded context name (e.g., 'Security Context', "
        "'User Domain', 'Persistence Layer'). Return ONLY the name, "
        "no explanation.\n\n"
        f"Classes: {', '.join(class_names)}"
    )

    result = query_ollama(prompt)
    return result if result else "Default Package"


def enrich_graph_with_contexts(graph: nx.DiGraph) -> None:
    """
    For each weakly-connected component in *graph*, call the SLM to
    assign a context name. The name is stored as a 'context' attribute
    on every node in that component.
    """
    for component in nx.weakly_connected_components(graph):
        subgraph = graph.subgraph(component)
        class_names = [str(n) for n in subgraph.nodes()]

        context = suggest_context_name(class_names)
        for node in subgraph.nodes():
            graph.nodes[node]["context"] = context
