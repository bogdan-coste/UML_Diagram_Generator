import networkx as nx


def _sanitise(name: str) -> str:
    """Structurizr identifiers: alphanumeric + hyphens only."""
    safe = name.replace(".", "-").replace("_", "-").replace(" ", "-")
    # Remove any other non-alphanumeric except hyphen
    return "".join(c for c in safe if c.isalnum() or c == "-")


def _is_external(node_id: str) -> bool:
    """Heuristic: nodes whose FQN starts with known external packages."""
    ext_prefixes = ("java.", "javax.", "jakarta.", "org.", "com.sun.")
    return any(node_id.lower().startswith(p) for p in ext_prefixes)


def to_structurizr_dsl(
    graph: nx.DiGraph,
    workspace_name: str = "Architecture Workspace",
    description: str = "Auto-generated from source code analysis.",
) -> str:
    """Generate Structurizr DSL from the enriched graph.

    Maps contexts → Software Systems, classes → Containers,
    relationships → DSL relationships with tags.

    Args:
        graph: Enriched NetworkX DiGraph.
        workspace_name: Top-level workspace name.
        description: Workspace description.
    """
    lines = [
        f'workspace "{workspace_name}" "\\"{description}\\"" {{',
        "",
        "  model {",
    ]

    # Collect contexts → Systems
    contexts: dict[str, list[str]] = {}
    for node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        contexts.setdefault(ctx, []).append(node_id)

    # System IDs map for relationships
    system_ids: dict[str, str] = {}
    container_ids: dict[str, str] = {}

    for ctx_name, node_ids in sorted(contexts.items()):
        sys_id = _sanitise(ctx_name)
        system_ids[ctx_name] = sys_id

        # Check if any node looks like a person/user
        person_keywords = {"user", "person", "actor", "admin", "customer", "client"}
        is_person_system = any(
            kw in ctx_name.lower() for kw in person_keywords
        )

        if is_person_system:
            lines.append(f"    person = {sys_id} \"{ctx_name}\" \"A user / external actor\" {{")
        else:
            lines.append(f"    {sys_id} = softwareSystem \"{ctx_name}\" \"Bounded context for {ctx_name}\" {{")

        for nid in sorted(node_ids):
            data = graph.nodes[nid]
            node_type = data.get("type", "class")
            cls_name = data.get("name", nid)
            cont_id = _sanitise(str(cls_name))
            container_ids[nid] = cont_id

            tech = "Java" if data.get("file_path", "").endswith(".java") else "Python"
            if node_type == "interface":
                tech += " Interface"

            resp = data.get("responsibility", f"Container for {cls_name}")
            lines.append(f"      {cont_id} = container \"{cls_name}\" \"{resp}\" \"{tech}\" {{")
            # Tags based on edge types
            lines.append(f"        tags \"{node_type}\"")
            lines.append("      }")

        lines.append("    }")
        lines.append("")

    # Relationships
    for src, dst, edata in graph.edges(data=True):
        edge_type = edata.get("edge_type", "dependency")
        src_cont = container_ids.get(src)
        dst_cont = container_ids.get(dst)
        if not src_cont or not dst_cont:
            continue

        desc = f"{edge_type} relationship"
        tech_tag = edge_type
        lines.append(f"    {src_cont} -> {dst_cont} \"{desc}\" \"{tech_tag}\" {{")
        lines.append(f"      tags \"{edge_type}\"")
        lines.append("    }")

    lines.append("  }")
    lines.append("")
    lines.append("  views {")
    lines.append("    systemLandscape \"SystemLandscape\" \"System Landscape\" {")
    lines.append("      include *")
    lines.append("    }")
    lines.append("")

    # One container view per system/context
    for ctx_name in sorted(contexts.keys()):
        sys_id = system_ids[ctx_name]
        ctx_safe = _sanitise(ctx_name)
        lines.append(f"    container {sys_id} \"{ctx_name}ContainerView\" \"{ctx_name} Containers\" {{")
        lines.append(f"      include *")
        lines.append("    }")
        lines.append("")

    lines.append("  }")
    lines.append("  styles {")

    # Relationship-style tags
    lines.append('    element "class" {')
    lines.append("      shape Box")
    lines.append("      background #85BBF0")
    lines.append("    }")
    lines.append('    element "interface" {')
    lines.append("      shape Box")
    lines.append("      background #BBDEFB")
    lines.append("    }")

    lines.append('    relationship "inheritance" {')
    lines.append("      color #0000FF")
    lines.append("    }")
    lines.append('    relationship "composition" {')
    lines.append("      color #FF0000")
    lines.append("    }")
    lines.append('    relationship "implementation" {')
    lines.append("      color #00AA00")
    lines.append("      dashed true")
    lines.append("    }")
    lines.append('    relationship "dependency" {')
    lines.append("      color #888888")
    lines.append("      dashed true")
    lines.append("    }")

    lines.append("  }")
    lines.append("}")

    return "\n".join(lines)
