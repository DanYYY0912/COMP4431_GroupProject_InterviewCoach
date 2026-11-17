# Latency benchmark

This is the evidence procedure for the release gate:

| Metric | Gate | Measured by |
| --- | --- | --- |
| LLM p95 first token | <= 4 s | `scripts/bench_latency.py` (tool) |
| Speech end to first audio | <= 8 s | operator, browser screen recording |
| Avatar frame rate | >= 30 FPS | operator, Chrome DevTools |

Run everything on the presentation Mac, with the same build and the same local
services that will be used in the presentation. Numbers from a different machine
or a different model are not evidence for this gate.

`scripts/bench_latency.py` only reports real responses from real services. If a
service is not running it prints the unreachable endpoint and exits with code 2
**without writing a file**. It never estimates a missing number, and `--record`
never fills in a tool-measured field from typed input.

## 1. Start the services

From the repository root:

```bash
make dev
```

Confirm each endpoint answers before benchmarking (a 200 or a JSON error body is
fine here; connection refused is not):

```bash
curl -sS http://127.0.0.1:8080/v1/models  | head -c 200; echo
curl -sS http://127.0.0.1:8082/v1/models  | head -c 200; echo
curl -sS http://127.0.0.1:8083/v1/models  | head -c 200; echo
```

The benchmark reads `LLAMA_BASE_URL`, `EMBEDDING_BASE_URL`, `RERANKER_BASE_URL`
and the model names from the backend settings (`.env`), falling back to the
documented local defaults (`http://127.0.0.1:8082/v1` and
`http://127.0.0.1:8083/v1`). Override with `--llm-url`, `--embedding-url`,
`--reranker-url`, `--model`, `--embedding-model`, `--reranker-model` if needed.
The same values the app uses must be used here.

## 2. Measure the services

Warm-up rule: discard the first call of every probe (`--warmup 1`). The first
call loads weights/pages and is not representative. Measure **N = 10** calls
after warm-up. Do not benchmark while a build, download or video call is running.

```bash
.venv/bin/python scripts/bench_latency.py \
  --probe llm --probe embeddings --probe rerank \
  --repeats 10 --warmup 1
```

Expected output shape (values below are placeholders, not results):

```text
llm_first_token first_token_seconds: p50=<s>s p95=<s>s max=<s>s (n=10)
llm_first_token total_seconds: p50=<s>s p95=<s>s max=<s>s (n=10)
embeddings seconds: p50=<s>s p95=<s>s max=<s>s (n=10)
rerank seconds: p50=<s>s p95=<s>s max=<s>s (n=10)
gate llm_p95_first_token: <pass|fail> (<value> vs <= 4.0)
gate speech_end_to_first_audio: not measured
gate avatar_fps: not measured
Wrote evaluation/results/latency_metrics.json
```

The LLM probe streams the runtime coach request built by
`backend/app/coach.py`'s `question_messages`/`grounded_schema` (same system
prompt, JSON-schema constrained decode, `max_tokens=480`) and adds
`stream: true`, which the app does not need but the gate does. "First token" is
the first non-empty `delta.content`; total time is measured to the end of the
stream.

Run a single probe when only one is relevant, for example:

```bash
.venv/bin/python scripts/bench_latency.py --probe llm --repeats 10 --warmup 1
```

Exit codes: `0` all requested probes measured; `2` a service was unreachable,
returned an unexpected shape, or `--record` input was invalid. Nothing is
written on failure.

If a probe is measured in a later run, its entry is merged into the existing
JSON and keeps its own `measured_at` timestamp. Untouched probe entries keep
their earlier timestamps; re-run all three on the final machine/configuration so
every number in the file belongs to the same setup.

## 3. Measure avatar FPS in Chrome DevTools

Do this during a real, representative session (same window size, same browser
profile, no devtools throttling) and while the avatar is actually animating
during a spoken answer.

1. Open the app in Chrome, start a session, and reach the avatar/interviewer view.
2. Open DevTools: `Cmd + Option + I`.
3. Open the Rendering panel: DevTools menu (three dots) > **More tools** >
   **Rendering**.
4. Tick **Frame Rendering Stats**. A FPS meter appears in the top-left of the
   page.
5. Let the app settle, then have the avatar speak for ~30 s while you watch the
   meter. Ignore the first second (layout/compile spike).
6. Record the **sustained** FPS, not the peak. Repeat three times in fresh
   sessions and keep the **lowest sustained** value. That number goes into
   `--avatar-fps`.

If the meter is unreadable at presentation resolution, resize the window once
and re-check; do not switch to another machine's numbers.

