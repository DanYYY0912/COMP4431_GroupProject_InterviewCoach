"""Reproducible evaluation runner. Smoke tests never count as release evidence."""

import argparse
import hashlib
import json
import random
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from evaluation.metrics import (
    citation_precision,
    cohens_kappa,
    edit_distance,
    error_rate,
    language_proxy,
    percentile,
    recall_at_k,
    sus_score,
    tokens,
    validate_output,
)
from ml.dataset import read_jsonl, validate_dataset, write_jsonl
from ml.schemas import SCHEMAS

RESULTS = Path("evaluation/results")
LIMITATIONS = [
    "No QLoRA training or fine-tuned adapter has been produced in this environment.",
    "Synthetic curriculum drafts require independent human review and duplicate removal before training.",
    "Schema smoke tests are software checks, not model quality measurements.",
    "Language detection is a script heuristic; Cantonese adherence requires human assessment.",
    "Blinded preference, four-speaker speech tests, usability, and clean-machine release gates remain pending.",
]


def write_result(suite, data):
    RESULTS.mkdir(parents=True, exist_ok=True)
    data = {"suite": suite, "recorded_at": datetime.now(UTC).isoformat(), **data}
    (RESULTS / f"{suite}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )
    evaluations = []
    for path in sorted(RESULTS.glob("*.json")):
        if path.name == "latest.json":
            continue
        item = json.loads(path.read_text())
        evaluations.append(
            {
                "name": item.get("suite", path.stem),
                "status": item.get("status", "pending"),
                "value": item.get("summary"),
                "sample_size": item.get("sample_size", 0),
                "details": str(path),
            }
        )
    latest = {
        "status": "development_evidence_only",
        "provider": "configured_at_runtime",
        "training": {
            "status": "not_trained",
            "base_model": "Qwen/Qwen3-4B-Instruct-2507",
            "draft_examples": 1500,
            "reviewed_examples": 0,
            "adapter_available": False,
        },
        "evaluations": evaluations,
        "limitations": LIMITATIONS,
    }
    run = Path("ml/runs/voxprep-qlora/model_manifest.json")
    if run.is_file():
        manifest = json.loads(run.read_text())
        latest["training"] = {
            "status": manifest["status"],
            "base_model": manifest["base_model"],
            "reviewed_examples": manifest["dataset"]["review_validation"]["reviewed"],
            "adapter_available": True,
            "best_validation_loss": manifest["best_validation_loss"],
        }
        latest["limitations"] = [s for s in LIMITATIONS if not s.startswith("No QLoRA")]
    (RESULTS / "latest.json").write_text(
        json.dumps(latest, indent=2, ensure_ascii=False)
    )
    print(
        json.dumps(
            {k: v for k, v in data.items() if k not in ("records", "raw")},
            indent=2,
            ensure_ascii=False,
        )
    )
    return data


def smoke():
    seeds = read_jsonl("ml/data/seed_examples.jsonl")
    check = validate_dataset(seeds)
    assert check["valid"], check["errors"]
    assert error_rate("we built tests", "we built tests") == 0
    assert error_rate("我做測試", "我做試", "character") == 0.25
    assert recall_at_k(["a", "c"], ["a", "b"], 5) == 0.5
    assert sus_score([5, 1] * 5) == 100
    assert abs(percentile([1, 2, 3, 4, 5], 95) - 4.8) < 1e-9
    return write_result(
        "smoke",
        {
            "status": "passed_software_checks_only",
            "sample_size": len(seeds),
            "summary": {
                "golden_schemas_valid": len(seeds),
                "metric_fixture_checks": 5,
                "release_gates_passed": False,
            },
            "records": [
                {
                    "id": r["id"],
                    "task": r["task"],
                    "language": r["language"],
                    "valid": True,
                }
                for r in seeds
            ],
        },
    )


def loopback(url):
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            "Evaluation endpoints must be local HTTP(S) services without embedded credentials"
        )
    return url.rstrip("/")


def complete(base_url, model, messages, schema, timeout=90):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "seed": 42,
        "max_tokens": 1536,
        "stream": True,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "voxprep_response",
                "strict": True,
                "schema": schema,
            },
        },
    }
    request = Request(
        loopback(base_url) + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    first = None
    content = ""
    finish_reason = None
    with urlopen(request, timeout=timeout) as response:
        for line in response:
            if not line.startswith(b"data:"):
                continue
            value = line[5:].strip()
            if value == b"[DONE]":
                break
            event = json.loads(value)
            choices = event.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {}).get("content") or ""
            if delta:
                if first is None:
                    first = time.perf_counter() - start
                content += delta
            finish_reason = choices[0].get("finish_reason") or finish_reason
    return content, first, time.perf_counter() - start, finish_reason


