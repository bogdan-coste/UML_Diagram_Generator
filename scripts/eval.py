"""Evaluate a QLoRA adapter against the held-out split.

Reports the metrics the README promises: validity rate, entity precision /
recall / F1, edge precision / recall / F1, relationship-type accuracy and
context overlap.

Aggregation conventions, stated once so the numbers can be read correctly:

* Entity and edge metrics are **micro-averaged** over every example. A
  generation that does not parse counts as an *empty graph*, so an invalid
  output costs recall rather than silently dropping out of the average.
* `terminated_rate` is reported separately from validity, because a
  generation cut off by `max_new_tokens` still *parses* (the parser needs only
  one recognisable declaration) while missing its relationships and
  `@enduml`. "Parses" and "finished" are different claims.
* Relationship-type accuracy and context overlap are computed over **valid
  generations only** (there is no edge type to score otherwise).
* Validity is reported twice: on the raw completion, and after stripping a
  wrapping ``` fence. The gap between the two is how much of the failure is
  pure formatting.

Usage::

    python scripts/eval.py --verify-prompts          # cheap, CPU only
    python scripts/eval.py --limit 20                # quick smoke run
    python scripts/eval.py                           # full val split
"""
import argparse
import json
import sys
import time

import networkx as nx
import torch
from datasets import load_dataset
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, ".")
from src.dataset import parse_plantuml
from src.evaluation.comparator import (
    compare_context_quality,
    compare_entity_detection,
    compare_relationship_detection,
)
from src.prompts.prompt_templates import PromptTemplates

DEFAULT_ADAPTER = "models/starcoder2-3b-lora-v2"
DEFAULT_DATA = "data-v3"


def strip_code_fences(text: str) -> str:
    """Mirror ``DiagramGeneratorLLM._strip_code_fences``.

    Duplicated rather than imported so this script does not drag in the HTTP
    client (and its ``openai`` dependency) just to trim a fence.
    """
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def resolve_eos(tokenizer, model) -> int | None:
    """Pick an EOS id that is actually inside the vocabulary.

    The published StarCoder2 checkpoint ships ``eos_token_id=50256`` (GPT-2's)
    while the vocabulary is 49152 wide, so generation can never emit it and
    would run to ``max_new_tokens`` every time.
    """
    vocab = model.config.vocab_size
    candidates = [tokenizer.eos_token_id]
    for name in ("<|endoftext|>", "</s>"):
        tid = tokenizer.convert_tokens_to_ids(name)
        if isinstance(tid, int) and tid >= 0:
            candidates.append(tid)

    for cand in candidates:
        if isinstance(cand, int) and 0 <= cand < vocab:
            return cand
    return None


def _prf(matched: int, produced: int, truth: int) -> tuple[float, float, float]:
    """Micro precision/recall/F1, with an explicit empty-output convention."""
    precision = matched / produced if produced else (1.0 if truth == 0 else 0.0)
    recall = matched / truth if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def _edge_type_agreement(ref: nx.DiGraph, gen: nx.DiGraph) -> tuple[int, int]:
    """(correct, comparable) edge types over the shared node-name pairs."""

    def typed(graph: nx.DiGraph) -> dict[tuple[str, str], str]:
        return {
            (graph.nodes[u].get("name", u), graph.nodes[v].get("name", v)): graph.edges[u, v].get(
                "edge_type", "dependency"
            )
            for u, v in graph.edges()
        }

    a, b = typed(ref), typed(gen)
    shared = set(a) & set(b)
    return sum(1 for k in shared if a[k] == b[k]), len(shared)


