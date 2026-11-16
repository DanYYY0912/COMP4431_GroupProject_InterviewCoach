"""Score the consented speech study: WER, CER, correction rate and coverage.

The study protocol is in ``docs/SPEECH_STUDY.md``: 24 clips from four
speakers, six clips each, three clean and three noisy, covering both en-HK and
zh-HK. This script never invents transcripts. It scores what humans recorded
and reviewed, and it refuses to score a sheet whose references are blank.

Metric definitions
------------------
* WER (``en-HK``) is word error rate: case-folded alphanumeric word tokens,
  ``(substitutions + deletions + insertions) / reference tokens``, computed with
  the same edit distance as ``evaluation/metrics.py``.
* CER (``zh-HK``) uses the identical edit distance over character tokens:
  alphanumeric characters only, so punctuation and whitespace are dropped and
  no traditional/simplified conversion is applied.
* Every rate is reported with its denominator. Group rates are corpus-level
  (``sum(edits) / sum(reference units)``), never the mean of per-clip rates,
  because clips differ in length. Insertions can push a rate above 1.0.
* ``correction_rate`` is the share of scored utterances that a human had to
  edit: ``(corrected or failure) / scored clips``. A recognizer failure with an
  empty hypothesis counts as an utterance needing correction (its text is
  scored as deletions, not excluded), and this matches ``evaluation/run.py``.
  ``accepted_without_edit_rate`` is the complement, ``1 - correction_rate``:
  the share of utterances a human accepted unchanged.
* An empty reference is an error, not a 0% error rate. Silence belongs in the
  separate robustness test.

Modes
-----
``--template``
    Print a blank recording sheet (JSONL, one clip per line) for four speakers
    x six clips: three clean and three noisy, both languages. Field names match
    ``evaluation/fixtures/speech_collection_template.jsonl``.
``--score SHEET``
    Score a filled sheet and print a markdown table plus the JSON report.
``--audio``
    Optional, with ``--score``: transcribe clips that have no hypothesis
    through the application's own speech path (``backend.app.speech``). It
    fails loudly when no Whisper endpoint is configured rather than writing
    guessed text.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import edit_distance, tokens

PRISTINE_TEMPLATE = ROOT / "evaluation/fixtures/speech_collection_template.jsonl"
LANGUAGES = ("en-HK", "zh-HK")
CONDITIONS = ("clean", "noisy")
SPEAKERS = 4
CLIPS_PER_SPEAKER = 6
# Six clips per speaker, alternating condition so each speaker covers both
# conditions in both languages: three clean and three noisy, three per language.
CLIP_PLAN = (
    ("en-HK", "clean"),
    ("en-HK", "noisy"),
    ("en-HK", "clean"),
    ("zh-HK", "noisy"),
    ("zh-HK", "clean"),
    ("zh-HK", "noisy"),
)
PROTOCOL_CLIPS = SPEAKERS * CLIPS_PER_SPEAKER
PROTOCOL_PER_LANGUAGE = PROTOCOL_CLIPS // 2
PROTOCOL_PER_CONDITION = PROTOCOL_CLIPS // 2

# Alternate column names accepted on input so a team member can jot a sheet
# by hand; the canonical names are the fixture's.
ALIASES = {
    "wav_path": "recording_path",
    "reference_text": "reference",
    "hypothesis_text": "hypothesis",
    "speaker": "speaker_id",
}

METRIC_DEFINITIONS = {
    "wer": "en-HK word error rate: edit_distance(word tokens) / reference words",
    "cer": "zh-HK character error rate: edit_distance(character tokens) / reference characters",
    "aggregation": "corpus-level: sum(edits) / sum(reference units), never a mean of clip rates",
    "correction_rate": "(corrected or failure) / scored clips; a failure is scored as deletions",
    "accepted_without_edit_rate": "1 - correction_rate; share a human accepted unchanged",
    "empty_reference": "rejected: silence belongs in the robustness test, not a 0% clip",
}


def canonical_row(raw):
    """Return a copy of a sheet row with alias column names mapped to canonical."""
    row = dict(raw)
    for alias, name in ALIASES.items():
        if alias in row and not str(row.get(name) or "").strip():
            row[name] = row[alias]
    return row


def clip_tokens(text, language):
    """Tokenise per language: words for English, characters for Chinese."""
    return tokens(str(text or ""), "character" if language == "zh-HK" else "word")


def score_clip(raw):
    """Score one clip; raise ValueError for a blank reference or bad labels."""
    row = canonical_row(raw)
    clip_id = str(row.get("id") or "<missing id>")
    language = row.get("language")
    if language not in LANGUAGES:
        raise ValueError(f"{clip_id}: language must be one of {', '.join(LANGUAGES)}")
    condition = row.get("condition")
    if condition not in CONDITIONS:
        raise ValueError(f"{clip_id}: condition must be one of {', '.join(CONDITIONS)}")
    reference = str(row.get("reference") or "")
    hypothesis = str(row.get("hypothesis") or "")
    reference_units = clip_tokens(reference, language)
    if not reference_units:
        raise ValueError(
            f"{clip_id}: reference transcript is empty; a silence clip belongs in the "
            "robustness test, not the accuracy study"
        )
    edits = edit_distance(reference_units, clip_tokens(hypothesis, language))
    return {
        "id": clip_id,
        "speaker_id": str(row.get("speaker_id") or ""),
        "condition": condition,
        "language": language,
        "metric": "CER" if language == "zh-HK" else "WER",
        "edits": edits,
        "reference_units": len(reference_units),
        "error_rate": round(edits / len(reference_units), 4),
        "corrected": bool(row.get("corrected")),
        "failure": row.get("failure") or None,
        "speech_end_to_audio_seconds": row.get("speech_end_to_audio_seconds"),
    }


def score_rows(rows):
    return [score_clip(row) for row in rows]


def _error_block(part):
    if not part:
        return None
    edits = sum(record["edits"] for record in part)
    units = sum(record["reference_units"] for record in part)
    return {
        "metric": part[0]["metric"],
        "clips": len(part),
        "edits": edits,
        "reference_units": units,
        "rate": round(edits / units, 4),
    }


def summarise(records):
    """Corpus-level WER/CER and correction rate for a set of scored clips."""
    if not records:
        return {
            "clips": 0,
            "wer": None,
            "cer": None,
            "correction_rate": None,
            "accepted_without_edit_rate": None,
            "failures": 0,
        }
    edited = sum(1 for record in records if record["corrected"] or record["failure"])
    return {
        "clips": len(records),
        "wer": _error_block([r for r in records if r["language"] == "en-HK"]),
        "cer": _error_block([r for r in records if r["language"] == "zh-HK"]),
        "correction_rate": round(edited / len(records), 4),
        "accepted_without_edit_rate": round(1 - edited / len(records), 4),
        "failures": sum(1 for record in records if record["failure"]),
    }


def coverage(rows):
    """Compare collected rows against the four-speaker x six-clip protocol."""
    speakers = sorted({str(row.get("speaker_id") or "") for row in rows})
    by_language = Counter(row.get("language") for row in rows)
    by_condition = Counter(row.get("condition") for row in rows)
    consent = sum(1 for row in rows if row.get("consent_recorded"))
    reviewed = sum(1 for row in rows if str(row.get("reference_reviewed_by") or "").strip())
    gaps = []
    if len(rows) != PROTOCOL_CLIPS:
        gaps.append(f"{len(rows)} of {PROTOCOL_CLIPS} clips collected")
    if len(speakers) < SPEAKERS or "" in speakers:
        gaps.append(f"{len(speakers)} of {SPEAKERS} speakers")
    for language in LANGUAGES:
        if by_language.get(language) != PROTOCOL_PER_LANGUAGE:
            gaps.append(
                f"{by_language.get(language, 0)} of {PROTOCOL_PER_LANGUAGE} "
                f"{language} clips"
            )
    for condition in CONDITIONS:
        if by_condition.get(condition) != PROTOCOL_PER_CONDITION:
            gaps.append(
                f"{by_condition.get(condition, 0)} of {PROTOCOL_PER_CONDITION} "
                f"{condition} clips"
            )
    if consent != len(rows):
        gaps.append(f"{len(rows) - consent} clips missing recorded consent")
    if reviewed != len(rows):
        gaps.append(f"{len(rows) - reviewed} clips missing a reviewed reference")
    return {
        "clips": len(rows),
        "speakers": len([speaker for speaker in speakers if speaker]),
        "by_language": {language: by_language.get(language, 0) for language in LANGUAGES},
        "by_condition": {
            condition: by_condition.get(condition, 0) for condition in CONDITIONS
        },
        "consent_recorded": consent,
        "reference_reviewed": reviewed,
        "meets_protocol": not gaps,
        "gaps": gaps,
    }


def build_report(rows, source=None, hypothesis_source=None):
    records = score_rows(rows)
    cov = coverage(rows)
    speakers = sorted({record["speaker_id"] for record in records})
    report = {
        "study": "speech_accuracy",
        "status": "measured" if cov["meets_protocol"] else "incomplete_coverage",
        "source": str(source) if source is not None else None,
        "scored_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sample_size": len(records),
        "protocol": {
            "speakers": SPEAKERS,
            "clips_per_speaker": CLIPS_PER_SPEAKER,
            "clips": PROTOCOL_CLIPS,
            "clean_and_noisy_each": PROTOCOL_PER_CONDITION,
            "languages": list(LANGUAGES),
        },
        "metric_definitions": METRIC_DEFINITIONS,
        "coverage": cov,
        "overall": summarise(records),
        "by_speaker": {
            speaker: summarise([r for r in records if r["speaker_id"] == speaker])
            for speaker in speakers
        },
        "by_condition": {
            condition: summarise([r for r in records if r["condition"] == condition])
            for condition in CONDITIONS
            if any(r["condition"] == condition for r in records)
        },
        "records": records,
        "warnings": list(cov["gaps"]),
    }
    if hypothesis_source:
        report["hypothesis_source"] = hypothesis_source
    return report


def _rate(block):
    if not block:
        return "n/a"
    return f"{block['rate'] * 100:.1f}% ({block['edits']}/{block['reference_units']})"


def _share(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_markdown(report):
    """Markdown tables for the console and for pasting into the report."""
    lines = [
        "# Speech accuracy (WER for en-HK, CER for zh-HK)",
        "",
        "Corpus-level rates: total edits / total reference units. Correction rate is the",
        "share of scored clips a human had to edit; a recognizer failure is scored as",
        "deletions and counts as needing correction.",
        "",
        "| Scope | Clips | WER en-HK | CER zh-HK | Correction rate | Accepted without edit |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    def row(scope, block):
        return (
            f"| {scope} | {block['clips']} | {_rate(block['wer'])} | "
            f"{_rate(block['cer'])} | {_share(block['correction_rate'])} | "
            f"{_share(block['accepted_without_edit_rate'])} |"
        )

    lines.append(row("Overall", report["overall"]))
    for speaker, block in report["by_speaker"].items():
        lines.append(row(f"Speaker {speaker}", block))
    for condition, block in report["by_condition"].items():
        lines.append(row(f"Condition {condition}", block))
    lines += [
        "",
        "| Clip | Speaker | Condition | Language | Metric | Edits / units | Rate | Corrected | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in report["records"]:
        failure = record["failure"] or ""
        lines.append(
            f"| {record['id']} | {record['speaker_id']} | {record['condition']} | "
            f"{record['language']} | {record['metric']} | "
            f"{record['edits']}/{record['reference_units']} | "
            f"{record['error_rate'] * 100:.1f}% | "
            f"{'yes' if record['corrected'] else 'no'} | {failure} |"
        )
    cov = report["coverage"]
    lines += [
        "",
        (
            f"Protocol coverage: {cov['clips']} clips, {cov['speakers']} speakers, "
            f"{cov['by_language']['en-HK']} en-HK / {cov['by_language']['zh-HK']} zh-HK, "
            f"{cov['by_condition']['clean']} clean / {cov['by_condition']['noisy']} noisy, "
            f"{cov['consent_recorded']}/{cov['clips']} consented, "
            f"{cov['reference_reviewed']}/{cov['clips']} references reviewed. "
            f"Status: {report['status']}."
        ),
    ]
    if cov["gaps"]:
        lines.append("")
        lines += [f"- Gap: {gap}" for gap in cov["gaps"]]
    return "\n".join(lines)


def build_template():
    """Blank sheet: four speakers x six clips, three clean and three noisy each.

    Odd-numbered speakers use the printed condition order; even-numbered speakers
    get the inverse, so no prompt is only ever recorded in one condition and the
    prompt set cannot be confounded with clean versus noisy.
    """
    rows = []
    for speaker in range(1, SPEAKERS + 1):
        speaker_id = f"participant-{speaker}"
        seen = Counter()
        for language, planned in CLIP_PLAN:
            seen[language] += 1
            condition = planned
            if speaker % 2 == 0:
                condition = "noisy" if planned == "clean" else "clean"
            rows.append(
                {
                    "condition": condition,
                    "consent_recorded": False,
                    "corrected": False,
                    "failure": None,
                    "hypothesis": "",
                    "id": f"s{speaker}-{language}-{seen[language]}",
                    "language": language,
                    "notes": "",
                    "recording_path": "",
                    "recording_sha256": "",
                    "reference": "",
                    "reference_reviewed_by": "",
                    "speaker_id": speaker_id,
                    "speech_end_to_audio_seconds": None,
                }
            )
    return rows


def require_endpoint(endpoint):
    """Return a normalised Whisper base URL or exit without guessing text."""
    url = str(endpoint or "").strip().rstrip("/")
    if not url:
        raise SystemExit(
            "No Whisper endpoint configured for --audio. Start whisper-server "
            "(README: port 8081) and pass --whisper-url http://127.0.0.1:8081 or "
            "export WHISPER_BASE_URL. No hypothesis text is invented without a "
            "recognizer."
        )
    if not url.startswith(("http://", "https://")):
        raise SystemExit(f"Whisper endpoint must be an http(s) URL, got {url!r}")
    return url


def resolve_endpoint(cli_value, env):
    return require_endpoint(cli_value or env.get("WHISPER_BASE_URL", ""))


async def fill_hypotheses(rows, endpoint, redo=False):
    """Transcribe clips with an empty hypothesis through backend.app.speech."""
    base_url = require_endpoint(endpoint)
    from fastapi import HTTPException

    from backend.app.config import Settings
    from backend.app.speech import transcribe

    settings = Settings(whisper_base_url=base_url, _env_file=None)
    filled = []
    for raw in rows:
        row = canonical_row(raw)
        if str(row.get("hypothesis") or "").strip() and not redo:
            filled.append(row)
            continue
        clip_id = str(row.get("id") or "<missing id>")
        path = Path(str(row.get("recording_path") or ""))
        if not path.is_file():
            raise SystemExit(f"{clip_id}: recording not found: {path or '<blank>'}")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        expected = str(row.get("recording_sha256") or "").strip().lower()
        if expected and expected != digest:
            raise SystemExit(
                f"{clip_id}: recording_sha256 does not match {path}; re-record or fix "
                "the sheet instead of scoring a different file"
            )
        try:
            result = await transcribe(content, path.name, row["language"], settings)
        except HTTPException as exc:
            raise SystemExit(
                f"{clip_id}: transcription failed ({exc.status_code}): {exc.detail} "
                f"Endpoint: {base_url}"
            ) from exc
        filled.append({**row, "hypothesis": result["text"], "recording_sha256": digest})
    return filled


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON ({exc.msg})") from exc
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Score the four-speaker speech study (WER/CER, correction rate).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--template", action="store_true", help="print a blank 4 x 6 recording sheet"
    )
    mode.add_argument("--score", metavar="SHEET", help="score a filled JSONL sheet")
    parser.add_argument(
        "--output",
        "--out",
        dest="output",
        metavar="PATH",
        help="write JSON report (--score) or JSONL sheet (--template)",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="transcribe clips without a hypothesis through backend.app.speech",
    )
    parser.add_argument(
        "--whisper-url",
        metavar="URL",
        help="whisper-server base URL; defaults to $WHISPER_BASE_URL",
    )
    parser.add_argument(
        "--redo", action="store_true", help="re-transcribe clips that already have a hypothesis"
    )
    parser.add_argument(
        "--sheet-out", metavar="PATH", help="write the sheet back with transcribed hypotheses"
    )
    parser.add_argument(
        "--strict", action="store_true", help="fail unless the 24-clip protocol is complete"
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite the --output file if it exists"
    )
    args = parser.parse_args(argv)

    if args.template:
        rows = build_template()
        if not args.output:
            for row in rows:
                print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            return 0
        target = Path(args.output)
        if target.resolve() == PRISTINE_TEMPLATE.resolve():
            raise SystemExit(
                f"{target} is the blank study fixture; write the recording sheet elsewhere"
            )
        if target.exists() and not args.force:
            raise SystemExit(f"{target} exists; pass --force to overwrite")
        write_jsonl(target, rows)
        print(f"Wrote {len(rows)} blank clips to {target}")
        return 0

    if args.output:
        target = Path(args.output)
        if target.exists() and not args.force:
            raise SystemExit(f"{target} exists; pass --force to overwrite")

    try:
        rows = read_jsonl(args.score)
    except OSError as exc:
        print(f"error: cannot read {args.score}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"error: no clips found in {args.score}", file=sys.stderr)
        return 2
    hypothesis_source = None
    if args.audio:
        endpoint = resolve_endpoint(args.whisper_url, os.environ)
        rows = asyncio.run(fill_hypotheses(rows, endpoint, redo=args.redo))
        hypothesis_source = "whisper.cpp via backend.app.speech"
        if args.sheet_out:
            write_jsonl(args.sheet_out, rows)
            print(f"Wrote {len(rows)} clips with hypotheses to {args.sheet_out}")

    try:
        report = build_report(
            rows, source=args.score, hypothesis_source=hypothesis_source
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.strict and report["status"] != "measured":
        print(
            "error: incomplete protocol coverage: "
            + "; ".join(report["coverage"]["gaps"]),
            file=sys.stderr,
        )
        return 2
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(render_markdown(report))
    print()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output:
        print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
