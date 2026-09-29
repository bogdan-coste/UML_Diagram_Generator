"""Token-length distribution of the training pairs.

Answers whether ``max_length`` truncates the targets. If prompt+completion
exceeds the cap, the *tail* of the target — the relationship lines and
``@enduml`` — is cut off, which teaches the model to stop mid-diagram. If the
prompt alone exceeds the cap, the whole target is masked and the example is
dropped.

Needs a tokenizer, not a GPU.

Usage::

    python scripts/check_lengths.py --data data-v3
"""
import argparse

from datasets import load_dataset
from transformers import AutoTokenizer


def _pct(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(int(q * len(ordered)), len(ordered) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data-v3")
    ap.add_argument("--split", default="train")
    ap.add_argument("--base", default="bigcode/starcoder2-3b")
    ap.add_argument("--max-length", type=int, default=2048)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.base)
    rows = load_dataset(
        "json", data_files=f"{args.data}/{args.split}.jsonl", split="train"
    )

    prompt, total = [], []
    for row in rows:
        prompt.append(len(tok(row["prompt"])["input_ids"]))
        total.append(len(tok(row["prompt"] + row["completion"])["input_ids"]))

    cap = args.max_length
    n = len(rows)
    over_p = sum(p > cap for p in prompt)
    over_t = sum(t > cap for t in total)

    print(f"{args.split}: {n} pairs from {args.data}   (max_length={cap})")
    print(f"  prompt   p50={_pct(prompt, .5)}  p90={_pct(prompt, .9)}  "
          f"p99={_pct(prompt, .99)}  max={max(prompt)}")
    print(f"  total    p50={_pct(total, .5)}  p90={_pct(total, .9)}  "
          f"p99={_pct(total, .99)}  max={max(total)}")
    print(f"  prompt alone over cap:      {over_p}/{n} ({over_p / n:.1%})")
    print(f"  prompt+completion over cap: {over_t}/{n} ({over_t / n:.1%})")

    print()
    if over_p:
        print(f"  {over_p} examples have their entire target cut -> dropped as fully masked")
    if over_t > over_p:
        print(
            f"  a further {over_t - over_p} keep the prompt but lose the completion tail\n"
            "  (relationship lines and @enduml) -> trains the model to stop mid-diagram"
        )
    if not over_t:
        print(f"  nothing exceeds the cap; targets are intact")


if __name__ == "__main__":
    main()
