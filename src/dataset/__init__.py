"""
Dataset module for SLM training and validation.

Generates:
  1. Training datasets — SLM fine-tuning pairs (text description → canonical AST)
  2. Validation datasets — for evaluating diagram generation accuracy
  3. Diagram DSL parsers — Mermaid, PlantUML → canonical AST conversion
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from src.rag import graph_to_canonical_ast, canonical_ast_to_text


# ==========================================================================
# Dataset generation
# ==========================================================================
def generate_training_dataset(
    graphs: List[nx.DiGraph],
    output_path: str,
    format: str = "jsonl",
) -> int:
    """Convert a list of graphs into an SLM training dataset.

    Each record: { "instruction": "...", "input": "text description",
                   "output": "JSON canonical AST" }

    Args:
        graphs: List of enriched NetworkX graphs.
        output_path: Path for the output file.
        format: 'jsonl' (default) or 'json'.

    Returns:
        Number of records written.
    """
    records = []
    for g in graphs:
        ast = graph_to_canonical_ast(g)
        text = canonical_ast_to_text(ast)
        records.append({
            "instruction": (
                "Given the following software architecture description, "
                "generate a structured diagram representation as a JSON "
                "object with entities and relationships."
            ),
            "input": text,
            "output": json.dumps(ast, ensure_ascii=False),
        })

    if format == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    return len(records)


def generate_validation_dataset(
    graphs: List[nx.DiGraph],
    output_path: str,
) -> int:
    """Generate a validation dataset for evaluating diagram accuracy.

    Format: { "description": "...", "expected_ast": {...}, "metrics": {} }
    """
    records = []
    for g in graphs:
        ast = graph_to_canonical_ast(g)
        text = canonical_ast_to_text(ast)
        records.append({
            "description": text,
            "expected_ast": ast,
            "metrics": {
                "entity_count": ast["entity_count"],
                "relationship_count": ast["relationship_count"],
                "contexts": list(set(
                    e["context"] for e in ast["entities"]
                )),
            },
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return len(records)


# ==========================================================================
# Diagram DSL parsers: Mermaid / PlantUML → canonical AST
# ==========================================================================
import re


def parse_mermaid_class_diagram(source: str) -> Optional[nx.DiGraph]:
    """Parse a Mermaid classDiagram string into an enriched NetworkX graph.

    Handles:
      - ``class ClassName { ... }``
      - ``namespace PackageName { ... }``
      - ``<<interface>>`` stereotype
      - ``ClassA <|-- ClassB`` relationships (inheritance)
      - ``ClassA <|.. ClassB`` (implementation)
      - ``ClassA *-- ClassB`` (composition)
      - ``ClassA --> ClassB``, ``ClassA ..> ClassB`` (dependency)

    Returns None if parsing fails.
    """
    graph = nx.DiGraph()
    graph.graph["source"] = "mermaid_import"

    current_namespace = "Default Package"
    lines = source.split("\n")

    # --- Pass 1: Find namespaces and classes ---
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Namespace
        ns_match = re.match(r"namespace\s+(\w+)\s*\{", line)
        if ns_match:
            current_namespace = ns_match.group(1)
            i += 1
            continue

        # End namespace
        if line == "}":
            if current_namespace != "Default Package":
                current_namespace = "Default Package"
            i += 1
            continue

        # Class definition start
        cls_match = re.match(r"class\s+(\w+)\s*\{", line)
        if cls_match:
            cls_name = cls_match.group(1)
            methods: List[Dict[str, Any]] = []
            is_interface = False
            responsibility = ""

            # Read class body
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("}"):
                inner = lines[i].strip()

                # Interface stereotype
                if "<<interface>>" in inner:
                    is_interface = True
                    i += 1
                    continue

                # Method / field
                method_match = re.match(r"[+\-~#]\s*(\w+)\(([^)]*)\)\s*:?\s*(\w+)?", inner)
                if method_match:
                    methods.append({
                        "name": method_match.group(1),
                        "return_type": method_match.group(3) or "",
                        "params": [p.strip() for p in method_match.group(2).split(",") if p.strip()],
                    })
                    i += 1
                    continue

                # Responsibility (as a comment-like field)
                if inner.startswith("+"):
                    responsibility = inner.lstrip("+").strip()
                    i += 1
                    continue

                i += 1

            node_type = "interface" if is_interface else "class"
            graph.add_node(cls_name, **{
                "name": cls_name,
                "type": node_type,
                "context": current_namespace,
                "responsibility": responsibility,
                "methods": methods,
                "fields": [],
                "constructor_params": [],
                "imports": [],
                "file_path": "",
                "package": current_namespace,
                "superclass": "",
                "interfaces": [],
            })

        i += 1

    # --- Pass 2: Relationships ---
    # Mermaid relationship patterns (longer arrows first)
    # The `rev` flag marks forms whose left-hand operand is the *subtype*.
    # `A <|-- B` means B extends A, so the graph edge runs B -> A; `A --|> B`
    # says the same thing with the operands the other way round.
    rel_patterns = [
        # "from" arrow "to" : label
        (r"(\w+)\s*<\|--\s*(\w+)\s*(?::\s*(.*))?", "inheritance", True),
        (r"(\w+)\s*<\|\.\.\s*(\w+)\s*(?::\s*(.*))?", "implementation", True),
        (r"(\w+)\s*\*--\s*(\w+)\s*(?::\s*(.*))?", "composition"),
        (r"(\w+)\s*\.\.>\s*(\w+)\s*(?::\s*(.*))?", "dependency"),
        (r"(\w+)\s*-->\s*(\w+)\s*(?::\s*(.*))?", "dependency"),
        # Same relationships, written with the arrowhead on the supertype.
        (r"(\w+)\s*--\|>\s*(\w+)\s*(?::\s*(.*))?", "inheritance"),
        (r"(\w+)\s*\.\.\|>\s*(\w+)\s*(?::\s*(.*))?", "implementation"),
        (r"(\w+)\s*--\*\s*(\w+)\s*(?::\s*(.*))?", "composition", True),
    ]

    for pattern, edge_type, *rev in rel_patterns:
        for match in re.finditer(pattern, source):
            a, b = match.group(1), match.group(2)
            label = (match.group(3) or "").strip()
            if rev and rev[0]:
                a, b = b, a  # swap
            if a in graph and b in graph:
                graph.add_edge(a, b, edge_type=edge_type, description=label)

    return graph if graph.number_of_nodes() > 0 else None


def _clause_edge(match: "re.Match[str]") -> tuple[str, str, str] | None:
    """(source, edge_type, target) from an optional inline `extends`/`implements` clause.

    Our own exporter never writes one, but a model copying the phrasing of a prose
    description attaches it to the declaration. PlantUML ignores it there, so the
    edge has to be read back out of the clause or the relationship is lost twice.
    """
    keyword = match.group(3)
    if not keyword:
        return None
    return (
        match.group(2),
        "inheritance" if keyword == "extends" else "implementation",
        match.group(4),
    )


def parse_plantuml(source: str) -> Optional[nx.DiGraph]:
    """Parse a PlantUML .puml class diagram into an enriched NetworkX graph.

    Handles:
      - ``package "Name" as P {``
      - ``class "Name" as C {`` / ``interface "Name" as I {``
      - ``abstract class ...``
      - ``A <|-- B`` (inheritance), ``A <|.. B`` (implementation),
        ``A *-- B`` (composition), ``A ..> B`` (dependency)

    Returns None if parsing fails.
    """
    graph = nx.DiGraph()
    graph.graph["source"] = "plantuml_import"

    current_package = "Default Package"
    current_class: Optional[str] = None
    is_interface = False
    is_abstract = False
    methods: List[Dict[str, Any]] = []
    fields: List[str] = []
    responsibility = ""
    package_map: Dict[str, str] = {}

    lines = source.split("\n")
    # Edges implied by an inline `extends`/`implements` clause; added last so both
    # endpoints are known regardless of declaration order.
    declared_edges: list[tuple[str, str, str]] = []

    for line in lines:
        stripped = line.strip()

        # Skip non-structural lines
        if stripped.startswith("@") or stripped.startswith("title") or stripped.startswith("skinparam"):
            continue

        # Package
        pkg_match = re.match(r'package\s+"([^"]+)"\s+as\s+(\w+)\s*\{', stripped)
        if pkg_match:
            current_package = pkg_match.group(1)
            package_map[pkg_match.group(2)] = current_package
            continue

        # End package (bare closing brace)
        if stripped == "}" and current_class is None:
            if current_package != "Default Package":
                current_package = "Default Package"
            continue

        # End class body
        if stripped == "}" and current_class is not None:
            graph.add_node(current_class, **{
                "name": current_class,
                "type": "interface" if is_interface else "class",
                "context": current_package,
                "responsibility": responsibility,
                "methods": methods,
                "fields": fields,
                "constructor_params": [],
                "imports": [],
                "file_path": "",
                "package": current_package,
                "superclass": "",
                "interfaces": [],
            })
            current_class = None
            is_interface = False
            is_abstract = False
            methods = []
            responsibility = ""
            continue

        # Interface / Class / Abstract class. A trailing `extends X` / `implements Y`
        # is tolerated: the stricter pattern dropped the entire class, taking every
        # relationship that referenced it along with it.
        iface_match = re.match(
            r'interface\s+"([^"]+)"\s+as\s+(\w+)(?:\s+(extends|implements)\s+(\w+))?\s*\{',
            stripped,
        )
        if iface_match:
            current_class = iface_match.group(2)
            is_interface = True
            is_abstract = False
            methods = []
            fields = []
            responsibility = ""
            clause = _clause_edge(iface_match)
            if clause:
                declared_edges.append(clause)
            continue

        cls_match = re.match(
            r'(?:abstract\s+)?class\s+"([^"]+)"\s+as\s+(\w+)(?:\s+(extends|implements)\s+(\w+))?\s*\{',
            stripped,
        )
        if cls_match:
            current_class = cls_match.group(2)
            is_interface = False
            is_abstract = cls_match.group(0).startswith("abstract")
            methods = []
            fields = []
            responsibility = ""
            clause = _clause_edge(cls_match)
            if clause:
                declared_edges.append(clause)
            continue

        # Inside class body
        if current_class:
            # Method: visibility, optional return type, name, params.
            # The return type must be optional: our own exporter always writes one,
            # but a model given prose without types emits `+checkout(cart)`, which
            # the older `([+\-~#])(\w+)\s+` pattern rejected -- silently dropping
            # every member of the class from the reconstructed graph.
            method_match = re.match(
                r"([+\-~#])\s*(?:(\S+)\s+)?([A-Za-z_]\w*)\(([^)]*)\)", stripped
            )
            if method_match:
                methods.append({
                    "name": method_match.group(3).strip(),
                    "return_type": (method_match.group(2) or "").strip(),
                    "params": [
                        p.strip()
                        for p in method_match.group(4).split(",")
                        if p.strip()
                    ],
                })
                continue

            # Responsibility (field marker)
            field_match = re.match(r"\{field\}\s*<<(.+)>>", stripped)
            if field_match:
                responsibility = field_match.group(1)
                continue

            # Field member, no parentheses: `+Repository repository`,
            # `+LineItem[] lineItems`. Our exporter never writes these, but a model
            # does -- and a field is what implies a composition relationship, so it
            # has to survive into the graph.
            member_match = re.match(r"([+\-~#])\s*(\S+)\s+([A-Za-z_]\w*)\s*$", stripped)
            if member_match:
                fields.append(member_match.group(2))
                continue

    # --- Relationships ---
    # The `rev` flag marks forms whose left-hand operand is the *subtype*.
    # `A <|-- B` means B extends A, so the graph edge runs B -> A; `A --|> B`
    # says the same thing with the operands the other way round. This mirrors
    # the operand order that the PlantUML/Mermaid exporters emit.
    rel_patterns = [
        (r"(\w+)\s*<\|--\s*(\w+)", "inheritance", True),
        (r"(\w+)\s*<\|\.\.\s*(\w+)", "implementation", True),
        (r"(\w+)\s*\*--\s*(\w+)", "composition"),
        (r"(\w+)\s*\.\.>\s*(\w+)", "dependency"),
        (r"(\w+)\s*-->\s*(\w+)", "dependency"),
        (r"(\w+)\s*--\|>\s*(\w+)", "inheritance"),
        (r"(\w+)\s*\.\.\|>\s*(\w+)", "implementation"),
    ]

    for pattern, edge_type, *rev in rel_patterns:
        for match in re.finditer(pattern, source):
            a, b = match.group(1), match.group(2)
            if rev and rev[0]:
                a, b = b, a
            if a in graph and b in graph:
                graph.add_edge(a, b, edge_type=edge_type, description="")

    for src, edge_type, dst in declared_edges:
        if src in graph and dst in graph and not graph.has_edge(src, dst):
            graph.add_edge(src, dst, edge_type=edge_type, description="")

    return graph if graph.number_of_nodes() > 0 else None


def parse_structurizr_dsl(source: str) -> Optional[nx.DiGraph]:
    """Parse a Structurizr DSL workspace into an enriched NetworkX graph.

    Handles: ``workspace { model { ... } }``, ``person = ...``,
             ``softwareSystem = ... { container = ... }``, ``->`` relations.

    Returns None if parsing fails.
    """
    graph = nx.DiGraph()
    graph.graph["source"] = "structurizr_import"

    current_system = "Default Package"
    lines = source.split("\n")

    for line in lines:
        stripped = line.strip()

        # Person / Software System
        person_match = re.match(
            r'(\w+)\s*=\s*person\s+"([^"]+)"\s+"([^"]*)"',
            stripped,
        )
        if person_match:
            node_id = person_match.group(1)
            name = person_match.group(2)
            desc = person_match.group(3)
            graph.add_node(node_id, name=name, type="class", context="Users",
                           responsibility=desc, methods=[], fields=[],
                           constructor_params=[], imports=[], file_path="",
                           package="Users", superclass="", interfaces=[])
            continue

        sys_match = re.match(
            r'(\w+)\s*=\s*softwareSystem\s+"([^"]+)"\s+"([^"]*)"',
            stripped,
        )
        if sys_match:
            current_system = sys_match.group(2)
            continue

        # Container
        cont_match = re.match(
            r'(\w+)\s*=\s*container\s+"([^"]+)"\s+"([^"]*)"\s+"([^"]*)"',
            stripped,
        )
        if cont_match:
            node_id = cont_match.group(1)
            name = cont_match.group(2)
            desc = cont_match.group(3)
            tech = cont_match.group(4)
            is_interface = "interface" in tech.lower()
            graph.add_node(node_id, name=name,
                           type="interface" if is_interface else "class",
                           context=current_system, responsibility=desc,
                           methods=[], fields=[], constructor_params=[],
                           imports=[], file_path="", package=current_system,
                           superclass="", interfaces=[])
            continue

        # Relationship: A -> B "description" "technology"
        rel_match = re.match(
            r'(\w+)\s*->\s*(\w+)\s+"([^"]*)"\s+"([^"]*)"',
            stripped,
        )
        if rel_match:
            src, dst = rel_match.group(1), rel_match.group(2)
            desc = rel_match.group(3)
            tech = rel_match.group(4)

            # Map technology tags to edge types
            edge_type = "dependency"
            if "inheritance" in tech.lower() or "extends" in tech.lower():
                edge_type = "inheritance"
            elif "implementation" in tech.lower() or "implements" in tech.lower():
                edge_type = "implementation"
            elif "composition" in tech.lower() or "owns" in tech.lower():
                edge_type = "composition"

            if src in graph and dst in graph:
                graph.add_edge(src, dst, edge_type=edge_type, description=desc)

    return graph if graph.number_of_nodes() > 0 else None


# ==========================================================================
# Graph distance / similarity metrics for dataset validation
# ==========================================================================
def graph_similarity(g1: nx.DiGraph, g2: nx.DiGraph) -> Dict[str, float]:
    """Compute structural similarity metrics between two graphs.

    Returns a dict with: node_jaccard, edge_jaccard, context_overlap,
    edge_type_accuracy.
    """
    nodes1 = set(g1.nodes())
    nodes2 = set(g2.nodes())
    edges1 = set((u, v) for u, v in g1.edges())
    edges2 = set((u, v) for u, v in g2.edges())

    node_jaccard = len(nodes1 & nodes2) / max(len(nodes1 | nodes2), 1)

    edge_types1 = {(u, v, g1.edges[u, v].get("edge_type", "")) for u, v in g1.edges()}
    edge_types2 = {(u, v, g2.edges[u, v].get("edge_type", "")) for u, v in g2.edges()}
    edge_jaccard = len(edge_types1 & edge_types2) / max(len(edge_types1 | edge_types2), 1)

    contexts1 = {g1.nodes[n].get("context", "") for n in nodes1}
    contexts2 = {g2.nodes[n].get("context", "") for n in nodes2}
    ctx_overlap = len(contexts1 & contexts2) / max(len(contexts1 | contexts2), 1)

    return {
        "node_jaccard": round(node_jaccard, 4),
        "edge_jaccard": round(edge_jaccard, 4),
        "context_overlap": round(ctx_overlap, 4),
        "edge_type_accuracy": round(edge_jaccard, 4),
    }


# ==========================================================================
# Batch dataset builder from scanned codebases
# ==========================================================================
def build_dataset_from_codebases(
    codebase_dirs: List[str],
    output_dir: str,
    pipeline_fn,
) -> Dict[str, Any]:
    """Run the full pipeline on multiple codebases and build a dataset.

    Args:
        codebase_dirs: List of source code directory paths.
        output_dir: Where to write train/val splits.
        pipeline_fn: Callable (dir) → nx.DiGraph that runs the full pipeline.

    Returns:
        Stats dict with counts.
    """
    os.makedirs(output_dir, exist_ok=True)

    graphs = []
    errors = []
    for d in codebase_dirs:
        try:
            g = pipeline_fn(d)
            if g and g.number_of_nodes() > 0:
                graphs.append(g)
            else:
                errors.append({"dir": d, "error": "Empty graph"})
        except Exception as e:
            errors.append({"dir": d, "error": str(e)})

    # Split 80/20
    split = int(len(graphs) * 0.8)
    train_graphs = graphs[:split]
    val_graphs = graphs[split:]

    n_train = generate_training_dataset(
        train_graphs,
        os.path.join(output_dir, "train.jsonl"),
    )
    n_val = generate_validation_dataset(
        val_graphs,
        os.path.join(output_dir, "val.json"),
    )

    return {
        "total_graphs": len(graphs),
        "train_records": n_train,
        "val_records": n_val,
        "errors": errors,
    }
