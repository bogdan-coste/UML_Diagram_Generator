"""
Classify and extract relationships (edges) from parsed metadata.

Relationship types:
    - Inheritance   (class → superclass)
    - Implementation (class → interface)
    - Composition   (class → class via constructor param ownership)
    - Dependency    (class → class via import/usage without ownership)
"""

from typing import Any, Dict, List, Set

import networkx as nx


# ---------------------------------------------------------------------------
# Name resolution: find the fully-qualified node id for a simple class name
# ---------------------------------------------------------------------------
def _resolve_name(candidates: List[str], simple_name: str) -> str:
    """
    Given a list of known fully-qualified node IDs and a simple class name,
    return the matching node ID. Prioritises exact suffix match
    (e.g. 'UserRepository' matches 'com.example.repo.UserRepository').
    """
    # Direct match
    if simple_name in candidates:
        return simple_name

    # Suffix match: ends with ".SimpleName"
    suffix = f".{simple_name}"
    matches = [c for c in candidates if c.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    # Ambiguous — pick the first
    if matches:
        return matches[0]

    # Fuzzy: the simple_name appears as a token in the candidate
    for c in candidates:
        if simple_name in c:
            return c

    return simple_name  # return as-is, won't resolve to an existing node


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------
def extract_edges(metadata: Dict[str, Any], graph: nx.DiGraph) -> None:
    """
    Analyse *metadata* and add classified edges to *graph* in-place.

    Edge types stored as 'edge_type' attribute on each edge.
    """
    # Build a lookup from simple class name → fully-qualified node id
    all_node_ids: Set[str] = set(graph.nodes())

    # 1. Build a set of domain-level names from nodes (simple names)
    domain_simple: Set[str] = {graph.nodes[n].get("name", n) for n in graph.nodes()}

    # 2. Process each class in metadata
    for cls in metadata.get("classes", []):
        src_id = cls.get("package", "") + "." + cls["name"] if cls.get("package") else cls["name"]
        if src_id not in graph:
            continue

        # --- Inheritance ---
        superclass = cls.get("superclass", "")
        if superclass:
            dst = _resolve_name(list(all_node_ids), superclass)
            if dst in graph and dst != src_id:
                graph.add_edge(src_id, dst, edge_type="inheritance")

        # --- Implementation ---
        for iface_name in cls.get("interfaces", []):
            dst = _resolve_name(list(all_node_ids), iface_name)
            if dst in graph and dst != src_id:
                graph.add_edge(src_id, dst, edge_type="implementation")

        # --- Composition (via constructor params and fields) ---
        comp_targets: Set[str] = set()

        # Constructor parameters → composition
        for param_type in cls.get("constructor_params", []):
            resolved = _resolve_name(list(all_node_ids), param_type)
            if resolved in graph and resolved != src_id:
                comp_targets.add(resolved)

        # Fields that are domain types → composition
        for field_type in cls.get("fields", []):
            if field_type in domain_simple:
                resolved = _resolve_name(list(all_node_ids), field_type)
                if resolved in graph and resolved != src_id:
                    comp_targets.add(resolved)

        for target in comp_targets:
            if not graph.has_edge(src_id, target):
                graph.add_edge(src_id, target, edge_type="composition")

        # --- Dependency (import-based; only if no stronger relationship exists) ---
        for imp in cls.get("imports", []):
            # Extract the last component of the import as candidate simple name
            simple = imp.split(".")[-1].strip()
            if simple in domain_simple:
                resolved = _resolve_name(list(all_node_ids), simple)
                if resolved in graph and resolved != src_id:
                    if not graph.has_edge(src_id, resolved):
                        graph.add_edge(src_id, resolved, edge_type="dependency")

    # 3. Process interfaces — they can also have dependencies via method params
    for iface in metadata.get("interfaces", []):
        src_id = iface.get("package", "") + "." + iface["name"] if iface.get("package") else iface["name"]
        if src_id not in graph:
            continue

        for imp in iface.get("imports", []):
            simple = imp.split(".")[-1].strip()
            if simple in domain_simple:
                resolved = _resolve_name(list(all_node_ids), simple)
                if resolved in graph and resolved != src_id:
                    if not graph.has_edge(src_id, resolved):
                        graph.add_edge(src_id, resolved, edge_type="dependency")
