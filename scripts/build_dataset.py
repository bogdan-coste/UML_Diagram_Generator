import argparse
import json
import os
import sys

import networkx as nx

sys.path.insert(0, ".")
from src.dataset import graph_similarity, parse_plantuml
from src.exporters.plantuml_exporter import to_plantuml
from src.graph.builder import build_graph
from src.graph.relationships import extract_edges
from src.ingestion.file_traverser import collect_source_files
from src.ingestion.parser import parse_all_files
from src.prompts.prompt_templates import PromptTemplates as P
from src.rag import canonical_ast_to_text, graph_to_canonical_ast

MIN_ENTITIES = 3
MAX_ENTITIES = 30
MAX_CHARS = 6000
MIN_ROUNDTRIP = 0.80

def relabel(graph):
    """Key nodes by simple name so source and round-tripped graphs are comparable."""
    return nx.relabel_nodes(graph, {n: graph.nodes[n].get("name", n) for n in graph.nodes})


def _make_pair(chunk, package):
    """Round-trip validate one chunk and build a training pair, or return None."""
    for node in chunk.nodes:
        chunk.nodes[node]["context"] = package

    dsl = to_plantuml(chunk)
    if len(dsl) > MAX_CHARS:
        return None

    back = parse_plantuml(dsl)
    if back is None:
        return None

    score = graph_similarity(relabel(chunk), relabel(back))
    if score["node_jaccard"] < MIN_ROUNDTRIP or score["edge_jaccard"] < MIN_ROUNDTRIP:
        return None

    # Keep the AST on the row so prompt formats can be re-rendered later without
    # re-parsing every repository.
    canonical_ast = graph_to_canonical_ast(chunk)
    description = canonical_ast_to_text(canonical_ast)
    prompt = P.build_prompt(description, output_format="plantuml")
    return {
        "prompt": prompt,
        "completion": dsl,
        "ast": canonical_ast,
        "package": package,
        "entities": chunk.number_of_nodes(),
        "roundtrip": round(score["edge_jaccard"], 3),
    }


def build_repo_pairs(repo_root):
    """One pair per connected chunk within each package of the repository."""
    metadata = parse_all_files(collect_source_files(repo_root))
    graph = build_graph(metadata)
    extract_edges(metadata, graph)
    if graph.number_of_nodes() == 0:
        return []

    by_package = {}
    for node, data in graph.nodes(data=True):
        by_package.setdefault(data.get("package") or "Default", []).append(node)

    pairs = []
    for package, nodes in by_package.items():
        sub = graph.subgraph(nodes).copy()
        components = sorted(nx.weakly_connected_components(sub), key=lambda c: sorted(c))
        for component in components:
            chunk = sub.subgraph(component).copy()
            size = chunk.number_of_nodes()
            if not (MIN_ENTITIES <= size <= MAX_ENTITIES):
                continue
            pair = _make_pair(chunk, package)
            if pair is not None:
                pair["source"] = repo_root
                pairs.append(pair)
    return pairs


def _fits_context(tokenizer, rows, max_length, label):
    """Drop pairs whose prompt+completion exceeds *max_length* tokens.

    The trainer truncates at ``max_length``, and a cut completion loses the
    relationship lines and ``@enduml`` -- which teaches the model to stop
    mid-diagram. Dropping is the lesser evil only because the cap is set as high
    as the context window allows, so just the unrepresentable tail goes.
    """
    keep = [
        row
        for row in rows
        if len(tokenizer(row["prompt"] + row["completion"])["input_ids"]) <= max_length
    ]
    dropped = len(rows) - len(keep)
    print(f"{label}: dropped {dropped}/{len(rows)} over {max_length} tokens ({len(keep)} kept)")
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--out", default="data")
    ap.add_argument("--val-every", type=int, default=5, help="every Nth repo goes to val")
    ap.add_argument(
        "--max-length",
        type=int,
        default=4096,
        help="context window; pairs longer than this are dropped, not truncated",
    )
    ap.add_argument("--tokenizer", default="bigcode/starcoder2-3b")
    ap.add_argument(
        "--no-token-filter",
        dest="token_filter",
        action="store_false",
        help="keep over-length pairs; they will be truncated during training",
    )
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    train, val, seen = [], [], set()

    for i, root in enumerate(sorted(args.roots)):
        pairs = [p for p in build_repo_pairs(root) if p["completion"] not in seen]
        seen.update(p["completion"] for p in pairs)
        bucket = val if i % args.val_every == 0 else train
        bucket.extend(pairs)
        sizes = [p["entities"] for p in pairs] or [0]
        print(f"{root}: {len(pairs)} pairs (entities {min(sizes)}-{max(sizes)})")

    # Run before the sort so the split (which is repo-position based) is
    # unaffected; this only removes rows, it never reassigns them.
    if args.token_filter:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
        train = _fits_context(tokenizer, train, args.max_length, "train")
        val = _fits_context(tokenizer, val, args.max_length, "val")

    for rows in (train, val):
        rows.sort(key=lambda r: (r["source"], r["package"], r["completion"]))

    for name, rows in (("train", train), ("val", val)):
        with open(os.path.join(args.out, f"{name}.jsonl"), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)

    print(f"\ntrain {len(train)} | val {len(val)} | unique DSL {len(seen)}")


if __name__ == "__main__":
    main()
