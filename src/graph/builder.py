from typing import Any

import networkx as nx

# Matches the fallback used by the exporters and by `graph_to_canonical_ast`.
DEFAULT_CONTEXT = "Default Package"


def _make_node_id(cls: dict[str, Any]) -> str:
    """Build a unique node identifier from a class/interface metadata dict."""
    name = cls.get("name", "Anonymous")
    pkg = cls.get("package", "")
    if pkg:
        return f"{pkg}.{name}"
    return name


def build_graph(metadata: dict[str, Any]) -> nx.DiGraph:
    graph = nx.DiGraph()

    # `context` is what the exporters and the canonical-AST converter read to
    # group types. The parser produces `package`, so it is copied here under the
    # name the rest of the pipeline expects -- without it, every node collapses
    # into a single "Default Package" box and the description handed to the model
    # loses the package each type belongs to.
    def _attrs(entry: dict[str, Any], kind: str) -> dict[str, Any]:
        attrs = dict(entry)
        attrs["type"] = kind
        attrs["context"] = entry.get("package") or DEFAULT_CONTEXT
        return attrs

    for cls in metadata.get("classes", []):
        graph.add_node(_make_node_id(cls), **_attrs(cls, "class"))

    for iface in metadata.get("interfaces", []):
        graph.add_node(_make_node_id(iface), **_attrs(iface, "interface"))

    return graph
