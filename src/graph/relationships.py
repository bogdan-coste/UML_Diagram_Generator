from typing import Any

import networkx as nx


def _resolve_name(candidates: list[str], simple_name: str) -> str:
    if simple_name in candidates:
        return simple_name

    suffix = f".{simple_name}"
    matches = [c for c in candidates if c.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]

    if matches:
        return matches[0]

    for c in candidates:
        if simple_name in c:
            return c

    return simple_name

def extract_edges(metadata: dict[str, Any], graph: nx.DiGraph) -> None:
    all_node_ids: list[str] = sorted(graph.nodes())

    domain_simple: set[str] = {graph.nodes[n].get("name", n) for n in graph.nodes()}

    for cls in metadata.get("classes", []):
        src_id = cls.get("package", "") + "." + cls["name"] if cls.get("package") else cls["name"]
        if src_id not in graph:
            continue

        superclass = cls.get("superclass", "")
        if superclass:
            dst = _resolve_name(all_node_ids, superclass)
            if dst in graph and dst != src_id:
                graph.add_edge(src_id, dst, edge_type="inheritance")

        for iface_name in cls.get("interfaces", []):
            dst = _resolve_name(all_node_ids, iface_name)
            if dst in graph and dst != src_id:
                graph.add_edge(src_id, dst, edge_type="implementation")

        comp_targets: set[str] = set()

        for param_type in cls.get("constructor_params", []):
            resolved = _resolve_name(all_node_ids, param_type)
            if resolved in graph and resolved != src_id:
                comp_targets.add(resolved)

        for field_type in cls.get("fields", []):
            if field_type in domain_simple:
                resolved = _resolve_name(all_node_ids, field_type)
                if resolved in graph and resolved != src_id:
                    comp_targets.add(resolved)

        for target in sorted(comp_targets):
            if not graph.has_edge(src_id, target):
                graph.add_edge(src_id, target, edge_type="composition")

        for imp in cls.get("imports", []):
            simple = imp.split(".")[-1].strip()
            if simple in domain_simple:
                resolved = _resolve_name(all_node_ids, simple)
                if resolved in graph and resolved != src_id and not graph.has_edge(src_id, resolved):
                        graph.add_edge(src_id, resolved, edge_type="dependency")

    for iface in metadata.get("interfaces", []):
        src_id = iface.get("package", "") + "." + iface["name"] if iface.get("package") else iface["name"]
        if src_id not in graph:
            continue

        for imp in iface.get("imports", []):
            simple = imp.split(".")[-1].strip()
            if simple in domain_simple:
                resolved = _resolve_name(all_node_ids, simple)
                if resolved in graph and resolved != src_id and not graph.has_edge(src_id, resolved):
                        graph.add_edge(src_id, resolved, edge_type="dependency")
