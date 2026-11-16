"""Latency benchmark checks. No real model service is contacted."""

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from scripts import bench_latency


def test_percentile_matches_known_samples():
    samples = list(range(1, 11))
    assert bench_latency.percentile(samples, 50) == 5.5
    assert bench_latency.percentile(samples, 95) == pytest.approx(9.55)
    assert bench_latency.percentile(samples, 0) == 1
    assert bench_latency.percentile(samples, 100) == 10
    assert bench_latency.percentile([7.0], 95) == 7.0
    with pytest.raises(ValueError):
        bench_latency.percentile([], 50)
    with pytest.raises(ValueError):
        bench_latency.percentile([1.0], 101)


def test_summarize_reports_p50_p95_and_max():
    summary = bench_latency.summarize([0.4, 0.2, 0.3, 0.1])
    assert summary["count"] == 4
    assert summary["p50_seconds"] == pytest.approx(0.25)
    assert summary["p95_seconds"] == pytest.approx(0.385)
    assert summary["max_seconds"] == 0.4
    assert summary["samples_seconds"] == [0.4, 0.2, 0.3, 0.1]


class _SSEHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: ClassVar[list[dict]] = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(json.loads(body))
        events = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": '{"interviewer_text":'}}]},
            {"choices": [{"delta": {"content": '"Hello"}'}}]},
        ]
        payload = b""
        for event in events:
            payload += f"data: {json.dumps(event)}\n\n".encode()
        payload += b"data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        # Send the role-only event first so first-token timing must skip empty deltas.
        self.wfile.write(b"data: " + json.dumps(events[0]).encode() + b"\n\n")
        self.wfile.flush()
        for event in events[1:]:
            self.wfile.write(b"data: " + json.dumps(event).encode() + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def sse_server():
    _SSEHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SSEHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_llm_probe_times_first_non_empty_chunk(sse_server):
    result = bench_latency.run_llm_probe(
        base_url=sse_server,
        model="fake-model",
        repeats=2,
        warmup=0,
        timeout=10,
    )
    first = result["first_token_seconds"]
    total = result["total_seconds"]
    assert result["source"] == "tool_measured"
    assert result["endpoint"].endswith("/chat/completions")
    assert first["count"] == total["count"] == 2
    assert all(value > 0 for value in first["samples_seconds"])
    assert all(value > 0 for value in total["samples_seconds"])
    assert first["p50_seconds"] <= first["p95_seconds"] <= first["max_seconds"]
    assert total["max_seconds"] >= first["max_seconds"]
    sent = _SSEHandler.requests[-1]
    assert sent["stream"] is True
    assert [message["role"] for message in sent["messages"]] == ["system", "user"]


def test_probe_run_writes_tool_measured_results(tmp_path, sse_server):
    output = tmp_path / "latency.json"
    code = bench_latency.main(
        [
            "--probe",
            "llm",
            "--llm-url",
            sse_server,
            "--repeats",
            "2",
            "--warmup",
            "1",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    data = json.loads(output.read_text())
    probe = data["probes"]["llm_first_token"]
    assert probe["source"] == "tool_measured"
    assert probe["warmup_discarded"] == 1
    assert probe["first_token_seconds"]["count"] == 2
    assert probe["total_seconds"]["count"] == 2
    assert probe["machine"]["hostname"] == data["machine"]["hostname"]
    assert data["manual"] == []
    assert data["gate_status"]["speech_end_to_first_audio"]["status"] == "not_measured"
    assert data["gate_status"]["llm_p95_first_token"]["status"] in {"pass", "fail"}


def test_unreachable_service_exits_nonzero_and_writes_nothing(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    output = tmp_path / "latency.json"
    result = subprocess.run(
        [
            sys.executable,
            str(bench_latency.ROOT / "scripts" / "bench_latency.py"),
            "--probe",
            "llm",
            "--llm-url",
            f"http://127.0.0.1:{port}/v1",
            "--repeats",
            "1",
            "--warmup",
            "0",
            "--timeout",
            "2",
            "--output",
            str(output),
        ],
        check=False,
        cwd=bench_latency.ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert "ERROR:" in result.stderr
    assert "not reachable" in result.stderr
    assert "No measurements were written" in result.stderr
    assert not output.exists()


def test_record_refuses_to_fill_machine_measured_fields(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("record mode must not run network probes")

    monkeypatch.setattr(bench_latency, "run_llm_probe", forbidden)
    monkeypatch.setattr(bench_latency, "run_embedding_probe", forbidden)
    monkeypatch.setattr(bench_latency, "run_reranker_probe", forbidden)
    output = tmp_path / "latency.json"
    output.write_text(
        json.dumps(
            {
                "suite": "latency",
                "probes": {
                    "llm_first_token": {
                        "source": "tool_measured",
                        "first_token_seconds": {"p95_seconds": 3.25},
                    }
                },
                "manual": [],
            }
        )
    )
    code = bench_latency.main(
        [
            "--record",
            "--avatar-fps",
            "57.5",
            "--speech-end-to-first-audio",
            "5.4",
            "--output",
            str(output),
            "--operator",
            "tester",
        ]
    )
    assert code == 0
    data = json.loads(output.read_text())
    assert data["probes"]["llm_first_token"]["first_token_seconds"]["p95_seconds"] == 3.25
    assert data["probes"]["llm_first_token"]["source"] == "tool_measured"
    entry = data["manual"][-1]
    assert entry["source"] == "operator_entered"
    assert entry["avatar_fps"] == 57.5
    assert entry["speech_end_to_first_audio_seconds"] == 5.4
    assert entry["operator"] == "tester"
    assert entry["machine"]["hostname"]
    assert "p95_seconds" not in json.dumps(entry)
    assert data["updated_at"].endswith("Z")
    assert data["field_sources"] == {
        "probes": "tool_measured",
        "manual": "operator_entered",
    }
    assert data["gate_status"]["llm_p95_first_token"]["status"] == "pass"
    assert data["gate_status"]["avatar_fps"]["status"] == "pass"
    assert data["gate_status"]["speech_end_to_first_audio"]["status"] == "pass"


def test_record_on_fresh_file_leaves_probe_fields_unmeasured(tmp_path):
    output = tmp_path / "latency.json"
    code = bench_latency.main(
        [
            "--record",
            "--avatar-fps",
            "45",
            "--speech-end-to-first-audio",
            "7.5",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    data = json.loads(output.read_text())
    assert "probes" not in data
    assert data["gate_status"]["llm_p95_first_token"]["status"] == "not_measured"
    assert data["gate_status"]["avatar_fps"]["status"] == "pass"
    assert data["manual"][0]["source"] == "operator_entered"


@pytest.mark.parametrize(
    "extra",
    [
        ["--avatar-fps", "60"],
        ["--speech-end-to-first-audio", "5"],
        ["--avatar-fps", "0", "--speech-end-to-first-audio", "5"],
        ["--avatar-fps", "60", "--speech-end-to-first-audio", "-1"],
        ["--avatar-fps", "nan", "--speech-end-to-first-audio", "5"],
    ],
)
def test_record_rejects_missing_or_implausible_values(tmp_path, extra):
    output = tmp_path / "latency.json"
    code = bench_latency.main(["--record", *extra, "--output", str(output)])
    assert code == 2
    assert not output.exists()
