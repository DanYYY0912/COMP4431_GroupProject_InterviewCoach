"""Score the standard ten-item System Usability Scale from real participant rows.

Input is a CSV or JSONL sheet with one row per participant. This script does not
generate, impute, average over or default any answer: every score below comes
from a row someone actually filled in. An input with zero rows is refused,
because writing a 0 or a "pending" number would create evidence that does not
exist.

Required per row:
    participant_id    anonymous ID such as P1 (names must not be recorded)
    q1 ... q10        the ten SUS responses, whole numbers 1-5, in questionnaire order
                      (JSONL may instead carry "sus_answers": [ ... ten values ... ])

Optional per row:
    flow_completed    true/false (accepts 1/0, yes/no); omit if not observed
    duration_minutes  nonnegative number of minutes for the timed flow

Usage:
    python scripts/score_sus.py evaluation/raw/usability_20261116.csv \
        --out evaluation/results/usability_metrics.json

The SUS formula is the standard one: for the five positively worded items take
(item - 1), for the five negatively worded items take (5 - item), sum all ten
contributions and multiply by 2.5. Scores therefore run from 0 to 100; they are
not percentages.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import sus_score

SUS_TARGET = 80.0
COMPLETION_TARGET = 0.90
PARTICIPANTS_MIN = 5
PARTICIPANTS_MAX = 8
ITEM_FIELDS = tuple(f"q{index}" for index in range(1, 11))
TRUE_WORDS = {"1", "true", "yes", "y", "completed", "complete"}
FALSE_WORDS = {"0", "false", "no", "n", "not completed", "incomplete", "abandoned"}


def _parse_item(value, participant_id, field):
    """Return one 1-5 response, refusing blanks, ranges and non-integers."""
    if isinstance(value, bool) or value is None:
        raise ValueError(
            f"{participant_id}: {field} is missing or not a whole number 1-5 "
            f"(got {value!r})"
        )
    if isinstance(value, int):
        score = value
    elif isinstance(value, str) and value.strip().isdigit():
        score = int(value.strip())
    else:
        raise ValueError(
            f"{participant_id}: {field} must be a whole number 1-5 (got {value!r})"
        )
    if not 1 <= score <= 5:
        raise ValueError(
            f"{participant_id}: {field} is outside the 1-5 scale (got {score})"
        )
    return score


def _parse_optional_bool(value, participant_id):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().casefold()
        if token in TRUE_WORDS:
            return True
        if token in FALSE_WORDS:
            return False
    raise ValueError(
        f"{participant_id}: flow_completed must be true/false, yes/no or 1/0 "
        f"(got {value!r})"
    )


def _parse_duration(value, participant_id):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise TypeError(
            f"{participant_id}: duration_minutes must be a nonnegative number"
        )
    try:
        minutes = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{participant_id}: duration_minutes must be a nonnegative number "
            f"(got {value!r})"
        ) from exc
    if not math.isfinite(minutes) or minutes < 0:
        raise ValueError(
            f"{participant_id}: duration_minutes must be a finite nonnegative number "
            f"(got {value!r})"
        )
    return minutes


def _normalise_record(record, position):
    if not isinstance(record, dict):
        raise TypeError(f"row {position}: each record must be a JSON object")
    participant_id = str(record.get("participant_id") or "").strip()
    if not participant_id:
        raise ValueError(f"row {position}: participant_id is required")

    answers = record.get("sus_answers")
    if answers is None:
        answers = [record.get(field) for field in ITEM_FIELDS]
    elif not isinstance(answers, list):
        raise ValueError(f"{participant_id}: sus_answers must be a list of ten values")
    if len(answers) != 10:
        raise ValueError(
            f"{participant_id}: expected ten SUS answers, got {len(answers)}"
        )
    parsed = [
        _parse_item(value, participant_id, f"q{index}")
        for index, value in enumerate(answers, 1)
    ]
    return {
        "participant_id": participant_id,
        "sus_answers": parsed,
        "sus": sus_score(parsed),
        "flow_completed": _parse_optional_bool(
            record.get("flow_completed"), participant_id
        ),
        "duration_minutes": _parse_duration(
            record.get("duration_minutes"), participant_id
        ),
    }


def read_rows(path):
    """Read a CSV or JSON/JSONL sheet and validate every row.

    Blank lines are ignored; a header-only or empty file yields an empty list so
    the caller can refuse to emit metrics.
    """
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    stripped = text.lstrip()
    if path.suffix.lower() in {".json", ".jsonl"} or stripped.startswith(("{", "[")):
        records = _read_json_records(text)
    else:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            return []
        records = list(reader)
    rows = [_normalise_record(record, position) for position, record in enumerate(records, 1)]
    seen = set()
    for row in rows:
        if row["participant_id"] in seen:
            raise ValueError(
                f"duplicate participant_id {row['participant_id']!r}; "
                "each participant must appear once"
            )
        seen.add(row["participant_id"])
    return rows


def _read_json_records(text):
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON input must be an array of participant objects")
        return data
    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
    return records


def summarise(rows):
    """Return descriptive statistics and the release-gate evaluation."""
    scores = [row["sus"] for row in rows]
    count = len(scores)
    if count == 0:
        raise ValueError("Cannot summarise zero participants")
    mean = statistics.fmean(scores)
    median = statistics.median(scores)
    stdev = statistics.stdev(scores) if count > 1 else None
    flow = [row["flow_completed"] for row in rows if row["flow_completed"] is not None]
    completion_rate = sum(flow) / len(flow) if flow else None
    durations = [
        row["duration_minutes"]
        for row in rows
        if row["duration_minutes"] is not None
    ]
    mean_duration = statistics.fmean(durations) if durations else None

    sample_ok = PARTICIPANTS_MIN <= count <= PARTICIPANTS_MAX
    completion_ok = completion_rate is not None and completion_rate >= COMPLETION_TARGET
    sus_ok = mean >= SUS_TARGET
    all_met = sample_ok and completion_ok and sus_ok
    if count < PARTICIPANTS_MIN:
        sample_status = "below_release_sample"
        note = (
            f"Only {count} real participant(s); the release gate requires "
            f"{PARTICIPANTS_MIN}-{PARTICIPANTS_MAX}."
        )
    elif count > PARTICIPANTS_MAX:
        sample_status = "above_release_sample"
        note = (
            f"{count} participants exceed the {PARTICIPANTS_MIN}-{PARTICIPANTS_MAX} "
            "release range; start a new round instead of adding more rows."
        )
    else:
        sample_status = "release_sample"
        note = "Sample size is within the 5-8 range."
    if not completion_ok:
        note += " Flow completion is missing or below 90%."
    if not sus_ok:
        note += " Mean SUS is below 80."
    if all_met:
        note = (
            "All three usability release thresholds are met by these rows; "
            "report the configuration and raw sheet with the result."
        )

    return {
        "participant_count": count,
        "sample_status": sample_status,
        "mean_sus": round(mean, 2),
        "median_sus": round(median, 2),
        "sd_sus": round(stdev, 2) if stdev is not None else None,
        "min_sus": min(scores),
        "max_sus": max(scores),
        "sus_score_0_100": round(mean, 2),
        "flow_completion_count": sum(flow),
        "flow_completion_sample_size": len(flow),
        "flow_completion_rate": round(completion_rate, 4)
        if completion_rate is not None
        else None,
        "flow_completion_percent": round(completion_rate * 100, 1)
        if completion_rate is not None
        else None,
        "duration_sample_size": len(durations),
        "mean_duration_minutes": round(mean_duration, 2)
        if mean_duration is not None
        else None,
        "release_gates": {
            "participants_5_to_8": sample_ok,
            "flow_completion_at_least_90_percent": completion_ok,
            "mean_sus_at_least_80": sus_ok,
            "all_met": all_met,
            "note": note,
        },
    }


def _md_cell(value):
    return str(value).replace("|", "\\|")


def print_markdown(rows, summary, source):
    print(f"Source: `{source}`")
    print(f"Participants: {summary['participant_count']}")
    print()
    print("| Participant | SUS (0-100) | Flow completed | Duration (min) |")
    print("| --- | ---: | :---: | ---: |")
    for row in rows:
        if row["flow_completed"] is None:
            completed = "-"
        elif row["flow_completed"]:
            completed = "yes"
        else:
            completed = "no"
        duration = (
            f"{row['duration_minutes']:.1f}"
            if row["duration_minutes"] is not None
            else "-"
        )
        print(
            f"| {_md_cell(row['participant_id'])} | {row['sus']:.1f} | "
            f"{completed} | {duration} |"
        )
    print()
    print(f"Mean SUS: **{summary['mean_sus']:.2f}** / 100 (target >= {SUS_TARGET:.0f})")
    print(f"Median SUS: {summary['median_sus']:.2f}")
    if summary["sd_sus"] is None:
        print("SD (sample): n/a (single participant)")
    else:
        print(f"SD (sample): {summary['sd_sus']:.2f}")
    if summary["flow_completion_rate"] is None:
        print("Flow completion: not recorded")
    else:
        print(
            "Flow completion: "
            f"{summary['flow_completion_count']}/{summary['flow_completion_sample_size']} "
            f"({summary['flow_completion_percent']:.1f}%, target >= 90%)"
        )
    if summary["mean_duration_minutes"] is None:
        print("Mean duration: not recorded")
    else:
        print(
            f"Mean duration: {summary['mean_duration_minutes']:.2f} min "
            f"(n={summary['duration_sample_size']})"
        )
    gates = summary["release_gates"]
    verdict = "MET" if gates["all_met"] else "NOT MET"
    print(f"Release gate: **{verdict}** - {gates['note']}")


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Score the standard 10-item SUS and flow completion from real "
            "participant rows, refusing empty input."
        )
    )
    parser.add_argument("input", type=Path, help="CSV or JSONL sheet of participants")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write metrics JSON here, e.g. evaluation/results/usability_metrics.json",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        rows = read_rows(args.input)
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 2
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(
            "error: no participant rows found in "
            f"{args.input}; refusing to write a metrics file because a zero or "
            "placeholder SUS score would be fabricated evidence.",
            file=sys.stderr,
        )
        if args.out is not None and args.out.exists():
            print(
                f"warning: existing {args.out} was left unchanged; verify it is not "
                "stale before reporting it.",
                file=sys.stderr,
            )
        return 2

    summary = summarise(rows)
    print_markdown(rows, summary, args.input)

    if args.out is not None:
        payload = {
            "status": "measured",
            "source": str(args.input),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "instrument": (
                "System Usability Scale (Brooke, 1996): 10 items, 5-point Likert, "
                "standard alternating item order"
            ),
            "scoring": (
                "(sum(item-1) for Q1, Q3, Q5, Q7, Q9 + sum(5-item) for "
                "Q2, Q4, Q6, Q8, Q10) * 2.5"
            ),
            "thresholds": {
                "participants_min": PARTICIPANTS_MIN,
                "participants_max": PARTICIPANTS_MAX,
                "flow_completion": COMPLETION_TARGET,
                "mean_sus": SUS_TARGET,
            },
            "summary": summary,
            "participants": rows,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
