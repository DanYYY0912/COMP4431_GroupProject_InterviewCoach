"""Interactive human review; approvals always identify the exact content reviewed."""

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from ml.dataset import content_hash, read_jsonl
from ml.schemas import SCHEMAS, validate


def atomic_write(path, text):
    """Replace a complete file atomically; an interruption preserves the last decision."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            name = file.name
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def reviewer_name(value):
    value = value.strip()
    if not value:
        raise ValueError("Reviewer must be a real, nonblank name")
    return value


def identity(value):
    return reviewer_name(value).casefold()


def slug(value):
    normalized = identity(value)
    readable = re.sub(r"[^\w-]+", "-", normalized).strip("-_")[:60] or "reviewer"
    return readable + "-" + hashlib.sha256(normalized.encode()).hexdigest()[:10]


def edit_path(directory, example_id):
    if not re.fullmatch(r"[\w.-]+", example_id) or example_id in (".", ".."):
        raise ValueError(f"Unsafe example ID: {example_id!r}")
    return Path(directory) / f"{example_id}.json"


def parse_shard(value):
    try:
        number, total = map(int, value.split("/"))
        if not 1 <= number <= total:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("Shard must be N/T with 1 <= N <= T") from None
    return number, total


def shard_rows(rows, shard):
    number, total = parse_shard(shard)
    # Stable file order; no Python hash randomization or reviewer-dependent assignment.
    return [row for i, row in enumerate(rows) if i % total == number - 1]


def apply_edits(rows, edits_dir):
    result = copy.deepcopy(rows)
    for row in result:
        path = edit_path(edits_dir, row["id"])
        if path.exists():
            edit = json.loads(path.read_text(encoding="utf-8"))
            original_hash = content_hash(row)
            row["messages"][-1]["content"] = json.dumps(
                edit["assistant"], ensure_ascii=False
            )
            final_hash = content_hash(row)
            if edit["example_id"] != row["id"] or original_hash not in (
                edit["base_content_sha256"],
                edit.get("input_content_sha256"),
                final_hash,
            ):
                raise ValueError(
                    f"{row['id']}: edit conflicts with the input; resolve before reviewing"
                )
        row["content_sha256"] = content_hash(row)
        row["reviews"] = [
            r
            for r in row.get("reviews", [])
            if r.get("content_sha256") == row["content_sha256"]
        ]
    return result


def load_records(directory):
    return [
        record
        for path in sorted(Path(directory).glob("*.jsonl"))
        for record in read_jsonl(path)
    ]


def current_reviews(row, records):
    """A reviewer's latest decision replaces earlier decisions, including approvals."""
    latest = {}
    candidates = [
        *row.get("reviews", []),
        *(r for r in records if r["example_id"] == row["id"]),
    ]
    for record in sorted(candidates, key=lambda r: r["reviewed_at"]):
        latest[identity(record["reviewer"])] = record
    return [r for r in latest.values() if r["content_sha256"] == row["content_sha256"]]


def eligible(row, records, reviewer, second=False, revisit=False):
    reviews = current_reviews(row, records)
    own = next(
        (r for r in reviews if identity(r["reviewer"]) == identity(reviewer)), None
    )
    if own and (not revisit or own["decision"] == "approved"):
        return False
    if second:
        return (
            bool(row.get("double_review_required"))
            and not (own and own["decision"] == "approved")
            and any(
                r["decision"] == "approved"
                and identity(r["reviewer"]) != identity(reviewer)
                for r in reviews
            )
        )
    return True