## 4. Measure speech end to first audio

This is end-to-end: release of the user's speech through STT, backend, model and
the first audio sample the room hears. Measure the total, not just one hop.

1. Record the screen with system audio. QuickTime Player > **File** > **New
   Screen Recording** > Options: select the microphone that hears the speakers
   (or a loopback device), then record a full answer-and-response exchange.
   Record at the display's native rate; note it (usually 60 fps). `screencapture
   -v` is an equivalent CLI recorder. If you use `ffmpeg`, record with a known
   constant frame rate, e.g.
   `ffmpeg -f avfoundation -framerate 60 -i "1:0" -c:v libx264 -r 60 out.mov`.
2. Open the recording in QuickTime and step frame by frame with the left/right
   arrow keys (pause first). Enable the timecode display (`View` > `Show
   Timecode`, or `Cmd + J`) if needed.
3. Find **frame A**: the last frame where the user's speech is still audible
   (waveform/mouth movement ends). Find **frame B**: the first frame where the
   coach's audio starts (waveform appears / first syllable is audible).
4. Count the frames between A and B and divide by the capture frame rate:
   `seconds = (B - A) / fps`. At 60 fps, 330 frames is 5.5 s.
5. Repeat three times with different answers and take the **worst (largest)**
   value. That number goes into `--speech-end-to-first-audio`.

Do not measure from the tap on "submit" to audio: the gate is speech-end to
first audio, so start the clock when the user stops talking.

## 5. Record the manual numbers

Run this on the presentation Mac, with the values you actually measured:

```bash
.venv/bin/python scripts/bench_latency.py --record \
  --avatar-fps <FPS_YOU_MEASURED> \
  --speech-end-to-first-audio <SECONDS_YOU_MEASURED> \
  --operator "<your name>" \
  --notes "presentation Mac, <build/commit>, <date>"
```

The angle-bracket placeholders are deliberately not valid numbers; the command
fails until you replace them with measured values. The tool refuses zero,
negative and non-finite values.

What lands in `evaluation/results/latency_metrics.json` (default; change with
`--output`):

```json
{
  "suite": "latency",
  "schema_version": 1,
  "updated_at": "2026-11-16T12:34:56Z",
  "machine": {"hostname": "...", "platform": "...", "memory_gib": 0.0},
  "field_sources": {
    "probes": "tool_measured",
    "manual": "operator_entered"
  },
  "thresholds": {"p95_first_token_seconds": 4.0,
                 "speech_end_to_first_audio_seconds": 8.0,
                 "avatar_fps": 30.0},
  "probes": {
    "llm_first_token": {
      "source": "tool_measured",
      "measured_at": "2026-11-16T12:30:00Z",
      "machine": {"hostname": "...", "platform": "..."},
      "first_token_seconds": {"count": 10, "p50_seconds": 0.0,
                              "p95_seconds": 0.0, "max_seconds": 0.0,
                              "samples_seconds": [0.0]},
      "total_seconds": {"...": "..."},
      "warmup_total_seconds": [0.0]
    },
    "embeddings": {"...": "..."},
    "rerank": {"...": "..."}
  },
  "manual": [
    {
      "source": "operator_entered",
      "recorded_at": "2026-11-16T12:34:56Z",
      "avatar_fps": 0.0,
      "speech_end_to_first_audio_seconds": 0.0,
      "method": {"...": "..."},
      "operator": "...",
      "notes": "...",
      "machine": {"...": "..."}
    }
  ],
  "gate_status": {
    "llm_p95_first_token": {"measured": 0.0, "threshold": 4.0,
                            "comparison": "<=", "status": "pass"},
    "speech_end_to_first_audio": {"...": "..."},
    "avatar_fps": {"...": "..."}
  }
}
```

`source` is `tool_measured` only for values produced by this tool from real
service responses; everything typed by a human is `operator_entered` and lives
under `manual` with the machine description and UTC timestamp. Each `--record`
run appends one `manual` entry, so you keep the history. `gate_status` uses the
latest manual entry and the most recent tool-measured LLM p95; missing values are
`not_measured`, never `pass`.

## 6. Check before presenting

- [ ] `gate_status` shows `pass` for all three entries on the final presentation
      Mac with the final build and models.
- [ ] `probes.llm_first_token`, `probes.embeddings`, `probes.rerank` all have the
      same `measured_at` date/config.
- [ ] `manual`'s last entry has the same `machine.hostname` as `machine.hostname`.
- [ ] Keep `evaluation/results/latency_metrics.json` with the presentation
      evidence; do not edit it by hand.
