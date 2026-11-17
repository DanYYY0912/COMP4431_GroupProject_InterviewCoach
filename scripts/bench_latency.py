"""Measure VoxPrep HK local service latency and record manual browser timings.

Three machine-measured probes (all optional with ``--probe``):

1. LLM first token: streams the exact coach request shape from
   ``backend/app/coach.py`` to ``{LLM_URL}/chat/completions`` and reports time to
   the first non-empty content chunk plus total stream time.
2. Embeddings: times one ``{EMBEDDING_URL}/embeddings`` call shaped like
   ``backend/app/retrieval.py``.
3. Reranker: times one ``{RERANKER_URL}/rerank`` call shaped like retrieval.

A probe whose service is not running fails loudly and writes nothing: this tool
never substitutes or estimates a latency number.

``--record`` stores the operator's browser measurements (avatar FPS and
speech-end-to-first-audio) in the same JSON file, labelled
``"source": "operator_entered"`` so they can never be mistaken for tool output.

See ``docs/LATENCY.md`` for the presentation-machine procedure.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation" / "results" / "latency_metrics.json"
DEFAULT_EMBEDDING_URL = "http://127.0.0.1:8082/v1"
DEFAULT_RERANKER_URL = "http://127.0.0.1:8083/v1"
THRESHOLDS = {
    "p95_first_token_seconds": 4.0,
    "speech_end_to_first_audio_seconds": 8.0,
    "avatar_fps": 30.0,
}
SERVICE_HINTS = {
    "LLM": "start llama.cpp on port 8080 (make dev)",
    "Embedding": "start the embedding server on port 8082 and set EMBEDDING_BASE_URL",
    "Reranker": "start the reranker server on port 8083 and set RERANKER_BASE_URL",
}
FALLBACK_SOURCE_TEXT = (
    "Situation: describe the context, users and constraint that made the example "
    "meaningful. Task: explain your own responsibility and what success would mean. "
    "Action: state the steps you took and why. Result: give the measured outcome."
)


class BenchError(RuntimeError):
    """A probe could not produce a real measurement."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def percentile(samples: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile (the numpy default) of the samples."""
    values = sorted(samples)
    if not values:
        raise ValueError("percentile requires at least one sample")
    if not 0 <= q <= 100:
        raise ValueError("percentile must be between 0 and 100")
    position = (len(values) - 1) * q / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] + (values[upper] - values[lower]) * weight


def summarize(samples: Sequence[float]) -> dict[str, Any]:
    """Distribution summary; samples are kept so the record stays auditable."""
    if not samples:
        raise ValueError("summarize requires at least one sample")
    return {
        "count": len(samples),
        "p50_seconds": round(percentile(samples, 50), 4),
        "p95_seconds": round(percentile(samples, 95), 4),
        "max_seconds": round(max(samples), 4),
        "samples_seconds": [round(value, 4) for value in samples],
    }


def machine_description() -> dict[str, Any]:
    """Describe the measuring machine so a number is never machine-less."""
    memory_gib = None
    try:
        memory_gib = round(
            os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1
        )
    except (AttributeError, OSError, ValueError):
        pass
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or _mac_cpu_brand(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory_gib": memory_gib,
    }


def _mac_cpu_brand() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _unreachable(service: str, url: str, exc: Exception) -> BenchError:
    hint = SERVICE_HINTS.get(service, "start the local service")
    return BenchError(
        f"{service} endpoint {url} is not reachable ({type(exc).__name__}: {exc}). "
        f"To measure it, {hint} and retry."
    )


def _post_json(
    client: httpx.Client, service: str, url: str, payload: dict
) -> dict[str, Any]:
    try:
        response = client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise _unreachable(service, url, exc) from exc
    if response.status_code != 200:
        body = response.text[:300].replace("\n", " ")
        raise BenchError(
            f"{service} endpoint {url} returned HTTP {response.status_code}: {body}. "
            "Check the URL/model name with --help; no latency was measured."
        )
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise BenchError(
            f"{service} endpoint {url} did not return JSON: {response.text[:200]!r}"
        ) from exc


def _bench_source_text() -> str:
    path = ROOT / "knowledge" / "star-rubric.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK_SOURCE_TEXT
    return text[:480] or FALLBACK_SOURCE_TEXT