def model_evaluation(args):
    rows = read_jsonl(args.input)
    config = json.loads(Path(args.config).read_text())
    if len(rows) != 120 and not args.diagnostic:
        raise ValueError(
            "Assessed model evaluation requires exactly 120 held-out prompts"
        )
    if not args.diagnostic:
        validation = validate_dataset(rows, require_review=True)
        if not validation["valid"]:
            raise ValueError(
                "Held-out examples must pass current human review validation"
            )
        if not args.training_data:
            raise ValueError("--training-data is required to check independence")
        training = read_jsonl(args.training_data)
        role_overlap = {r["role_family"] for r in rows} & {
            r["role_family"] for r in training
        }
        source_overlap = {r["source_id"] for r in rows} & {
            r["source_id"] for r in training
        }
        if role_overlap or source_overlap:
            raise ValueError("Evaluation and training role/source groups overlap")
        from ml.dataset import near_duplicate_pairs

        eval_ids = {r["id"] for r in rows}
        for pair in near_duplicate_pairs(
            training + rows, limit=len(training) * len(rows) + len(rows) ** 2
        ):
            if (pair["left"] in eval_ids) != (pair["right"] in eval_ids):
                raise ValueError("Near-duplicate evaluation leakage")
    records = []
    for variant in ("base_rag", "lora_only", "lora_rag"):
        endpoint = config[variant]
        for row in rows:
            messages = [dict(m) for m in row["messages"][:-1]]
            if variant == "lora_only":
                request = json.loads(messages[-1]["content"])
                request["job_sources"] = []
                messages[-1]["content"] = json.dumps(request, ensure_ascii=False)
            record = {
                "id": row["id"],
                "variant": variant,
                "task": row["task"],
                "language": row["language"],
                "prompt_sha256": hashlib.sha256(
                    json.dumps(messages, sort_keys=True).encode()
                ).hexdigest(),
                "schema_valid": False,
                "language_proxy_pass": False,
            }
            try:
                raw, first, total, finish = complete(
                    endpoint["base_url"],
                    endpoint["model"],
                    messages,
                    SCHEMAS[row["task"]],
                )
                record.update(
                    {
                        "raw_output": raw,
                        "first_token_seconds": first,
                        "total_seconds": total,
                        "finish_reason": finish,
                    }
                )
                output = json.loads(raw)
                record["schema_valid"] = validate_output(output, row["task"])
                record["language_proxy_pass"] = language_proxy(output, row["language"])
            except (OSError, ValueError, KeyError, TypeError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            records.append(record)
            # Save every outcome including failures so interruptions do not erase evidence.
            write_jsonl(RESULTS / "model_raw.jsonl", records)
    summary = {}
    for variant in config:
        part = [r for r in records if r["variant"] == variant]
        if not part:
            continue
        first = [
            r["first_token_seconds"]
            for r in part
            if r.get("first_token_seconds") is not None
        ]
        summary[variant] = {
            "sample_size": len(part),
            "schema_validity": sum(r["schema_valid"] for r in part) / len(part),
            "language_script_proxy": sum(r["language_proxy_pass"] for r in part)
            / len(part),
            "failures": sum("error" in r for r in part),
            "first_token_p95_seconds": percentile(first, 95) if first else None,
            "language_adherence_human": "pending",
        }
    write_result(
        "model",
        {
            "status": "diagnostic_only"
            if args.diagnostic
            else "measured_pending_human_review",
            "sample_size": len(rows),
            "summary": summary,
            "config": config,
            "fixture_sha256": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
            "records": records,
        },
    )


def prepare(args):
    rows = read_jsonl(args.input)
    validation = validate_dataset(rows, require_review=not args.diagnostic)
    if not validation["valid"]:
        raise ValueError("Input examples failed validation")
    # Round robin over language/task strata, then deterministic shuffle within groups.
    groups = defaultdict(list)
    for row in rows:
        groups[(row["language"], row["task"])].append(row)
    for group in groups.values():
        random.Random(42).shuffle(group)
    selected = []
    while len(selected) < 120 and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(selected) < 120:
                selected.append(groups[key].pop())
    if len(selected) != 120:
        raise ValueError("Need at least 120 held-out records")
    write_jsonl(args.output, selected)
    print(f"Wrote {len(selected)} prompts to {args.output}")


def retrieval(args):
    rows = read_jsonl(args.input)
    if not rows:
        raise ValueError("Retrieval observations are empty")
    if not args.diagnostic and len(rows) != 40:
        raise ValueError("Assessed retrieval run requires 40 questions")
    records = []
    for row in rows:
        if not args.diagnostic and not row.get("reviewed_by"):
            raise ValueError("Supporting passages require human review")
        if "retrieved_ids" not in row:
            raise ValueError(
                "Provide actual ordered retrieved_ids from your retrieval run, not expected values"
            )
        records.append(
            {
                "id": row["id"],
                "recall_at_5": recall_at_k(
                    row["retrieved_ids"], row["relevant_ids"], 5
                ),
                "citation_precision": citation_precision(
                    row.get("cited_ids", []), row.get("supported_citation_ids", [])
                ),
                "unsupported_claims": row.get("unsupported_claims"),
                "total_claims": row.get("total_claims"),
                "injection_failed": row.get("injection_failed"),
            }
        )
    precision = [
        r["citation_precision"] for r in records if r["citation_precision"] is not None
    ]
    claims = [
        r
        for r in records
        if r["unsupported_claims"] is not None and r["total_claims"] is not None
    ]
    injection = [
        r["injection_failed"] for r in records if r["injection_failed"] is not None
    ]
    summary = {
        "recall_at_5": sum(r["recall_at_5"] for r in records) / len(records),
        "citation_precision": sum(precision) / len(precision) if precision else None,
        "citation_scored_count": len(precision),
        "unsupported_claim_rate": sum(r["unsupported_claims"] for r in claims)
        / sum(r["total_claims"] for r in claims)
        if claims and sum(r["total_claims"] for r in claims)
        else None,
        "prompt_injection_failure_rate": sum(injection) / len(injection)
        if injection
        else None,
    }
    write_result(
        "retrieval",
        {
            "status": "diagnostic_only" if args.diagnostic else "measured",
            "sample_size": len(rows),
            "summary": summary,
            "records": records,
        },
    )


def speech(args):
    rows = read_jsonl(args.input)
    if not rows or any(r.get("language") not in ("en-HK", "zh-HK") for r in rows):
        raise ValueError("Nonempty recordings with valid language labels are required")
    if not args.diagnostic:
        if len(rows) != 24 or len({r["speaker_id"] for r in rows}) < 4:
            raise ValueError(
                "Speech evaluation needs 24 recordings from at least four speakers"
            )
        if Counter(r["language"] for r in rows) != {"en-HK": 12, "zh-HK": 12}:
            raise ValueError("Balance the recordings: 12 per language")
        if any(
            not r.get("consent_recorded") or not r.get("reference_reviewed_by")
            for r in rows
        ):
            raise ValueError("Speaker consent and human reference review required")
        if {r["condition"] for r in rows} != {"clean", "noisy"}:
            raise ValueError("Include clean and noisy conditions")
    records = []
    for row in rows:
        unit = "character" if row["language"] == "zh-HK" else "word"
        ref = tokens(row["reference"], unit)
        hypothesis = tokens(row.get("hypothesis", ""), unit)
        if not ref:
            raise ValueError("Empty reference belongs in silence robustness tests")
        records.append(
            {
                "id": row["id"],
                "language": row["language"],
                "condition": row["condition"],
                "speaker_id": row["speaker_id"],
                "edits": edit_distance(ref, hypothesis),
                "reference_units": len(ref),
                "error_rate": error_rate(
                    row["reference"], row.get("hypothesis", ""), unit
                ),
                "corrected": bool(row.get("corrected")),
                "failure": row.get("failure"),
                "speech_end_to_audio_seconds": row.get("speech_end_to_audio_seconds"),
            }
        )
    summary = {}
    for language in ("en-HK", "zh-HK"):
        part = [r for r in records if r["language"] == language]
        if part:
            summary[language] = {
                "metric": "CER" if language == "zh-HK" else "WER",
                "corpus_error_rate": sum(r["edits"] for r in part)
                / sum(r["reference_units"] for r in part),
                "correction_rate": sum(r["corrected"] for r in part) / len(part),
                "failures": sum(bool(r["failure"]) for r in part),
                "sample_size": len(part),
            }
    latency = [
        r["speech_end_to_audio_seconds"]
        for r in records
        if r["speech_end_to_audio_seconds"] is not None
    ]
    summary["speech_end_to_audio_p95_seconds"] = (
        percentile(latency, 95) if latency else None
    )
    write_result(
        "speech",
        {
            "status": "diagnostic_only" if args.diagnostic else "measured",
            "sample_size": len(rows),
            "summary": summary,
            "records": records,
        },
    )


def human(args):
    data = json.loads(Path(args.input).read_text())
    preferences = data.get("preference", [])
    usability = data.get("usability", [])
    pairs = defaultdict(list)
    language_reviews = data.get("language_reviews", [])
    for review in language_reviews:
        if not review.get("reviewer_id") or type(review.get("adheres")) is not bool:
            raise ValueError(
                "Language ratings need a reviewer ID and a boolean adherence judgement"
            )
    if len({r["example_id"] for r in language_reviews}) != len(language_reviews):
        raise ValueError("Expected one final language judgement per example")
    if len({r.get("participant_id") for r in usability}) != len(usability) or any(
        not r.get("participant_id") for r in usability
    ):
        raise ValueError(
            "Usability participants must have distinct nonempty anonymous IDs"
        )
    for row in preferences:
        if row["choice"] not in ("A", "B", "tie") or row["lora_label"] not in (
            "A",
            "B",
        ):
            raise ValueError("Invalid blind preference labels")
        pairs[row["pair_id"]].append(row)
    for pair, ratings in pairs.items():
        if any(not r.get("reviewer_id") for r in ratings):
            raise ValueError("Real reviewer IDs are required")
        if len(ratings) != 2 or len({r["reviewer_id"] for r in ratings}) != 2:
            raise ValueError(f"{pair}: exactly two independent reviewers required")
        if len({r["lora_label"] for r in ratings}) != 1:
            raise ValueError(f"{pair}: inconsistent blinding key")
    if not args.diagnostic and (len(pairs) != 30 or not 5 <= len(usability) <= 8):
        raise ValueError(
            "Need 30 paired examples and five to eight usability participants"
        )
    agreements = [
        sorted(values, key=lambda r: r["reviewer_id"])
        for _, values in sorted(pairs.items())
    ]
    wins = sum(r["choice"] == r["lora_label"] for r in preferences)
    scores = [sus_score(row["sus_answers"]) for row in usability]
    summary = {
        "human_language_adherence": sum(r["adheres"] for r in language_reviews)
        / len(language_reviews)
        if language_reviews
        else None,
        "human_language_sample_size": len(language_reviews),
        "blinded_lora_preference": wins / len(preferences) if preferences else None,
        "ties": sum(r["choice"] == "tie" for r in preferences),
        "rating_count": len(preferences),
        "paired_examples": len(pairs),
        "cohens_kappa": cohens_kappa(
            [x[0]["choice"] for x in agreements], [x[1]["choice"] for x in agreements]
        )
        if agreements
        else None,
        "mean_sus": sum(scores) / len(scores) if scores else None,
        "completion_rate": sum(bool(row["completed"]) for row in usability)
        / len(usability)
        if usability
        else None,
        "usability_participants": len(usability),
    }
    write_result(
        "human",
        {
            "status": "diagnostic_only" if args.diagnostic else "measured",
            "sample_size": len(preferences) + len(usability),
            "summary": summary,
            "raw": data,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "suite", choices=["smoke", "prepare", "model", "retrieval", "speech", "human"]
    )
    p.add_argument("--input", default="evaluation/fixtures/model_prompts.jsonl")
    p.add_argument("--output", default="evaluation/fixtures/model_prompts.jsonl")
    p.add_argument("--config", default="evaluation/model_endpoints.example.json")
    p.add_argument("--training-data")
    p.add_argument(
        "--diagnostic",
        action="store_true",
        help="Allow incomplete or unreviewed fixtures; never counts as assessed evidence",
    )
    args = p.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        {
            "smoke": lambda _: smoke(),
            "prepare": prepare,
            "model": model_evaluation,
            "retrieval": retrieval,
            "speech": speech,
            "human": human,
        }[args.suite](args)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        p.exit(2, f"Evaluation cannot proceed: {exc}\n")


if __name__ == "__main__":
    main()
