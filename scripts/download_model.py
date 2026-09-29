"""Download a base model from the HuggingFace Hub and verify it landed intact.

    python scripts/download_model.py                        # into the HF cache
    python scripts/download_model.py --out models/base      # into a plain directory
    python scripts/download_model.py --list                 # files and sizes only

Downloads are resumable — interrupting and re-running continues from where it
stopped, because the hub skips files already present. Use `--token` (or the
`HF_TOKEN` environment variable) to avoid anonymous rate limits, and
`HF_XET_HIGH_PERFORMANCE=1` for faster transfers on a good connection.

The integrity check reads only the safetensors *headers*, so it can confirm that
every weight shard is complete without loading the model into memory.
"""
import argparse
import json
import os
import shutil
import struct
from fnmatch import fnmatch
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

DEFAULT_REPO = "bigcode/starcoder2-3b"

# Some repos ship the same weights in several frameworks. transformers only needs
# safetensors here, so skip the duplicated PyTorch/TF/Flax/ONNX copies.
IGNORE_PATTERNS = ("*.bin", "*.h5", "*.msgpack", "*.onnx", "*.tflite", "*.ot")

# Without these, `AutoTokenizer` / `AutoModelForCausalLM` cannot load the model.
REQUIRED_FILES = ("config.json", "tokenizer_config.json")

SAFETENSORS_SUFFIX = ".safetensors"

# Guard against a corrupt header length being read as an absurd allocation size.
MAX_HEADER_BYTES = 100_000_000


def human(num_bytes: float) -> str:
    """Format a byte count for humans."""
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def read_safetensors_header(path: Path) -> tuple[int, int]:
    """Return ``(tensor_count, expected_file_size)`` for a safetensors shard.

    The format is an 8-byte little-endian header length, that many bytes of JSON,
    then the tensor payload. Parsing the header is enough to detect truncation,
    which is the failure mode a resumed download can leave behind.
    """
    with path.open("rb") as handle:
        raw = handle.read(8)
        if len(raw) != 8:
            raise ValueError("file is too short to contain a header")

        (header_len,) = struct.unpack("<Q", raw)
        if not 0 < header_len <= MAX_HEADER_BYTES:
            raise ValueError(f"implausible header length ({header_len})")

        header = json.loads(handle.read(header_len))

    offsets = [v["data_offsets"][1] for k, v in header.items() if k != "__metadata__"]
    if not offsets:
        raise ValueError("header declares no tensors")

    return len(offsets), 8 + header_len + max(offsets)


def verify_snapshot(path: Path) -> None:
    """Check that the snapshot is complete, exiting with a clear message if not."""
    missing = [name for name in REQUIRED_FILES if not (path / name).is_file()]
    if missing:
        raise SystemExit(
            f"Incomplete download: {', '.join(missing)} missing from {path}.\n"
            "Re-run this script to resume."
        )

    shards = sorted(path.glob(f"*{SAFETENSORS_SUFFIX}"))
    if not shards:
        raise SystemExit(f"No {SAFETENSORS_SUFFIX} weights found in {path}.")

    tensors = 0
    total = 0
    for shard in shards:
        try:
            count, expected = read_safetensors_header(shard)
        except (ValueError, KeyError) as exc:
            raise SystemExit(f"{shard.name}: unreadable safetensors header ({exc})") from exc

        actual = shard.stat().st_size
        if actual != expected:
            raise SystemExit(
                f"{shard.name} is truncated: {human(actual)} on disk but the header "
                f"implies {human(expected)}. Re-run this script to resume."
            )
        tensors += count
        total += actual

    print(f"  OK  {len(shards)} weight shard(s), {tensors} tensors, {human(total)}")


def select_files(files: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Drop duplicated weight formats, unless that would leave no weights at all."""
    kept = [(n, s) for n, s in files if not any(fnmatch(n, p) for p in IGNORE_PATTERNS)]
    if any(n.endswith(SAFETENSORS_SUFFIX) for n, _ in kept):
        return kept
    # Repo ships PyTorch pickles only — filtering them out would break the download.
    return files


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--repo", default=DEFAULT_REPO, help="model repo id")
    ap.add_argument(
        "--out",
        default=None,
        help="download into this directory instead of the HuggingFace cache",
    )
    ap.add_argument("--revision", default=None, help="branch, tag or commit hash")
    ap.add_argument("--token", default=os.getenv("HF_TOKEN"), help="hub access token")
    ap.add_argument("--force", action="store_true", help="re-download files already present")
    ap.add_argument("--list", action="store_true", help="list files and sizes, then exit")
    args = ap.parse_args()

    api = HfApi(token=args.token)
    info = api.model_info(args.repo, revision=args.revision, files_metadata=True)
    files = [(s.rfilename, s.size or 0) for s in (info.siblings or [])]

    wanted = select_files(files)
    revision = info.sha[:12] if info.sha else "unknown"
    print(f"{args.repo} @ {revision}")

    if args.list:
        total = 0
        for name, size in sorted(wanted):
            print(f"  {human(size):>10}  {name}")
            total += size
        print(f"  {human(total):>10}  TOTAL ({len(wanted)} files)")

        skipped = [n for n in dict(files) if n not in dict(wanted)]
        if skipped:
            print(f"\n  skipped as duplicate formats: {', '.join(sorted(skipped))}")
        return

    target = Path(args.out).expanduser().resolve() if args.out else None

    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        needed = sum(size for _, size in wanted)
        free = shutil.disk_usage(target.parent).free
        # 1.1x headroom: the hub also writes small metadata files alongside.
        if free < needed * 1.1:
            raise SystemExit(
                f"Not enough free space in {target.parent}: "
                f"need about {human(needed * 1.1)}, {human(free)} available."
            )

    print(f"  target: {target if target else 'HuggingFace cache'}")
    print("  downloading (resumable; re-run to continue) ...\n")

    path = snapshot_download(
        repo_id=args.repo,
        revision=args.revision,
        token=args.token,
        ignore_patterns=list(IGNORE_PATTERNS),
        local_dir=str(target) if target else None,
        force_download=args.force,
    )

    snapshot = Path(path)
    print()
    verify_snapshot(snapshot)

    print(f"\nModel ready at:\n  {snapshot}")
    print("\nUse it directly:\n  python -u scripts/train.py --base " + str(snapshot))


if __name__ == "__main__":
    main()
