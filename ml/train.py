"""Real CUDA QLoRA training. Imports large GPU dependencies only after data gates."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from ml.dataset import read_jsonl, validate_dataset


def mask_completion(full_ids, prompt_ids):
    """Mask prompt tokens; fail if chat-template boundaries do not align."""
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(
            "Chat template is not prefix-stable; assistant-only masking would be invalid"
        )
    if len(full_ids) <= len(prompt_ids):
        raise ValueError("No assistant tokens remain")
    return [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]


def validate_splits(data_dir, expected_examples=1500):
    directory = Path(data_dir)
    manifest = json.loads((directory / "split_manifest.json").read_text())
    splits = {
        name: read_jsonl(directory / f"{name}.jsonl")
        for name in ("train", "validation", "test")
    }
    all_rows = [row for rows in splits.values() for row in rows]
    validation = validate_dataset(
        all_rows,
        require_review=True,
        check_duplicates=True,
        expected_count=expected_examples,
    )
    if not validation["valid"]:
        raise ValueError(
            "Dataset release gate failed: " + "; ".join(validation["errors"][:12])
        )
    assignments = {}
    for name, rows in splits.items():
        if not rows:
            raise ValueError(f"{name} is empty")
        digest = hashlib.sha256((directory / f"{name}.jsonl").read_bytes()).hexdigest()
        if manifest["sha256"][name] != digest:
            raise ValueError(f"{name} hash differs from split manifest")
        for row in rows:
            for key in ("role_family", "source_id", "template_family"):
                group = (key, row[key])
                if group in assignments and assignments[group] != name:
                    raise ValueError(f"Cross-split {key} leakage")
                assignments[group] = name
    return splits, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="ml/config.json")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume-from-checkpoint")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    splits, data_manifest = validate_splits(
        config["data_dir"], config["expected_examples"]
    )
    if args.validate_only:
        print("Reviewed data, hashes, schemas and independent splits validated.")
        return
    if int(os.environ.get("WORLD_SIZE", "1")) != 1:
        raise SystemExit(
            "This configuration is for one GPU; distributed batches would change the experiment."
        )
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    import torch

    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA GPU required. Use Colab/Kaggle; this workflow never trains on the presentation Mac."
        )
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )

    set_seed(config["seed"])
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(config, indent=2))
    (out / "split_manifest.json").write_text(json.dumps(data_manifest, indent=2))
    (out / "environment.txt").write_text(
        subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    )
    tokenizer = AutoTokenizer.from_pretrained(
        config["base_model"], revision=config["revision"]
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    def encode(row):
        messages = row["messages"]
        prompt = tokenizer.apply_chat_template(
            messages[:-1], tokenize=True, add_generation_prompt=True
        )
        full = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=False
        )
        if len(full) > config["max_length"]:
            raise ValueError(
                f"{row['id']} has {len(full)} tokens; shorten it and re-review (limit {config['max_length']})."
            )
        return {
            "input_ids": full,
            "attention_mask": [1] * len(full),
            "labels": mask_completion(full, prompt),
        }

    encoded = {
        name: Dataset.from_list([encode(row) for row in rows])
        for name, rows in splits.items()
        if name != "test"
    }
    # HF PEFT quantization guide: NF4 + double quantization + k-bit preparation.
    # https://huggingface.co/docs/peft/developer_guides/quantization
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"],
        revision=config["revision"],
        quantization_config=quant,
        torch_dtype=dtype,
        device_map={"": 0},
        attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(
        model,
        LoraConfig(
            r=config["lora_r"],
            lora_alpha=config["lora_alpha"],
            lora_dropout=config["lora_dropout"],
            target_modules=config["target_modules"],
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    def collate(features):
        length = max(len(f["input_ids"]) for f in features)
        return {
            key: torch.tensor(
                [f[key] + [fill] * (length - len(f[key])) for f in features]
            )
            for key, fill in [
                ("input_ids", tokenizer.pad_token_id),
                ("attention_mask", 0),
                ("labels", -100),
            ]
        }

    class SaveLogs(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            with (out / "training_log.jsonl").open("a") as file:
                file.write(
                    json.dumps({"step": state.global_step, **(logs or {})}) + "\n"
                )

    # Trainer API fixed to Transformers 4.57.1. Identical evaluation/save intervals
    # are required for load_best_model_at_end.
    training_args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        per_device_train_batch_size=config["per_device_batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        learning_rate=config["learning_rate"],
        num_train_epochs=config["num_train_epochs"],
        lr_scheduler_type=config["lr_scheduler_type"],
        warmup_ratio=config["warmup_ratio"],
        seed=config["seed"],
        data_seed=config["seed"],
        bf16=bf16,
        fp16=not bf16,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        eval_strategy="steps",
        eval_steps=config["eval_steps"],
        save_strategy="steps",
        save_steps=config["eval_steps"],
        logging_steps=config["logging_steps"],
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encoded["train"],
        eval_dataset=encoded["validation"],
        data_collator=collate,
        processing_class=tokenizer,
        callbacks=[SaveLogs()],
    )
    result = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    metrics = trainer.evaluate()
    adapter = out / "adapter"
    trainer.save_model(str(adapter))
    tokenizer.save_pretrained(adapter)
    trainer.save_state()
    trainer.save_metrics("train", result.metrics)
    trainer.save_metrics("validation", metrics)
    manifest = {
        "status": "training_completed",
        "completed_at": datetime.now(UTC).isoformat(),
        "base_model": config["base_model"],
        "base_revision": getattr(model.config, "_commit_hash", None),
        "training_config": config,
        "dataset": data_manifest,
        "gpu": torch.cuda.get_device_name(0),
        "precision": "bf16" if bf16 else "fp16",
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "best_validation_loss": trainer.state.best_metric,
        "adapter_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in adapter.iterdir()
            if p.is_file()
        },
        "evaluation_release_status": "pending_held_out_and_human_evaluation",
    }
    (out / "model_manifest.json").write_text(json.dumps(manifest, indent=2))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for key, label in [("loss", "Training"), ("eval_loss", "Validation")]:
        points = [x for x in trainer.state.log_history if key in x]
        if points:
            plt.plot([p["step"] for p in points], [p[key] for p in points], label=label)
    plt.xlabel("Optimizer step")
    plt.ylabel("Cross entropy loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out / "loss.png", dpi=160)
    plt.close()
    print(f"Adapter and real training evidence saved to {out}")


if __name__ == "__main__":
    main()
