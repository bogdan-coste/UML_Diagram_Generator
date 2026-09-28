"""
Export an enriched NetworkX graph to Graphviz DOT format.

Produces .dot files that can be rendered with the ``graphviz`` library
or the ``dot`` command-line tool.
"""
from typing import Optional

import networkx as nx

# Edge-type → Graphviz arrowhead mappings
DOT_EDGE_STYLE = {
    "inheritance":   {"arrowhead": "empty", "style": "solid"},
    "implementation": {"arrowhead": "empty", "style": "dashed"},
    "composition":   {"arrowhead": "diamond", "style": "solid"},
    "dependency":    {"arrowhead": "open", "style": "dashed"},
}


def _sanitise(name: str) -> str:
    return name.replace(".", "_").replace("-", "_").replace(" ", "_").replace('"', '\\"')


def to_graphviz_dot(graph: nx.DiGraph, title: str = "Architecture Diagram") -> str:
    """Generate a Graphviz ``.dot`` digraph from the enriched graph.

    Args:
        graph: Enriched NetworkX DiGraph.
        title: Graph label.
    """
    lines = [
        "digraph Architecture {",
        f'  label="{title}";',
        "  labelloc=t;",
        "  fontsize=20;",
        "  rankdir=TB;",
        "  node [shape=record, fontname=\"Helvetica\", style=filled, fillcolor=white];",
        "  edge [fontname=\"Helvetica\", fontsize=10];",
        "",
    ]

    # Cluster each context as a subgraph
    contexts: dict[str, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        contexts.setdefault(ctx, []).append(node_id)

    cluster_idx = 0
    for ctx_name, node_ids in sorted(contexts.items()):
        safe_ctx = _sanitise(ctx_name)
        lines.append(f"  subgraph cluster_{cluster_idx} {{")
        lines.append(f'    label="{ctx_name}";')
        lines.append("    style=filled;")
        lines.append("    fillcolor=\"#f0f0f0\";")
        cluster_idx += 1

        for nid in sorted(node_ids):
            data = graph.nodes[nid]
            node_type = data.get("type", "class")
            cls_name = _sanitise(str(data.get("name", nid)))

            # Build an HTML-like label with methods
            label_parts = [f"<b>{cls_name}</b>"]
            if data.get("responsibility"):
                label_parts.append(f"<i>{data['responsibility']}</i>")
            label_parts.append("")
            for m in data.get("methods", []):
                mname = m.get("name", "?")
                ret = m.get("return_type", "")
                ret_str = f": {ret}" if ret else ""
                label_parts.append(f"+ {mname}(){ret_str}")

            lbl = "\\n".join(label_parts)
            color = "lightblue" if node_type == "interface" else "lightyellow"
            lines.append(
                f'    {_sanitise(nid)} [label="{lbl}", fillcolor="{color}", '
                f'style=filled];'
            )

        lines.append("  }")

    # Edges
    for src, dst, edata in graph.edges(data=True):
        edge_type = edata.get("edge_type", "dependency")
        style = DOT_EDGE_STYLE.get(edge_type, DOT_EDGE_STYLE["dependency"])
        src_safe = _sanitise(str(graph.nodes[src].get("name", src)))
        dst_safe = _sanitise(str(graph.nodes[dst].get("name", dst)))
        lines.append(
            f'  {src_safe} -> {dst_safe} '
            f'[label="{edge_type}", arrowhead="{style["arrowhead"]}", '
            f'style="{style["style"]}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def render_to_png(dot_source: str, output_path: str) -> str:
    """Render a DOT source string to a PNG file using the graphviz library.

    Args:
        dot_source: DOT format string.
        output_path: Path for the output PNG (``.png`` extension added if missing).

    Returns:
        Path to the rendered PNG file.
    """
    import graphviz as gv
    if not output_path.endswith(".png"):
        output_path += ".png"
    dot = gv.Source(dot_source)
    dot.render(output_path.replace(".png", ""), format="png", cleanup=True)
    return output_path
