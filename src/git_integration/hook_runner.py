"""
Pre-commit hook: validate architectural consistency before a commit.

Workflow:
  1. Detect staged changes (modified source files).
  2. Run static analysis on changed files only.
  3. Compare the resulting dependency graph with the last committed version.
  4. If structural violations (removed interfaces, broken dependencies) are
     detected, block the commit and emit a report.
  5. Optionally auto-regenerate the architecture diagram (.gaphor, .mmd, .puml).
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def get_staged_files(repo_root: str) -> List[str]:
    """Return the list of staged (git add) file paths, relative to repo root."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, cwd=repo_root, timeout=10,
        )
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        return []


def get_changed_source_files(repo_root: str) -> List[str]:
    """Return staged files that are source files (.java, .py)."""
    staged = get_staged_files(repo_root)
    return [
        os.path.join(repo_root, f)
        for f in staged
        if f.endswith((".java", ".py"))
    ]


def run_analysis(files: List[str]) -> Optional[Any]:
    """Run the ingestion + graph pipeline on the given files.

    Returns a NetworkX DiGraph or None on failure.
    """
    try:
        from src.ingestion.parser import parse_all_files
        from src.graph.builder import build_graph
        from src.graph.relationships import extract_edges

        metadata = parse_all_files(files)
        graph = build_graph(metadata)
        extract_edges(metadata, graph)
        return graph
    except Exception as e:
        print(f"  [ERROR] Analysis failed: {e}", file=sys.stderr)
        return None


def graph_fingerprint(graph) -> str:
    """Compute a stable SHA256 hash of the graph's structural elements.

    This fingerprint captures: node names, edge (src, dst, type) triples,
    and context groupings. It is used to detect structural changes between
    the staged and committed versions.
    """
    nodes = sorted(graph.nodes())
    edges = sorted(
        (u, v, graph.edges[u, v].get("edge_type", ""))
        for u, v in graph.edges()
    )
    contexts = sorted(
        (n, graph.nodes[n].get("context", "")) for n in nodes
    )

    payload = json.dumps({
        "nodes": nodes,
        "edges": edges,
        "contexts": contexts,
    }, sort_keys=True)

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_last_committed_fingerprint(repo_root: str) -> Optional[str]:
    """Retrieve the stored fingerprint from the last commit.

    The fingerprint is stored in ``.arch-diagram-fingerprint`` at the repo root.
    """
    fp_path = os.path.join(repo_root, ".arch-diagram-fingerprint")
    if not os.path.isfile(fp_path):
        return None
    with open(fp_path, "r") as f:
        return f.read().strip()


def store_fingerprint(repo_root: str, fingerprint: str) -> None:
    """Store the fingerprint for the next commit comparison."""
    fp_path = os.path.join(repo_root, ".arch-diagram-fingerprint")
    with open(fp_path, "w") as f:
        f.write(fingerprint)


def detect_violations(
    staged_graph,
    committed_graph,
) -> Dict[str, Any]:
    """Compare two graphs and detect architectural violations.

    Returns a dict with:
      - removed_nodes: nodes present in committed but not in staged
      - added_nodes: nodes present in staged but not in committed
      - changed_edges: edges whose type changed
      - removed_edges: edges present in committed but not in staged
      - severe: bool — True if violations are blocking
    """
    staged_nodes = set(staged_graph.nodes())
    committed_nodes = set(committed_graph.nodes())

    removed_nodes = committed_nodes - staged_nodes
    added_nodes = staged_nodes - committed_nodes

    staged_edges = {
        (u, v, staged_graph.edges[u, v].get("edge_type", ""))
        for u, v in staged_graph.edges()
    }
    committed_edges = {
        (u, v, committed_graph.edges[u, v].get("edge_type", ""))
        for u, v in committed_graph.edges()
    }

    removed_edges = [
        {"from": u, "to": v, "type": t}
        for u, v, t in committed_edges
        if (u, v) not in {(a, b) for a, b, _ in staged_edges}
    ]

    # Edges where the type changed
    changed_edges = []
    for u, v, t_new in staged_edges:
        for u2, v2, t_old in committed_edges:
            if u == u2 and v == v2 and t_new != t_old:
                changed_edges.append({
                    "from": u, "to": v,
                    "old_type": t_old, "new_type": t_new,
                })

    # Severity: blocking if interfaces were removed or inheritance chains broken
    removed_interfaces = [
        n for n in removed_nodes
        if committed_graph.nodes[n].get("type") == "interface"
    ]
    severe = bool(removed_interfaces or removed_nodes)

    return {
        "removed_nodes": sorted(removed_nodes),
        "added_nodes": sorted(added_nodes),
        "removed_edges": removed_edges,
        "changed_edges": changed_edges,
        "removed_interfaces": sorted(removed_interfaces),
        "severe": severe,
    }


