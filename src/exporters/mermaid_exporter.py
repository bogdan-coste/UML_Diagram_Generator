"""
Export an enriched NetworkX graph to Mermaid diagram syntax.

Supported Mermaid diagram types:
  - classDiagram (structural UML — default)
  - graph TD (flowchart-style dependencies)
  - C4Context (C4 architecture via Mermaid's C4 extension — if available)
"""
from typing import Optional

import networkx as nx

# Edge-type → Mermaid classDiagram relationship decorators
MERMAID_RELATION_MAP = {
    "inheritance":   " --|> ",
    "implementation": " ..|> ",
    "composition":   " *-- ",
    "dependency":    " ..> ",
}


def _sanitise(name: str) -> str:
    """Replace characters that break Mermaid identifiers."""
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")


def to_mermaid_class_diagram(graph: nx.DiGraph) -> str:
    """Generate a Mermaid ``classDiagram`` from the enriched graph.

    Each node becomes a class; edges become UML-style relations.
    Contexts (packages) are rendered as Mermaid namespaces.
    """
    lines = ["classDiagram"]

    # Collect unique contexts for namespace wrapping
    contexts: dict[str, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        contexts.setdefault(ctx, []).append(node_id)

    for ctx_name, node_ids in sorted(contexts.items()):
        safe_ctx = _sanitise(ctx_name)
        lines.append(f"  namespace {safe_ctx} {{")

        for nid in sorted(node_ids):
            data = graph.nodes[nid]
            node_type = data.get("type", "class")
            cls_name = _sanitise(str(data.get("name", nid)))

            if node_type == "interface":
                lines.append(f"    class {cls_name} {{")
                lines.append(f"      <<interface>>")
                if data.get("responsibility"):
                    lines.append(f"      +{data['responsibility']}")
                for m in data.get("methods", []):
                    mname = m.get("name", "?")
                    ret = m.get("return_type", "void")
                    params = ", ".join(m.get("params", []))
                    lines.append(f"      +{mname}({params}) {ret}")
                lines.append(f"    }}")
            else:
                lines.append(f"    class {cls_name} {{")
                if data.get("responsibility"):
                    lines.append(f"      +{data['responsibility']}")
                for m in data.get("methods", []):
                    mname = m.get("name", "?")
                    ret = m.get("return_type", "void")
                    params = ", ".join(m.get("params", []))
                    lines.append(f"      +{mname}({params}) {ret}")
                lines.append(f"    }}")

        lines.append(f"  }}")

    # Relationships
    for src, dst, edata in graph.edges(data=True):
        edge_type = edata.get("edge_type", "dependency")
        arrow = MERMAID_RELATION_MAP.get(edge_type, " --> ")
        src_safe = _sanitise(str(graph.nodes[src].get("name", src)))
        dst_safe = _sanitise(str(graph.nodes[dst].get("name", dst)))
        lines.append(f"  {src_safe}{arrow}{dst_safe} : {edge_type}")

    return "\n".join(lines)


def to_mermaid_flowchart(graph: nx.DiGraph, direction: str = "TD") -> str:
    """Generate a Mermaid ``graph`` (flowchart) from the enriched graph.

    Each node becomes a box; edges are labeled arrows.
    """
    lines = [f"graph {direction}"]

    for node_id, data in graph.nodes(data=True):
        safe = _sanitise(str(data.get("name", node_id)))
        ctx = data.get("context", "")
        label = f"{safe}<br/><i>{ctx}</i>" if ctx else safe

        if data.get("type") == "interface":
            lines.append(f"  {safe}[«interface»<br/>{label}]")
        else:
            lines.append(f"  {safe}[{label}]")

    for src, dst, edata in graph.edges(data=True):
        edge_type = edata.get("edge_type", "dependency")
        src_safe = _sanitise(str(graph.nodes[src].get("name", src)))
        dst_safe = _sanitise(str(graph.nodes[dst].get("name", dst)))
        lines.append(f"  {src_safe} -- {edge_type} --> {dst_safe}")

    return "\n".join(lines)


def to_mermaid(graph: nx.DiGraph, style: str = "class") -> str:
    """Unified Mermaid export entry point.

    Args:
        graph: Enriched NetworkX DiGraph.
        style: One of 'class' (default), 'flowchart'.
    """
    if style == "flowchart":
        return to_mermaid_flowchart(graph)
    return to_mermaid_class_diagram(graph)
