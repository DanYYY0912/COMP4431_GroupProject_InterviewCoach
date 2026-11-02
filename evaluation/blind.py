"""Create reviewer packets without model labels; keep the key with the operator."""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from ml.dataset import read_jsonl


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", default="evaluation/results/model_raw.jsonl")
    p.add_argument("--prompts", default="evaluation/fixtures/model_prompts.jsonl")
    p.add_argument("--output", default="evaluation/results/blinded")
    args = p.parse_args()
    grouped = defaultdict(dict)
    for row in read_jsonl(args.input):
        if row["variant"] in ("base_rag", "lora_rag"):
            grouped[row["id"]][row["variant"]] = row
    candidates = [
        (key, rows)
        for key, rows in grouped.items()
        if set(rows) == {"base_rag", "lora_rag"}
    ]
    if len(candidates) < 30:
        raise SystemExit(
            "Need at least 30 complete pairs, including failed outputs rather than cherry-picking"
        )
    random.Random(42).shuffle(candidates)
    prompts = {r["id"]: r["messages"][-2]["content"] for r in read_jsonl(args.prompts)}
    packets = []
    keys = []
    rng = random.Random(420)
    for number, (example_id, rows) in enumerate(candidates[:30], 1):
        pair_id = f"pair-{number:02}"
        lora = rng.choice(["A", "B"])
        labels = {lora: "lora_rag", ("B" if lora == "A" else "A"): "base_rag"}
        packet = {"pair_id": pair_id, "prompt": prompts[example_id]}
        for label, variant in labels.items():
            result = rows[variant]
            packet[label] = result.get("raw_output") or "[No response: service failure]"
        packets.append(packet)
        keys.append({"pair_id": pair_id, "example_id": example_id, "lora_label": lora})
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reviewer_packet.json").write_text(
        json.dumps(packets, indent=2, ensure_ascii=False)
    )
    (out / "operator_key.json").write_text(json.dumps(keys, indent=2))
    ratings = [{"pair_id": r["pair_id"], "choice": "", "reason": ""} for r in packets]
    for reviewer in (1, 2):
        (out / f"reviewer_{reviewer}_ratings.json").write_text(
            json.dumps({"reviewer_id": "", "ratings": ratings}, indent=2)
        )
    print(
        "Share reviewer_packet.json and one rating form per reviewer. Keep operator_key.json hidden until both reviews finish."
    )


if __name__ == "__main__":
    main()
