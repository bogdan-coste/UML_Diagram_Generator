"""Load the QLoRA adapter in-process and generate diagram source.

Deliberately lazy and optional. The API is expected to run without the training
stack installed (see ``src/api/main.py:_cuda_available``), so importing this
module must not import torch, peft or transformers -- those are pulled inside
``_load`` and any failure surfaces as ``None`` from :func:`generate_dsl`, which
lets the caller fall back to the deterministic exporter.
"""
from __future__ import annotations

import os
from typing import Any

DEFAULT_BASE = os.getenv("FINETUNED_BASE_MODEL", "bigcode/starcoder2-3b")
DEFAULT_ADAPTER = os.getenv("FINETUNED_ADAPTER", "models/starcoder2-3b-lora-v2")
DEFAULT_MAX_LENGTH = int(os.getenv("FINETUNED_MAX_LENGTH", "4096"))
DEFAULT_MAX_NEW_TOKENS = int(os.getenv("FINETUNED_MAX_NEW_TOKENS", "2048"))


def strip_code_fences(text: str) -> str:
    """Drop a wrapping ``` fence, which models add despite being told not to."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()

# One loaded adapter per (base, path) -- loading is ~10 s and several GB of VRAM,
# so it must happen once per process, not once per request.
_cache: dict[str, tuple[Any, Any, int | None]] = {}


def _resolve_eos(tokenizer: Any, model: Any) -> int | None:
    """EOS id that is actually inside the vocabulary.

    The published StarCoder2 checkpoint ships ``eos_token_id=50256`` while the
    vocabulary is 49152 wide, so generation could never emit it and would always
    run to ``max_new_tokens``.
    """
    vocab = model.config.vocab_size
    candidates = [tokenizer.eos_token_id]
    for name in ("<|endoftext|>", "</s>"):
        tid = tokenizer.convert_tokens_to_ids(name)
        if isinstance(tid, int) and tid >= 0:
            candidates.append(tid)
    for candidate in candidates:
        if isinstance(candidate, int) and 0 <= candidate < vocab:
            return candidate
    return None


def _load(base: str, adapter: str, fp16: bool) -> tuple[Any, Any, int | None]:
    key = f"{base}|{adapter}|{fp16}"
    if key in _cache:
        return _cache[key]

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA device visible to torch.")

    model = AutoModelForCausalLM.from_pretrained(
        base,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16 if fp16 else torch.bfloat16,
        ),
        device_map="auto",
    )
    model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    model.config.use_cache = True

    tokenizer = AutoTokenizer.from_pretrained(base)
    tokenizer.pad_token = tokenizer.eos_token

    _cache[key] = (model, tokenizer, _resolve_eos(tokenizer, model))
    return _cache[key]


def generate_dsl(
    prompt: str,
    *,
    base: str = DEFAULT_BASE,
    adapter: str = DEFAULT_ADAPTER,
    max_length: int = DEFAULT_MAX_LENGTH,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    fp16: bool = False,
) -> str | None:
    """Generate diagram source for *prompt*, or ``None`` if the adapter is unusable.

    Returning ``None`` rather than raising is deliberate: every caller here has a
    deterministic fallback, and a missing GPU is not a request failure.
    """
    try:
        model, tokenizer, eos_id = _load(base, adapter, fp16)
    except Exception:  # noqa: BLE001 - absent torch/GPU/adapter all mean "unavailable"
        return None

    import torch

    enc = tokenizer(
        prompt, return_tensors="pt", truncation=True, max_length=max_length
    ).to(model.device)

    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            eos_token_id=eos_id,
            pad_token_id=eos_id if eos_id is not None else tokenizer.pad_token_id,
        )

    text = tokenizer.decode(
        out[0][enc["input_ids"].shape[1]:],
        skip_special_tokens=True,
        # The default tokenization cleanup strips spaces before punctuation, which
        # is designed for WordPiece and corrupts BPE output. Never post-process
        # diagram source that way.
        clean_up_tokenization_spaces=False,
    )
    return text.strip()