def verify_prompts(rows) -> int:
    """How many stored prompts does ``PromptTemplates.build_prompt`` fail to reproduce?

    This is what proves the single-sourcing refactor did not change the
    training input.
    """
    from src.rag import canonical_ast_to_text  # lazy: keeps the GPU path dependency-free

    mismatches = 0
    for row in rows:
        rebuilt = PromptTemplates.build_prompt(
            canonical_ast_to_text(row["ast"]), output_format="plantuml"
        )
        if rebuilt != row["prompt"]:
            mismatches += 1
    return mismatches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=DEFAULT_ADAPTER)
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--base", default="bigcode/starcoder2-3b")
    ap.add_argument("--split", default="val")
    ap.add_argument("--limit", type=int, default=0, help="0 = every row")
    ap.add_argument(
        "--smallest",
        type=int,
        default=0,
        help="take the N smallest diagrams by entity count instead of the first N",
    )
    ap.add_argument("--max-new-tokens", type=int, default=2048)
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--report", default="eval-report.json")
    ap.add_argument("--dump", default="eval-generations.jsonl")
    ap.add_argument(
        "--verify-prompts",
        action="store_true",
        help="only re-derive the stored prompts; no model, no GPU",
    )
    ap.add_argument("--fp16", action="store_true", help="pre-Ampere GPUs only")
    args = ap.parse_args()

    rows = load_dataset(
        "json", data_files=f"{args.data}/{args.split}.jsonl", split="train"
    )
    if args.smallest and "entities" in rows.column_names:
        rows = rows.sort("entities").select(range(min(args.smallest, len(rows))))
    elif args.limit:
        rows = rows.select(range(min(args.limit, len(rows))))
    n = len(rows)
    print(f"{args.split}: {n} examples from {args.data}")

    if args.verify_prompts:
        if "ast" not in rows.column_names:
            raise SystemExit("No 'ast' column — rebuild the dataset to re-derive prompts.")
        print(f"build_prompt mismatches: {verify_prompts(rows)}/{n}")
        return

    if not torch.cuda.is_available():
        raise SystemExit("No CUDA device visible to torch.")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16 if args.fp16 else torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=bnb, device_map="auto"
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    model.config.use_cache = True

    tok = AutoTokenizer.from_pretrained(args.base)
    tok.pad_token = tok.eos_token
    eos_id = resolve_eos(tok, model)
    print(
        f"eos_token_id: config={model.config.eos_token_id} "
        f"resolved={eos_id} vocab={model.config.vocab_size}"
    )

    valid_raw = valid_clean = terminated_count = 0
    counts = {"ref_e": 0, "gen_e": 0, "match_e": 0, "ref_x": 0, "gen_x": 0, "match_x": 0}
    type_correct = type_total = 0
    overlaps: list[float] = []

    t0 = time.time()
    # Line-buffered so the JSONL file doubles as a progress indicator: a new
    # row appears on disk as each generation completes.
    with open(args.dump, "w", encoding="utf-8", buffering=1) as dump:
        for i, row in enumerate(rows):
            enc = tok(
                row["prompt"],
                return_tensors="pt",
                truncation=True,
                max_length=args.max_length,
            ).to(model.device)

            with torch.no_grad():
                out = model.generate(
                    **enc,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
                    eos_token_id=eos_id,
                    pad_token_id=eos_id if eos_id is not None else tok.pad_token_id,
                )
            text = tok.decode(
                out[0][enc["input_ids"].shape[1]:],
                skip_special_tokens=True,
                # Matches local_adapter.generate_dsl: the default cleanup is
                # destructive on BPE output, and validity is measured on exactly
                # what that function would return.
                clean_up_tokenization_spaces=False,
            )

            g_raw = parse_plantuml(text.strip())
            clean = strip_code_fences(text)
            g_clean = parse_plantuml(clean)
            valid_raw += g_raw is not None
            valid_clean += g_clean is not None
            # A generation that ran into the token cap ends mid-diagram but can
            # still parse, so completion is tracked as its own signal.
            terminated = clean.rstrip().endswith("@enduml")
            terminated_count += terminated

            ref = parse_plantuml(row["completion"])
            if ref is not None:
                # An unparseable generation is scored as an empty graph so that
                # it costs recall instead of vanishing from the average.
                gen = g_clean if g_clean is not None else nx.DiGraph()
                ent = compare_entity_detection(ref, gen)
                counts["ref_e"] += ent["static_entity_count"]
                counts["gen_e"] += ent["llm_entity_count"]
                counts["match_e"] += ent["matched_entities"]

                rel = compare_relationship_detection(ref, gen)
                counts["ref_x"] += rel["static_edge_count"]
                counts["gen_x"] += rel["llm_edge_count"]
                counts["match_x"] += rel["matched_edges"]

                overlaps.append(compare_context_quality(ref, gen)["context_overlap"])

                if g_clean is not None:
                    correct, comparable = _edge_type_agreement(ref, g_clean)
                    type_correct += correct
                    type_total += comparable

            dump.write(
                json.dumps(
                    {
                        "prompt": row["prompt"],
                        "reference": row["completion"],
                        "generated": clean,
                        "valid_raw": g_raw is not None,
                        "valid_clean": g_clean is not None,
                        "terminated": terminated,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            print(f"[{i + 1}/{n}] valid={g_clean is not None}", flush=True)

    ep, er, ef = _prf(counts["match_e"], counts["gen_e"], counts["ref_e"])
    xp, xr, xf = _prf(counts["match_x"], counts["gen_x"], counts["ref_x"])

    report = {
        "adapter": args.adapter,
        "base": args.base,
        "data": args.data,
        "split": args.split,
        "examples": n,
        "eos_token_id": eos_id,
        "max_new_tokens": args.max_new_tokens,
        "validity_rate_raw": round(valid_raw / n, 4),
        "validity_rate_fences_stripped": round(valid_clean / n, 4),
        "terminated_rate": round(terminated_count / n, 4),
        "entity_precision": ep,
        "entity_recall": er,
        "entity_f1": ef,
        "edge_precision": xp,
        "edge_recall": xr,
        "edge_f1": xf,
        "relationship_type_accuracy": (
            round(type_correct / type_total, 4) if type_total else 0.0
        ),
        "context_overlap_mean": (
            round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0
        ),
        "totals": {
            "reference_entities": counts["ref_e"],
            "generated_entities": counts["gen_e"],
            "matched_entities": counts["match_e"],
            "reference_edges": counts["ref_x"],
            "generated_edges": counts["gen_x"],
            "matched_edges": counts["match_x"],
        },
        "elapsed_sec": round(time.time() - t0, 1),
    }

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 56)
    print(f"  validity (raw)            {report['validity_rate_raw']:.2%}")
    print(f"  validity (fences stripped) {report['validity_rate_fences_stripped']:.2%}")
    print(f"  terminated with @enduml   {report['terminated_rate']:.2%}")
    print(f"  entity P / R / F1         {ep:.3f} / {er:.3f} / {ef:.3f}")
    print(f"  edge   P / R / F1         {xp:.3f} / {xr:.3f} / {xf:.3f}")
    print(f"  relationship type acc.    {report['relationship_type_accuracy']:.2%}")
    print(f"  context overlap           {report['context_overlap_mean']:.2%}")
    print(f"  elapsed                   {report['elapsed_sec']}s")
    print("=" * 56)
    print(f"report -> {args.report}\ngenerations -> {args.dump}")


if __name__ == "__main__":
    main()