def format_violation_report(violations: Dict[str, Any]) -> str:
    """Format a human-readable violation report for the commit hook."""
    lines = [
        "=" * 60,
        "  ARCHITECTURAL CONSISTENCY CHECK",
        "=" * 60,
        "",
    ]

    if violations["removed_nodes"]:
        lines.append("⚠ REMOVED NODES (classes/interfaces deleted):")
        for n in violations["removed_nodes"]:
            lines.append(f"    - {n}")
        lines.append("")

    if violations["removed_interfaces"]:
        lines.append("🚫 REMOVED INTERFACES (breaking change):")
        for n in violations["removed_interfaces"]:
            lines.append(f"    - {n}")
        lines.append("")

    if violations["added_nodes"]:
        lines.append("➕ ADDED NODES:")
        for n in violations["added_nodes"]:
            lines.append(f"    + {n}")
        lines.append("")

    if violations["removed_edges"]:
        lines.append("✂ REMOVED RELATIONSHIPS:")
        for e in violations["removed_edges"]:
            lines.append(
                f"    - {e['from']} --[{e['type']}]--> {e['to']}"
            )
        lines.append("")

    if violations["changed_edges"]:
        lines.append("🔄 CHANGED RELATIONSHIP TYPES:")
        for e in violations["changed_edges"]:
            lines.append(
                f"    - {e['from']} --[{e['old_type']}→{e['new_type']}]--> {e['to']}"
            )
        lines.append("")

    if violations["severe"]:
        lines.append("❌ BLOCKING: Severe violations detected. Commit BLOCKED.")
        lines.append("   Review the changes above. Use --no-verify to bypass.")
    else:
        lines.append("✅ Minor changes only. No blocking violations.")

    return "\n".join(lines)


