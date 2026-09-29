"""
Export an enriched NetworkX graph to PlantUML diagram syntax.

Generates class diagram (.puml) with packages, classes, interfaces,
and UML-typed relationships.
"""
from typing import Optional

import networkx as nx

# Edge-type → PlantUML relationship arrow
PUML_RELATION_MAP = {
    "inheritance":   " <|-- ",
    "implementation": " <|.. ",
    "composition":   " *-- ",
    "dependency":    " ..> ",
}


def _sanitise(name: str) -> str:
    return name.replace(".", "_").replace("-", "_").replace(" ", "_")


def to_plantuml(graph: nx.DiGraph, title: str = "Architecture Diagram") -> str:
    """Generate a PlantUML ``.puml`` class diagram from the enriched graph.

    Args:
        graph: Enriched NetworkX DiGraph.
        title: Diagram title rendered in the PUML header.
    """
    lines = [
        "@startuml",
        f"title {title}",
        "skinparam classAttributeIconSize 0",
        "skinparam packageStyle rectangle",
        "",
    ]

    # Collect contexts → namespace packages
    contexts: dict[str, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        contexts.setdefault(ctx, []).append(node_id)

    # Emit packages and classes/interfaces
    for ctx_name, node_ids in sorted(contexts.items()):
        safe_ctx = _sanitise(ctx_name)
        lines.append(f"package \"{ctx_name}\" as {safe_ctx} {{")

        for nid in sorted(node_ids):
            data = graph.nodes[nid]
            node_type = data.get("type", "class")
            cls_name = str(data.get("name", nid))

            if node_type == "interface":
                lines.append(f"  interface \"{cls_name}\" as {_sanitise(cls_name)} {{")
            else:
                # Abstract class detection heuristic (ABC or abstract method)
                is_abstract = any(
                    m.get("name", "").startswith("__")
                    for m in data.get("methods", [])
                )
                abstract_marker = "abstract " if is_abstract else ""
                lines.append(f"  {abstract_marker}class \"{cls_name}\" as {_sanitise(cls_name)} {{")

            # Responsibility note
            if data.get("responsibility"):
                lines.append(f"    {{field}} <<{data['responsibility']}>>")

            # Methods
            for m in data.get("methods", []):
                mname = m.get("name", "?")
                ret = m.get("return_type", "void")
                params = ", ".join(m.get("params", []))
                lines.append(f"    +{ret} {mname}({params})")

            lines.append("  }")

        lines.append("}")
        lines.append("")

    # Emit relationships
    # sorted so output is reproducible regardless of graph insertion order
    for src, dst, edata in sorted(
        graph.edges(data=True), key=lambda e: (str(e[0]), str(e[1]))
    ):
        edge_type = edata.get("edge_type", "dependency")
        arrow = PUML_RELATION_MAP.get(edge_type, " --> ")
        src_safe = _sanitise(str(graph.nodes[src].get("name", src)))
        dst_safe = _sanitise(str(graph.nodes[dst].get("name", dst)))
        lines.append(f"{src_safe}{arrow}{dst_safe} : {edge_type}")

    lines.append("@enduml")
    return "\n".join(lines)
