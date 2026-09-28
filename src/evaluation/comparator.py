"""
Systematic comparison of Static Analysis vs LLM-based diagram generation.

This module runs both approaches on the same codebase and produces
quantitative metrics comparing their outputs.
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

# ---------------------------------------------------------------------------
# Static analysis pipeline (deterministic, tree-sitter based)
# ---------------------------------------------------------------------------
def run_static_analysis_pipeline(repo_root: str) -> Tuple[nx.DiGraph, float]:
    """Run the tree-sitter static analysis pipeline and return (graph, elapsed_sec).

    This is the deterministic path: ingestion → parse → graph → edges.
    """
    t0 = time.time()

    from src.ingestion.file_traverser import collect_source_files
    from src.ingestion.parser import parse_all_files
    from src.graph.builder import build_graph
    from src.graph.relationships import extract_edges

    files = collect_source_files(repo_root)
    metadata = parse_all_files(files)
    graph = build_graph(metadata)
    extract_edges(metadata, graph)

    elapsed = time.time() - t0
    return graph, elapsed


# ---------------------------------------------------------------------------
# LLM-based pipeline (semantic interpretation, Ollama SLM)
# ---------------------------------------------------------------------------
def run_llm_pipeline(repo_root: str) -> Tuple[Optional[nx.DiGraph], float]:
    """Run the LLM-based pipeline: static analysis + AI enrichment.

    Returns (enriched_graph, elapsed_sec). Returns None if SLM is unavailable.
    """
    t0 = time.time()

    graph, static_elapsed = run_static_analysis_pipeline(repo_root)

    from src.ai.semantic_grouper import enrich_graph_with_contexts
    from src.ai.summarizer import enrich_graph_with_summaries

    try:
        enrich_graph_with_contexts(graph)
        enrich_graph_with_summaries(graph)
    except Exception:
        pass  # SLM unavailable; graph is still valid without enrichment

    elapsed = time.time() - t0
    return graph, elapsed


def run_text_to_diagram_pipeline(description: str) -> Tuple[Optional[nx.DiGraph], float]:
    """Run text-to-diagram via SLM and return (graph, elapsed_sec)."""
    t0 = time.time()

    from src.ai.text_to_diagram import text_to_graph
    graph = text_to_graph(description)

    elapsed = time.time() - t0
    return graph, elapsed


# ---------------------------------------------------------------------------
# Comparison metrics
# ---------------------------------------------------------------------------
def compare_entity_detection(
    static_graph: nx.DiGraph,
    llm_graph: Optional[nx.DiGraph],
) -> Dict[str, Any]:
    """Compare entity (node) detection between static and LLM approaches.

    Assumes static analysis is the ground truth for entity detection
    (tree-sitter is deterministic and accurate for structural parsing).

    Returns precision, recall, F1 of LLM against static analysis baseline.
    """
    static_nodes: set[str] = set(static_graph.nodes())
    static_names: set[str] = {
        static_graph.nodes[n].get("name", n) for n in static_nodes
    }

    if llm_graph is None:
        return {
            "llm_available": False,
            "static_entity_count": len(static_nodes),
            "note": "LLM was unavailable — only static analysis results.",
        }

    llm_nodes: set[str] = set(llm_graph.nodes())
    llm_names: set[str] = {
        llm_graph.nodes[n].get("name", n) for n in llm_nodes
    }

    # Match by simple name (LLM may not produce FQN)
    matched = static_names & llm_names
    precision = len(matched) / max(len(llm_names), 1)
    recall = len(matched) / max(len(static_names), 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.0001)

    return {
        "llm_available": True,
        "static_entity_count": len(static_nodes),
        "llm_entity_count": len(llm_nodes),
        "matched_entities": len(matched),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "extra_entities_llm": sorted(llm_names - static_names),
        "missing_entities_llm": sorted(static_names - llm_names),
    }


def compare_relationship_detection(
    static_graph: nx.DiGraph,
    llm_graph: Optional[nx.DiGraph],
) -> Dict[str, Any]:
    """Compare relationship (edge) detection accuracy.

    Edge matching considers (src_name, dst_name, edge_type) triples.
    """
    static_edges: set[Tuple[str, str, str]] = set()
    for u, v in static_graph.edges():
        utype = static_graph.edges[u, v].get("edge_type", "dependency")
        uname = static_graph.nodes[u].get("name", u)
        vname = static_graph.nodes[v].get("name", v)
        static_edges.add((uname, vname, utype))

    if llm_graph is None:
        return {
            "llm_available": False,
            "static_edge_count": len(static_edges),
            "note": "LLM was unavailable.",
        }

    llm_edges: set[Tuple[str, str, str]] = set()
    for u, v in llm_graph.edges():
        utype = llm_graph.edges[u, v].get("edge_type", "dependency")
        uname = llm_graph.nodes[u].get("name", u)
        vname = llm_graph.nodes[v].get("name", v)
        llm_edges.add((uname, vname, utype))

    # Match edges (name pair only, ignoring edge type)
    static_edge_pairs = {(s, d) for s, d, _ in static_edges}
    llm_edge_pairs = {(s, d) for s, d, _ in llm_edges}

    matched_pairs = static_edge_pairs & llm_edge_pairs

    # Edge type accuracy: of the matched pairs, how many have the correct type?
    type_correct = 0
    for s, d in matched_pairs:
        stype = next((t for sn, dn, t in static_edges if sn == s and dn == d), "")
        ltype = next((t for sn, dn, t in llm_edges if sn == s and dn == d), "")
        if stype == ltype:
            type_correct += 1

    edge_precision = len(matched_pairs) / max(len(llm_edge_pairs), 1)
    edge_recall = len(matched_pairs) / max(len(static_edge_pairs), 1)
    edge_f1 = 2 * edge_precision * edge_recall / max(edge_precision + edge_recall, 0.0001)
    type_accuracy = type_correct / max(len(matched_pairs), 1)

    return {
        "llm_available": True,
        "static_edge_count": len(static_edges),
        "llm_edge_count": len(llm_edges),
        "matched_edges": len(matched_pairs),
        "edge_precision": round(edge_precision, 4),
        "edge_recall": round(edge_recall, 4),
        "edge_f1": round(edge_f1, 4),
        "type_accuracy": round(type_accuracy, 4),
        "extra_edges_llm": sorted(
            (s, d, t) for s, d, t in llm_edges if (s, d) not in static_edge_pairs
        ),
        "missing_edges_llm": sorted(
            (s, d, t) for s, d, t in static_edges if (s, d) not in llm_edge_pairs
        ),
    }


def compare_context_quality(
    static_graph: nx.DiGraph,
    llm_graph: Optional[nx.DiGraph],
) -> Dict[str, Any]:
    """Evaluate context/package grouping quality.

    Static analysis uses package declarations (Java) or file paths (Python).
    LLM-based uses semantic grouping (SLM-suggested contexts).
    """
    static_contexts: Dict[str, str] = {}
    for n in static_graph.nodes():
        ctx = static_graph.nodes[n].get("package", "") or static_graph.nodes[n].get("context", "Default")
        static_contexts[n] = ctx

    if llm_graph is None:
        return {
            "llm_available": False,
            "static_context_count": len(set(static_contexts.values())),
            "note": "LLM unavailable.",
        }

    llm_contexts: Dict[str, str] = {}
    for n in llm_graph.nodes():
        ctx = llm_graph.nodes[n].get("context", "Default Package")
        llm_contexts[n] = ctx

    static_ctx_set = set(static_contexts.values())
    llm_ctx_set = set(llm_contexts.values())

    return {
        "llm_available": True,
        "static_context_count": len(static_ctx_set),
        "llm_context_count": len(llm_ctx_set),
        "static_contexts": sorted(static_ctx_set),
        "llm_contexts": sorted(llm_ctx_set),
        "context_overlap": len(static_ctx_set & llm_ctx_set) / max(len(static_ctx_set | llm_ctx_set), 1),
    }


# ---------------------------------------------------------------------------
# Full evaluation report
# ---------------------------------------------------------------------------
def run_full_comparison(
    repo_root: str,
    text_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a full comparison between static analysis and LLM approaches.

    Args:
        repo_root: Path to source code directory.
        text_description: Optional natural language description for
                          additional text-to-diagram comparison.

    Returns:
        Comprehensive evaluation report dict.
    """
    report: Dict[str, Any] = {
        "repo": repo_root,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # 1. Static analysis
    print("[eval] Running static analysis pipeline...")
    static_graph, static_time = run_static_analysis_pipeline(repo_root)
    report["static_analysis"] = {
        "elapsed_sec": round(static_time, 3),
        "node_count": static_graph.number_of_nodes(),
        "edge_count": static_graph.number_of_edges(),
    }

    # 2. LLM-enriched
    print("[eval] Running LLM-enriched pipeline...")
    llm_graph, llm_time = run_llm_pipeline(repo_root)
    report["llm_enriched"] = {
        "elapsed_sec": round(llm_time, 3),
        "node_count": llm_graph.number_of_nodes() if llm_graph else 0,
        "edge_count": llm_graph.number_of_edges() if llm_graph else 0,
        "available": llm_graph is not None,
    }

    # 3. Entity comparison
    print("[eval] Comparing entity detection...")
    report["entity_comparison"] = compare_entity_detection(static_graph, llm_graph)

    # 4. Relationship comparison
    print("[eval] Comparing relationship detection...")
    report["relationship_comparison"] = compare_relationship_detection(static_graph, llm_graph)

    # 5. Context comparison
    print("[eval] Comparing context quality...")
    report["context_comparison"] = compare_context_quality(static_graph, llm_graph)

    # 6. Text-to-diagram comparison (if description provided)
    if text_description:
        print("[eval] Running text-to-diagram pipeline...")
        text_graph, text_time = run_text_to_diagram_pipeline(text_description)
        report["text_to_diagram"] = {
            "elapsed_sec": round(text_time, 3),
            "node_count": text_graph.number_of_nodes() if text_graph else 0,
            "edge_count": text_graph.number_of_edges() if text_graph else 0,
            "available": text_graph is not None,
        }
        if text_graph:
            report["text_vs_static_entity"] = compare_entity_detection(static_graph, text_graph)
            report["text_vs_static_relationship"] = compare_relationship_detection(static_graph, text_graph)

    # 7. Summary
    report["summary"] = generate_comparison_summary(report)

    return report


def generate_comparison_summary(report: Dict[str, Any]) -> str:
    """Generate a human-readable summary of the comparison report."""
    lines = []
    lines.append("=" * 60)
    lines.append("  STATIC ANALYSIS vs LLM COMPARISON REPORT")
    lines.append("=" * 60)
    lines.append(f"  Repository: {report.get('repo', 'N/A')}")
    lines.append("")

    sa = report.get("static_analysis", {})
    llm = report.get("llm_enriched", {})
    lines.append(f"  Static Analysis: {sa.get('node_count', 0)} nodes, "
                 f"{sa.get('edge_count', 0)} edges "
                 f"({sa.get('elapsed_sec', 0):.2f}s)")
    lines.append(f"  LLM Enriched: {llm.get('node_count', 0)} nodes, "
                 f"{llm.get('edge_count', 0)} edges "
                 f"({llm.get('elapsed_sec', 0):.2f}s)")
    lines.append("")

    ec = report.get("entity_comparison", {})
    if ec.get("llm_available"):
        lines.append("  Entity Detection (LLM vs Static):")
        lines.append(f"    Precision: {ec.get('precision', 0):.2%}")
        lines.append(f"    Recall:    {ec.get('recall', 0):.2%}")
        lines.append(f"    F1 Score:  {ec.get('f1_score', 0):.2%}")

    rc = report.get("relationship_comparison", {})
    if rc.get("llm_available"):
        lines.append("  Relationship Detection (LLM vs Static):")
        lines.append(f"    Edge Precision: {rc.get('edge_precision', 0):.2%}")
        lines.append(f"    Edge Recall:    {rc.get('edge_recall', 0):.2%}")
        lines.append(f"    Edge F1:        {rc.get('edge_f1', 0):.2%}")
        lines.append(f"    Type Accuracy:  {rc.get('type_accuracy', 0):.2%}")

    cc = report.get("context_comparison", {})
    if cc.get("llm_available"):
        lines.append("  Context Grouping:")
        lines.append(f"    Static contexts: {cc.get('static_context_count', 0)}")
        lines.append(f"    LLM contexts:    {cc.get('llm_context_count', 0)}")
        lines.append(f"    Overlap:         {cc.get('context_overlap', 0):.2%}")

    td = report.get("text_to_diagram", {})
    if td:
        lines.append("")
        lines.append("  Text-to-Diagram (from description):")
        lines.append(f"    Generated: {td.get('node_count', 0)} nodes, "
                     f"{td.get('edge_count', 0)} edges "
                     f"({td.get('elapsed_sec', 0):.2f}s)")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_comparison_report(report: Dict[str, Any], output_path: str) -> str:
    """Save the comparison report as JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return output_path
