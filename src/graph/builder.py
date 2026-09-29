from typing import Any

import networkx as nx


def _make_node_id(cls: dict[str, Any]) -> str:
    """Build a unique node identifier from a class/interface metadata dict."""
    name = cls.get("name", "Anonymous")
    pkg = cls.get("package", "")
    if pkg:
        return f"{pkg}.{name}"
    return name


def build_graph(metadata: dict[str, Any]) -> nx.DiGraph:
    graph = nx.DiGraph()

    for cls in metadata.get("classes", []):
        node_id = _make_node_id(cls)
        attrs = dict(cls)
        attrs["type"] = "class"
        graph.add_node(node_id, **attrs)

    for iface in metadata.get("interfaces", []):
        node_id = _make_node_id(iface)
        attrs = dict(iface)
        attrs["type"] = "interface"
        graph.add_node(node_id, **attrs)

    return graph
