import argparse

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# `trl` exposes these through a lazy module: the names are re-exported only inside
# an `if TYPE_CHECKING:` block and swapped for a `_LazyModule` at runtime, so the
# type checker cannot see the re-export and calls the import private. The runtime
# import below is the documented one, so the diagnostic is suppressed rather than
# avoided by reaching into `trl.trainer.sft_config`.
from trl import SFTConfig, SFTTrainer  # pyright: ignore[reportPrivateImportUsage]

DEFAULT_OUT = "models/starcoder2-3b-lora"

# Examples used from the validation split during a smoke run. Enough to walk the
# eval code path at realistic sequence lengths without paying for a full pass.
SMOKE_EVAL_EXAMPLES = 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--base", default="bigcode/starcoder2-3b")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument(
        "--eval-batch-size",
        type=int,
        default=2,
        help="kept below the train batch size: eval cannot use gradient checkpointing",
    )
    ap.add_argument(
        "--save-steps",
        type=int,
        default=25,
        help="save (and eval) interval; must be a multiple of the eval interval",
    )
    ap.add_argument("--max-steps", type=int, default=0, help="0 = derive from --epochs")
    ap.add_argument("--fp16", action="store_true", help="pre-Ampere GPUs only")
    args = ap.parse_args()

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
    tok = AutoTokenizer.from_pretrained(args.base)
    tok.pad_token = tok.eos_token
    tok.padding_side = "right"

    train = load_dataset("json", data_files=f"{args.data}/train.jsonl", split="train")
    val = load_dataset("json", data_files=f"{args.data}/val.jsonl", split="train")
    print(f"train {len(train)} | val {len(val)}")

    smoke = args.max_steps > 0
    cfg = {
        "output_dir": args.out,
        "per_device_train_batch_size": 2,
        "per_device_eval_batch_size": args.eval_batch_size,
        "gradient_accumulation_steps": 8,
        "learning_rate": 2e-4,
        "lr_scheduler_type": "cosine",
        "warmup_steps": 20,
        "max_length": args.max_length,
        "completion_only_loss": True,
        "gradient_checkpointing": True,
        "eval_accumulation_steps": 1,
        "bf16": not args.fp16,
        "fp16": args.fp16,
        "logging_steps": 1,
        "seed": 42,
    }
    if smoke:
        # Evaluation stays ON, because the eval path is exactly what the smoke
        # test needs to exercise — it is what OOMed the first time it ran for
        # real. A small slice keeps the run quick.
        cfg.update(
            max_steps=args.max_steps,
            eval_strategy="steps",
            eval_steps=2,
            save_strategy="no",
        )
    else:
        cfg.update(
            num_train_epochs=args.epochs,
            eval_strategy="steps",
            eval_steps=args.save_steps,
            save_strategy="steps",
            save_steps=args.save_steps,
            save_total_limit=2,
            load_best_model_at_end=True,
        )

    eval_set = val.select(range(min(SMOKE_EVAL_EXAMPLES, len(val)))) if smoke else val

    trainer = SFTTrainer(
        model=model,
        train_dataset=train,
        eval_dataset=eval_set,
        peft_config=LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
        args=SFTConfig(**cfg),
    )
    trainer.train()
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print("SAVED", args.out)


if __name__ == "__main__":
    main()