def automatic_checks(row):
    output = json.loads(row["messages"][-1]["content"])
    errors = validate(output, SCHEMAS[row["task"]])
    if errors:
        return errors
    try:
        from backend.app.coach import (
            ModelCoachTurn,
            ModelReport,
            check_question_output,
            check_report_output,
        )
        from backend.app.schemas import Citation
    except ImportError:
        return []  # Schema validation supports WS3 before WS1 is merged.
    try:
        user = json.loads(row["messages"][1]["content"])
        sources = [
            Citation.model_validate(s)
            for s in user.get("quoted_sources", user.get("job_sources", []))
        ]
        competencies = user["allowed_competencies"]
        if row["task"] in ("question", "safety"):
            check_question_output(
                ModelCoachTurn.model_validate(output),
                competencies,
                row["language"],
                sources,
            )
        else:
            excerpts = user.get("quoted_answer_excerpts", [user.get("answer", "")])
            check_report_output(
                ModelReport.model_validate(output),
                competencies,
                row["language"],
                excerpts,
                sources,
            )
    except (KeyError, ValueError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def save_edit(row, assistant, directory):
    updated = copy.deepcopy(row)
    updated["messages"][-1]["content"] = json.dumps(assistant, ensure_ascii=False)
    updated["content_sha256"] = content_hash(updated)
    errors = automatic_checks(updated)
    if errors:
        raise ValueError("Invalid edit: " + "; ".join(errors))
    path = edit_path(directory, row["id"])
    base_hash = (
        json.loads(path.read_text())["base_content_sha256"]
        if path.exists()
        else content_hash(row)
    )
    atomic_write(
        path,
        json.dumps(
            {
                "example_id": row["id"],
                "base_content_sha256": base_hash,
                "input_content_sha256": content_hash(row),
                "assistant": assistant,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    updated["reviews"] = [
        r
        for r in updated.get("reviews", [])
        if r["content_sha256"] == updated["content_sha256"]
    ]
    return updated


def record_decision(row, reviewer, decision, directory, reason=""):
    reviewer = reviewer_name(reviewer)
    if decision not in ("approved", "rejected"):
        raise ValueError("A human must choose approved or rejected")
    if decision == "rejected" and not reason.strip():
        raise ValueError("Rejection requires a reason")
    if decision == "approved" and (errors := automatic_checks(row)):
        raise ValueError("Cannot approve invalid output: " + "; ".join(errors))
    record = {
        "example_id": row["id"],
        "reviewer": reviewer,
        "decision": decision,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "content_sha256": content_hash(row),
        "reason": reason.strip(),
    }
    path = Path(directory) / f"{slug(reviewer)}.jsonl"
    records = read_jsonl(path) if path.exists() else []
    records.append(record)
    atomic_write(
        path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    )
    return record


def merge(rows, reviews_dir, edits_dir, output):
    rows = apply_edits(rows, edits_dir)
    records = load_records(reviews_dir)
    known = {row["id"] for row in rows}
    if any(r["example_id"] not in known for r in records):
        raise ValueError("Review log contains IDs absent from the input")
    for row in rows:
        row["reviews"] = [
            {k: v for k, v in r.items() if k != "example_id"}
            for r in current_reviews(row, records)
        ]
        if errors := automatic_checks(row):
            raise ValueError(f"{row['id']}: " + "; ".join(errors))
    atomic_write(
        output,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )
    return rows


def status(rows, records):
    completed = Counter()
    rejected = Counter()
    remaining = second_done = second_total = 0
    for row in rows:
        reviews = current_reviews(row, records)
        approvals = {
            identity(r["reviewer"]) for r in reviews if r["decision"] == "approved"
        }
        for r in reviews:
            (completed if r["decision"] == "approved" else rejected)[r["reviewer"]] += 1
        required = 2 if row.get("double_review_required") else 1
        remaining += len(approvals) < required
        if row.get("double_review_required"):
            second_total += 1
            second_done += len(approvals) >= 2
    names = sorted(completed.keys() | rejected.keys())
    return {
        "total": len(rows),
        "remaining": remaining,
        "reviewers": {
            name: {
                "approved": completed[name],
                "rejected": rejected[name],
                "remaining": sum(eligible(row, records, name) for row in rows),
            }
            for name in names
        },
        "second_review": {
            "completed": second_done,
            "required": second_total,
            "remaining": second_total - second_done,
        },
    }


def evidence_spans(output):
    if isinstance(output, dict):
        for key, value in output.items():
            if key == "evidence" and isinstance(value, str) and value:
                yield value
            else:
                yield from evidence_spans(value)
    elif isinstance(output, list):
        for value in output:
            yield from evidence_spans(value)


def display_example(row):
    user = json.loads(row["messages"][1]["content"])
    assistant = json.loads(row["messages"][-1]["content"])
    print(f"\n{row['id']} | task={row['task']} | language={row['language']}")
    shown = copy.deepcopy(user)
    for key in ("quoted_sources", "job_sources"):
        for source in shown.get(key, []):
            text = source.get("text", "")
            source["text"] = text[:300] + (
                " … [display truncated]" if len(text) > 300 else ""
            )
    print("USER\n" + json.dumps(shown, ensure_ascii=False, indent=2))
    previous = user.get("previous_answer") or {}
    answers = user.get(
        "quoted_answer_excerpts", [previous.get("transcript", user.get("answer", ""))]
    )
    spans = sorted(set(evidence_spans(assistant)), key=len, reverse=True)
    print("ANSWER EVIDENCE (marked spans are exact quotes)")
    for answer in answers:
        if spans:
            answer = re.sub(
                "|".join(re.escape(span) for span in spans),
                lambda m: f"⟦{m.group()}⟧",
                answer,
            )
        print(answer)
    print("ASSISTANT\n" + json.dumps(assistant, ensure_ascii=False, indent=2))
    errors = automatic_checks(row)
    print(
        "AUTOMATIC CHECKS: "
        + ("; ".join(errors) if errors else "PASS (human judgement still required)")
    )


def edit_in_editor(row, directory):
    editor = os.environ.get("EDITOR")
    if not editor or not shlex.split(editor):
        raise ValueError(
            "Set $EDITOR before using e (for example: export EDITOR='nano')"
        )
    with tempfile.TemporaryDirectory(prefix="voxprep-review-") as temp:
        path = Path(temp) / "assistant.json"
        path.write_text(
            json.dumps(
                json.loads(row["messages"][-1]["content"]), ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        subprocess.run([*shlex.split(editor), str(path)], check=True)
        return save_edit(row, json.loads(path.read_text(encoding="utf-8")), directory)


def start(args):
    reviewer = reviewer_name(args.reviewer)
    ids = {r["id"] for r in shard_rows(read_jsonl(args.input), args.shard)}
    for example_id in [r["id"] for r in read_jsonl(args.input) if r["id"] in ids]:
        while True:
            rows = apply_edits(read_jsonl(args.input), args.edits_dir)
            row = next(r for r in rows if r["id"] == example_id)
            records = load_records(args.reviews_dir)
            if not eligible(row, records, reviewer, args.second, args.revisit):
                break
            display_example(row)
            try:
                command = (
                    input("[a] approve [r] reject [e] edit [s] skip [q] quit: ")
                    .strip()
                    .lower()
                )
                if command == "q":
                    return
                if command == "s":
                    break
                if command == "e":
                    edit_in_editor(row, args.edits_dir)
                    continue
                if command in ("a", "r"):
                    reason = (
                        input("Rejection reason (required): ").strip()
                        if command == "r"
                        else ""
                    )
                    fresh = next(
                        r
                        for r in apply_edits(read_jsonl(args.input), args.edits_dir)
                        if r["id"] == example_id
                    )
                    if fresh["content_sha256"] != row["content_sha256"]:
                        raise ValueError(
                            "Content changed while reviewing; review the new target first"
                        )
                    record_decision(
                        row,
                        reviewer,
                        "approved" if command == "a" else "rejected",
                        args.reviews_dir,
                        reason,
                    )
                    break
            except (ValueError, OSError, subprocess.CalledProcessError) as exc:
                print(f"Not saved: {exc}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("start", "merge", "status"):
        p = sub.add_parser(command)
        p.add_argument(
            "--input", type=Path, default=Path("ml/data/reviewed_examples.jsonl")
        )
        p.add_argument("--reviews-dir", type=Path)
        p.add_argument("--edits-dir", type=Path)
        if command == "start":
            p.add_argument("--reviewer", required=True)
            p.add_argument("--shard", default="1/1")
            p.add_argument("--second", action="store_true")
            p.add_argument(
                "--revisit", action="store_true", help="Revisit own rejected examples"
            )
        if command == "merge":
            p.add_argument("--output", type=Path)
    args = parser.parse_args()
    args.reviews_dir = args.reviews_dir or args.input.parent / "reviews"
    args.edits_dir = args.edits_dir or args.input.parent / "edits"
    try:
        if args.command == "start":
            start(args)
        elif args.command == "merge":
            rows = merge(
                read_jsonl(args.input),
                args.reviews_dir,
                args.edits_dir,
                args.output or args.input,
            )
            print(
                f"Merged {len(rows)} examples; run ml.dataset validate --require-review --check-duplicates next."
            )
        else:
            rows = apply_edits(read_jsonl(args.input), args.edits_dir)
            print(
                json.dumps(
                    status(rows, load_records(args.reviews_dir)),
                    ensure_ascii=False,
                    indent=2,
                )
            )
    except (EOFError, KeyboardInterrupt):
        print(
            "\nStopped. Saved decisions are preserved; rerun the same command to resume."
        )
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