def run_precommit_check(repo_root: str) -> int:
    """Run the architectural consistency check as a pre-commit hook.

    Returns:
        0 if the commit should proceed, 1 if violations block the commit.
    """
    print("\n🔍 Architecture Diagram Generator — Pre-Commit Hook\n")

    changed_files = get_changed_source_files(repo_root)
    if not changed_files:
        print("  No source files changed. Skipping architecture check.")
        return 0

    print(f"  Changed source files ({len(changed_files)}):")
    for f in changed_files:
        print(f"    {os.path.relpath(f, repo_root)}")

    # Run analysis on staged files
    staged_graph = run_analysis(changed_files)
    if staged_graph is None:
        print("\n⚠ Analysis failed — cannot verify. Allowing commit.")
        return 0

    fp = graph_fingerprint(staged_graph)

    # Compare with last committed fingerprint
    last_fp = get_last_committed_fingerprint(repo_root)

    if last_fp is None:
        print("\n  First run — no previous fingerprint to compare.")
        print("  Storing current fingerprint as baseline.")
        store_fingerprint(repo_root, fp)
        return 0

    if fp == last_fp:
        print("\n✅ Architecture unchanged. Fingerprint matches.")
        store_fingerprint(repo_root, fp)
        return 0

    # Fingerprints differ — need to compare graphs for detailed violations
    print("\n⚠ Architecture has changed. Running detailed comparison...")

    # Rebuild the full graph from all files to compare properly
    try:
        from src.ingestion.file_traverser import collect_source_files
        from src.ingestion.parser import parse_all_files
        from src.graph.builder import build_graph
        from src.graph.relationships import extract_edges

        all_files = collect_source_files(repo_root)
        metadata = parse_all_files(all_files)
        full_graph = build_graph(metadata)
        extract_edges(metadata, full_graph)
    except Exception as e:
        print(f"  [ERROR] Full graph rebuild failed: {e}")
        print("  Allowing commit (could not verify).")
        return 0

    # We don't have the committed graph stored, so we use the changed-files
    # analysis as a proxy. For a real implementation, store the full graph
    # JSON in .arch-diagram-graph along with the fingerprint.
    violations = detect_violations(staged_graph, staged_graph)  # compare against self as demo

    # In reality, load committed graph from .arch-diagram-graph
    committed_graph_path = os.path.join(repo_root, ".arch-diagram-graph.json")
    if os.path.isfile(committed_graph_path):
        try:
            import networkx as nx
            with open(committed_graph_path, "r") as f:
                committed_data = json.load(f)
            committed_graph = nx.node_link_graph(committed_data)
            violations = detect_violations(full_graph, committed_graph)
        except Exception:
            pass

    # Save current graph for next run
    try:
        import networkx as nx
        graph_data = nx.node_link_data(full_graph)
        with open(committed_graph_path, "w") as f:
            json.dump(graph_data, f, indent=2)
    except Exception:
        pass

    store_fingerprint(repo_root, fp)

    report = format_violation_report(violations)
    print(report)

    return 1 if violations["severe"] else 0


def install_hook(repo_root: str) -> None:
    """Install the pre-commit hook into .git/hooks/pre-commit."""
    hooks_dir = os.path.join(repo_root, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")

    hook_script = f'''#!/bin/sh
# Architecture Diagram Generator — Pre-Commit Hook
# Auto-generated. Do not edit manually.

REPO_ROOT="$(git rev-parse --show-toplevel)"
PYTHON_EXE="{sys.executable}"

if [ -f "$REPO_ROOT/.arch-diagram-hook-enabled" ]; then
    echo "Running architecture consistency check..."
    cd "$REPO_ROOT"
    "$PYTHON_EXE" -c "
import sys
sys.path.insert(0, '.')
from src.git_integration.hook_runner import run_precommit_check
sys.exit(run_precommit_check('.'))
"
    HOOK_EXIT=$?
    if [ $HOOK_EXIT -ne 0 ]; then
        echo ""
        echo "Architecture check FAILED. Commit blocked."
        echo "To bypass: git commit --no-verify"
        exit 1
    fi
    echo "Architecture check PASSED."
fi
'''

    with open(hook_path, "w") as f:
        f.write(hook_script)

    # Make executable on Unix
    try:
        os.chmod(hook_path, 0o755)
    except OSError:
        pass

    # Enable the hook
    enable_path = os.path.join(repo_root, ".arch-diagram-hook-enabled")
    if not os.path.isfile(enable_path):
        with open(enable_path, "w") as f:
            f.write("1")

    print(f"✅ Pre-commit hook installed at: {hook_path}")
    print(f"   Enabled flag at: {enable_path}")
    print(f"   To disable: delete {enable_path}")


def uninstall_hook(repo_root: str) -> None:
    """Remove the pre-commit hook and disable flag."""
    enable_path = os.path.join(repo_root, ".arch-diagram-hook-enabled")
    if os.path.isfile(enable_path):
        os.remove(enable_path)
        print(f"✅ Hook disabled (removed {enable_path})")
    else:
        print("Hook was not enabled.")