def build_llm_request(model: str) -> dict[str, Any]:
    """Reuse coach.py's runtime request shape, adding stream=True for TTFT."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from backend.app.coach import ModelCoachTurn, grounded_schema, question_messages
    from backend.app.ingestion import COMPETENCY_TERMS
    from backend.app.schemas import Citation

    competencies = sorted(COMPETENCY_TERMS)[:5]
    sources = [
        Citation(chunk_id="bench-0001", source="bench", text=_bench_source_text())
    ]
    return {
        "model": model,
        "messages": question_messages(
            competencies, "en-HK", "standard", 0, None, sources
        ),
        "temperature": 0.3,
        "max_tokens": 480,
        "stream": True,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "CoachTurn",
                "strict": True,
                "schema": grounded_schema(ModelCoachTurn, competencies, sources),
            },
        },
    }


def _stream_once(
    client: httpx.Client, url: str, payload: dict, timeout: float
) -> tuple[float, float]:
    """Stream one completion; return (first non-empty content, total) seconds."""
    start = time.perf_counter()
    first_token: float | None = None
    characters = 0
    try:
        with client.stream("POST", url, json=payload, timeout=timeout) as response:
            if response.status_code != 200:
                body = response.read()[:300].decode("utf-8", "replace")
                raise BenchError(
                    f"LLM endpoint {url} returned HTTP {response.status_code}: "
                    f"{body.replace(chr(10), ' ')}. No latency was measured."
                )
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise BenchError(
                        f"LLM endpoint {url} sent a non-JSON stream chunk: {data[:120]!r}"
                    ) from exc
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                content = (choices[0].get("delta") or {}).get("content") or ""
                if content:
                    if first_token is None:
                        first_token = time.perf_counter() - start
                    characters += len(content)
    except httpx.RequestError as exc:
        raise _unreachable("LLM", url, exc) from exc
    total = time.perf_counter() - start
    if first_token is None:
        raise BenchError(
            f"LLM endpoint {url} completed the stream without any content "
            f"(status 200). Check that stream=true is supported."
        )
    if total < first_token or characters == 0:
        raise BenchError(
            f"LLM endpoint {url} produced an inconsistent stream; no latency recorded."
        )
    return first_token, total


def run_llm_probe(
    *,
    base_url: str,
    model: str,
    repeats: int,
    warmup: int,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = build_llm_request(model)
    firsts: list[float] = []
    totals: list[float] = []
    warmup_totals: list[float] = []
    with httpx.Client() as client:
        for index in range(warmup + repeats):
            first_token, total = _stream_once(client, url, payload, timeout)
            if index < warmup:
                warmup_totals.append(total)
                continue
            firsts.append(first_token)
            totals.append(total)
    return {
        "source": "tool_measured",
        "endpoint": url,
        "model": model,
        "repeats": repeats,
        "warmup_discarded": warmup,
        "first_token_seconds": summarize(firsts),
        "total_seconds": summarize(totals),
        "warmup_total_seconds": [round(value, 4) for value in warmup_totals],
        "measurement": "Streamed coach.py request (json_schema constrained); "
        "first non-empty delta.content to stream end.",
    }


def _validate_embeddings(
    data: dict[str, Any], expected: int, dimensions: int, url: str
) -> None:
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) != expected:
        raise BenchError(
            f"Embedding endpoint {url} returned {len(rows) if isinstance(rows, list) else 'no'} "
            f"vectors for {expected} inputs."
        )
    for row in rows:
        vector = row.get("embedding") if isinstance(row, dict) else None
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise BenchError(
                f"Embedding endpoint {url} returned an unexpected vector shape "
                f"(expected {dimensions} dimensions)."
            )
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vector):
            raise BenchError(
                f"Embedding endpoint {url} returned non-finite vector values."
            )


def run_embedding_probe(
    *,
    base_url: str,
    model: str,
    dimensions: int,
    repeats: int,
    warmup: int,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/embeddings"
    texts = [
        (
            "Instruct: Retrieve passages supporting interview coaching.\n"
            "Query: Tell me about a time you improved a slow Python API."
        )
    ]
    payload = {"model": model, "input": texts}
    samples: list[float] = []
    warmup_totals: list[float] = []
    with httpx.Client(timeout=timeout) as client:
        for index in range(warmup + repeats):
            start = time.perf_counter()
            data = _post_json(client, "Embedding", url, payload)
            elapsed = time.perf_counter() - start
            _validate_embeddings(data, len(texts), dimensions, url)
            if index < warmup:
                warmup_totals.append(elapsed)
                continue
            samples.append(elapsed)
    return {
        "source": "tool_measured",
        "endpoint": url,
        "model": model,
        "dimensions": dimensions,
        "repeats": repeats,
        "warmup_discarded": warmup,
        "seconds": summarize(samples),
        "warmup_seconds": [round(value, 4) for value in warmup_totals],
        "measurement": "One retrieval-style query embedding per call.",
    }


def run_reranker_probe(
    *,
    base_url: str,
    model: str,
    repeats: int,
    warmup: int,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/rerank"
    documents = [
        f"Practice passage {index}: describe the situation, your action and the result."
        for index in range(1, 13)
    ]
    payload = {
        "model": model,
        "query": "How did you improve a slow Python API and measure the outcome?",
        "documents": documents,
        "top_n": 4,
    }
    samples: list[float] = []
    warmup_totals: list[float] = []
    with httpx.Client(timeout=timeout) as client:
        for index in range(warmup + repeats):
            start = time.perf_counter()
            data = _post_json(client, "Reranker", url, payload)
            elapsed = time.perf_counter() - start
            results = data.get("results")
            if not isinstance(results, list) or not results:
                raise BenchError(f"Reranker endpoint {url} returned no results.")
            indices = [item.get("index") for item in results if isinstance(item, dict)]
            if (
                len(indices) != len(results)
                or len(set(indices)) != len(indices)
                or any(
                    not isinstance(i, int) or i < 0 or i >= len(documents)
                    for i in indices
                )
            ):
                raise BenchError(
                    f"Reranker endpoint {url} returned invalid document indices."
                )
            if index < warmup:
                warmup_totals.append(elapsed)
                continue
            samples.append(elapsed)
    return {
        "source": "tool_measured",
        "endpoint": url,
        "model": model,
        "repeats": repeats,
        "warmup_discarded": warmup,
        "seconds": summarize(samples),
        "warmup_seconds": [round(value, 4) for value in warmup_totals],
        "measurement": "One retrieval-style rerank of 12 passages per call.",
    }


def _verdict(value: float | None, threshold: float, higher_is_better: bool) -> dict:
    if value is None:
        return {"measured": None, "threshold": threshold, "status": "not_measured"}
    passed = value >= threshold if higher_is_better else value <= threshold
    return {
        "measured": value,
        "threshold": threshold,
        "comparison": ">=" if higher_is_better else "<=",
        "status": "pass" if passed else "fail",
    }


def gate_status(data: dict[str, Any]) -> dict[str, Any]:
    probes = data.get("probes") or {}
    llm = probes.get("llm_first_token") or {}
    p95 = (llm.get("first_token_seconds") or {}).get("p95_seconds")
    manual = data.get("manual") or []
    latest = manual[-1] if manual else {}
    return {
        "llm_p95_first_token": _verdict(
            p95, THRESHOLDS["p95_first_token_seconds"], higher_is_better=False
        ),
        "speech_end_to_first_audio": _verdict(
            latest.get("speech_end_to_first_audio_seconds"),
            THRESHOLDS["speech_end_to_first_audio_seconds"],
            higher_is_better=False,
        ),
        "avatar_fps": _verdict(
            latest.get("avatar_fps"), THRESHOLDS["avatar_fps"], higher_is_better=True
        ),
    }


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchError(
            f"Existing {path} is unreadable or not JSON ({exc}); fix or delete it first."
        ) from exc
    if not isinstance(data, dict):
        raise BenchError(f"Existing {path} does not contain a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from backend.app.config import Settings

    try:
        settings = Settings()
    except Exception as exc:  # pydantic surfaces .env mistakes as ValidationError
        raise BenchError(f"Could not load backend settings: {exc}") from exc
    return {
        "llm_url": args.llm_url or settings.llama_base_url,
        "model": args.model or settings.model_name,
        "embedding_url": args.embedding_url
        or settings.embedding_base_url
        or DEFAULT_EMBEDDING_URL,
        "embedding_model": args.embedding_model or settings.embedding_model,
        "dimensions": args.embedding_dimensions or settings.embedding_dimensions,
        "reranker_url": args.reranker_url
        or settings.reranker_base_url
        or DEFAULT_RERANKER_URL,
        "reranker_model": args.reranker_model or settings.reranker_model,
    }


def _print_summary(data: dict[str, Any]) -> None:
    for key, probe in (data.get("probes") or {}).items():
        if key == "llm_first_token":
            for label in ("first_token_seconds", "total_seconds"):
                stats = probe[label]
                print(
                    f"{key} {label}: p50={stats['p50_seconds']}s "
                    f"p95={stats['p95_seconds']}s max={stats['max_seconds']}s "
                    f"(n={stats['count']})"
                )
        else:
            stats = probe["seconds"]
            print(
                f"{key} seconds: p50={stats['p50_seconds']}s "
                f"p95={stats['p95_seconds']}s max={stats['max_seconds']}s "
                f"(n={stats['count']})"
            )
    for name, gate in data["gate_status"].items():
        if gate["status"] == "not_measured":
            print(f"gate {name}: not measured")
        else:
            print(
                f"gate {name}: {gate['status']} "
                f"({gate['measured']} vs {gate['comparison']} {gate['threshold']})"
            )


def run_and_record(args: argparse.Namespace, probes: list[str]) -> None:
    config = resolve_config(args)
    data = load_existing(args.output)
    existing_probes = data.get("probes")
    merged = existing_probes if isinstance(existing_probes, dict) else {}
    now = utc_now()
    machine = machine_description()
    measured: dict[str, Any] = {}
    if "llm" in probes:
        measured["llm_first_token"] = run_llm_probe(
            base_url=config["llm_url"],
            model=config["model"],
            repeats=args.repeats,
            warmup=args.warmup,
            timeout=args.timeout,
        )
    if "embeddings" in probes:
        measured["embeddings"] = run_embedding_probe(
            base_url=config["embedding_url"],
            model=config["embedding_model"],
            dimensions=config["dimensions"],
            repeats=args.repeats,
            warmup=args.warmup,
            timeout=args.timeout,
        )
    if "rerank" in probes:
        measured["rerank"] = run_reranker_probe(
            base_url=config["reranker_url"],
            model=config["reranker_model"],
            repeats=args.repeats,
            warmup=args.warmup,
            timeout=args.timeout,
        )
    for probe in measured.values():
        probe["measured_at"] = now
        probe["machine"] = machine

    merged.update(measured)
    data.update(
        {
            "suite": "latency",
            "schema_version": 1,
            "updated_at": now,
            "machine": machine,
            "field_sources": {
                "probes": "tool_measured",
                "manual": "operator_entered",
            },
            "thresholds": THRESHOLDS,
            "probes": merged,
        }
    )
    if not isinstance(data.get("manual"), list):
        data["manual"] = []
    data["gate_status"] = gate_status(data)
    write_json(args.output, data)
    _print_summary(data)
    print(f"Wrote {args.output}")
    print(
        "Browser measurements are not filled in: run --record with numbers you "
        "actually measured on the presentation Mac."
    )


def record_manual(args: argparse.Namespace) -> None:
    missing = [
        flag
        for flag, value in (
            ("--avatar-fps", args.avatar_fps),
            ("--speech-end-to-first-audio", args.speech_end_to_first_audio),
        )
        if value is None
    ]
    if missing:
        raise BenchError(
            "--record needs both operator-measured values: " + ", ".join(missing)
        )
    if not math.isfinite(args.avatar_fps) or not 0 < args.avatar_fps < 1000:
        raise BenchError("--avatar-fps must be a finite number between 0 and 1000.")
    if (
        not math.isfinite(args.speech_end_to_first_audio)
        or not 0 < args.speech_end_to_first_audio < 600
    ):
        raise BenchError(
            "--speech-end-to-first-audio must be a finite number of seconds "
            "between 0 and 600."
        )
    data = load_existing(args.output)
    now = utc_now()
    machine = machine_description()
    entry = {
        "source": "operator_entered",
        "recorded_at": now,
        "avatar_fps": args.avatar_fps,
        "speech_end_to_first_audio_seconds": args.speech_end_to_first_audio,
        "method": {
            "avatar_fps": "Chrome DevTools > Rendering > Frame Rendering Stats; "
            "lowest sustained FPS of three 30 s runs while the avatar speaks.",
            "speech_end_to_first_audio_seconds": "Screen recording frame counting: "
            "last user-speech frame to first coach-audio frame / capture fps.",
        },
        "operator": args.operator or None,
        "notes": args.notes,
        "machine": machine,
    }
    manual: list[dict[str, Any]] = (
        list(data["manual"]) if isinstance(data.get("manual"), list) else []
    )
    manual.append(entry)
    data.update(
        {
            "suite": "latency",
            "schema_version": 1,
            "updated_at": now,
            "machine": machine,
            "field_sources": {
                "probes": "tool_measured",
                "manual": "operator_entered",
            },
            "thresholds": THRESHOLDS,
            "manual": manual,
        }
    )
    # Record mode deliberately leaves "probes" untouched (or absent): the tool
    # never fabricates a machine-measured field from typed numbers.
    data["gate_status"] = gate_status(data)
    write_json(args.output, data)
    print(
        f"Recorded operator-measured avatar_fps={args.avatar_fps} and "
        f"speech_end_to_first_audio_seconds={args.speech_end_to_first_audio} "
        f"for {machine['hostname']} at {now}"
    )
    print(f"Wrote {args.output}")
    for name, gate in data["gate_status"].items():
        if gate["status"] == "not_measured":
            print(f"gate {name}: not measured (run the probes to measure it)")
        else:
            print(
                f"gate {name}: {gate['status']} "
                f"({gate['measured']} vs {gate['comparison']} {gate['threshold']})"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure local LLM/embedding/reranker latency, or record the operator's "
            "browser measurements. Real measurements only: an unreachable service "
            "fails with exit code 2 and writes nothing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Probes (repeat --probe to choose; default is all three):\n"
            "  llm         streamed /chat/completions, time to first content token\n"
            "              and total time; request shape reused from backend/app/coach.py\n"
            "  embeddings  one retrieval-style /embeddings call\n"
            "  rerank      one retrieval-style /rerank call over 12 passages\n"
            "\n"
            "Examples:\n"
            "  # all probes, discard one warm-up call per probe, N=10\n"
            "  python scripts/bench_latency.py --repeats 10 --warmup 1\n"
            "\n"
            "  # store typed-in browser numbers next to the machine measurements\n"
            "  python scripts/bench_latency.py --record \\\n"
            "      --avatar-fps 58 --speech-end-to-first-audio 5.2\n"
            "\n"
            "Run from the repository root with the project virtualenv. See\n"
            "docs/LATENCY.md for the presentation-machine procedure."
        ),
    )
    parser.add_argument(
        "--probe",
        action="append",
        choices=["llm", "embeddings", "rerank"],
        help="probe to run (repeatable; default: llm, embeddings, rerank)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=10,
        help="measured calls per probe, after warm-up (default: 10)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="warm-up calls per probe, discarded from the statistics (default: 1)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="per-request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--llm-url",
        default=None,
        help="LLM base URL including /v1 (default: LLAMA_BASE_URL or the app default)",
    )
    parser.add_argument("--model", default=None, help="LLM model name override")
    parser.add_argument(
        "--embedding-url",
        default=None,
        help=f"embedding base URL (default: EMBEDDING_BASE_URL or {DEFAULT_EMBEDDING_URL})",
    )
    parser.add_argument(
        "--embedding-model", default=None, help="embedding model name override"
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=None,
        help="expected vector dimensions (default: EMBEDDING_DIMENSIONS or 1024)",
    )
    parser.add_argument(
        "--reranker-url",
        default=None,
        help=f"reranker base URL (default: RERANKER_BASE_URL or {DEFAULT_RERANKER_URL})",
    )
    parser.add_argument(
        "--reranker-model", default=None, help="reranker model name override"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSON output path (default: {DEFAULT_OUTPUT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help=(
            "record operator-measured avatar FPS and speech-end-to-first-audio; "
            "never runs probes or fills tool-measured fields"
        ),
    )
    parser.add_argument(
        "--avatar-fps",
        type=float,
        default=None,
        help="operator-measured sustained avatar FPS (DevTools Frame Rendering Stats)",
    )
    parser.add_argument(
        "--speech-end-to-first-audio",
        type=float,
        default=None,
        metavar="SECONDS",
        help="operator-measured seconds from end of user speech to first coach audio",
    )
    parser.add_argument(
        "--operator",
        default="",
        help="optional name of the person who measured the browser numbers",
    )
    parser.add_argument(
        "--notes", default=None, help="optional note stored with the manual numbers"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    if args.warmup < 0:
        parser.error("--warmup must be >= 0")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")
    try:
        if args.record:
            record_manual(args)
        else:
            run_and_record(args, args.probe or ["llm", "embeddings", "rerank"])
    except BenchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            f"No measurements were written to {args.output}.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
