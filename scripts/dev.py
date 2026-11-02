"""Local process supervisor. Only terminate processes started by this invocation."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
ENV = os.environ.copy()
ENV["PATH"] = os.pathsep.join(
    [str(RUNTIME / "node/bin"), str(RUNTIME / "bin/fallback"), ENV.get("PATH", "")]
)


def run(args, **kwargs):
    return subprocess.run(
        [str(a) for a in args], cwd=ROOT, env=ENV, check=True, **kwargs
    )


def python():
    local = ROOT / ".venv/bin/python"
    if local.exists():
        return str(local)
    bundled = RUNTIME / "python/bin/python3"
    return shutil.which("python3.12") or (
        str(bundled) if bundled.exists() else sys.executable
    )


def pnpm():
    binary = shutil.which("pnpm", path=ENV["PATH"])
    if not binary:
        raise SystemExit("Install Node 22+ and pnpm 11.25+, then retry. See README.md.")
    return binary


def load_env():
    if (ROOT / ".env").exists():
        from dotenv import dotenv_values

        for key, value in dotenv_values(ROOT / ".env").items():
            if value is not None:
                ENV.setdefault(key, value)


def bootstrap():
    if not (ROOT / ".venv").exists():
        run([python(), "-m", "venv", ".venv"])
    run([python(), "-m", "pip", "install", "-r", "requirements.lock"])
    run([python(), "-m", "pip", "install", "--no-deps", "-e", "backend"])
    run([pnpm(), "--dir", "frontend", "install", "--frozen-lockfile"])
    run([pnpm(), "--dir", "e2e", "install", "--frozen-lockfile"])
    if sys.platform == "darwin" and shutil.which("brew"):
        missing = [
            name
            for binary, name in [
                ("llama-server", "llama.cpp"),
                ("whisper-server", "whisper-cpp"),
                ("ffmpeg", "ffmpeg"),
            ]
            if not shutil.which(binary)
        ]
        if missing:
            run(["brew", "install", *missing])
    run([python(), "scripts/download_models.py"])
    print(
        "Bootstrap complete. make dev starts the app; make demo serves a production build."
    )


def available(url):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def serve(mode):
    load_env()
    if mode == "demo":
        run([pnpm(), "--dir", "frontend", "build"])
    children = []
    logs = []
    log_dir = ROOT / "artifacts/run"
    log_dir.mkdir(parents=True, exist_ok=True)

    def start(name, command, log=False):
        output = None
        if log:
            output = (log_dir / f"{name}.log").open("a")
            logs.append(output)
        child = subprocess.Popen(
            [str(a) for a in command],
            cwd=ROOT,
            env=ENV,
            stdout=output,
            stderr=subprocess.STDOUT if log else None,
        )
        children.append(child)
        return child

    def stop(*_):
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        for log in logs:
            log.close()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        model_path = ROOT / ENV.get(
            "MODEL_PATH", "models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        )
        provider = ENV.setdefault(
            "MODEL_PROVIDER", "llama" if model_path.exists() else "demo"
        )
        if provider == "llama" and not available("http://127.0.0.1:8080/health"):
            if not model_path.exists():
                raise SystemExit(
                    "MODEL_PROVIDER=llama requires MODEL_PATH. Run make bootstrap or use MODEL_PROVIDER=demo."
                )
            start(
                "llama",
                [
                    "llama-server",
                    "-m",
                    model_path,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8080",
                    "-c",
                    "8192",
                    "-ngl",
                    "99",
                    "--jinja",
                    "--parallel",
                    "1",
                ],
                log=True,
            )
        whisper_path = ROOT / ENV.get(
            "WHISPER_MODEL_PATH", "models/ggml-large-v3-turbo-q5_0.bin"
        )
        if whisper_path.exists() and not available("http://127.0.0.1:8081/"):
            start(
                "whisper",
                [
                    "whisper-server",
                    "-m",
                    whisper_path,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8081",
                    "--convert",
                ],
                log=True,
            )
        embedding_path = ROOT / "models/Qwen3-Embedding-0.6B-Q8_0.gguf"
        if embedding_path.exists():
            ENV.setdefault("EMBEDDING_BASE_URL", "http://127.0.0.1:8082/v1")
            if not available("http://127.0.0.1:8082/health"):
                start(
                    "embedding",
                    [
                        "llama-server",
                        "-m",
                        embedding_path,
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8082",
                        "--embedding",
                        "--pooling",
                        "last",
                        "-c",
                        "4096",
                        "-ngl",
                        "99",
                    ],
                    log=True,
                )
        reranker_path = ROOT / "models/Qwen3-Reranker-0.6B-Q8_0.gguf"
        if reranker_path.exists():
            ENV.setdefault("RERANKER_BASE_URL", "http://127.0.0.1:8083/v1")
            if not available("http://127.0.0.1:8083/health"):
                start(
                    "reranker",
                    [
                        "llama-server",
                        "-m",
                        reranker_path,
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8083",
                        "--embedding",
                        "--reranking",
                        "--pooling",
                        "rank",
                        "-c",
                        "4096",
                        "-ngl",
                        "99",
                    ],
                    log=True,
                )
        if "DATABASE_URL" not in ENV and ENV.get("VOXPREP_SQLITE") != "1":
            docker = shutil.which("docker")
            if (
                docker
                and subprocess.run(
                    [docker, "info"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            ):
                run(["docker", "compose", "up", "-d", "--wait", "db"])
                ENV["DATABASE_URL"] = (
                    "postgresql+psycopg://voxprep:local-development-only@127.0.0.1:54329/voxprep"
                )
            else:
                print(
                    "Docker unavailable: using the documented SQLite development fallback.",
                    flush=True,
                )
        run([python(), "-m", "scripts.migrate"])
        ready_urls = {}
        if provider == "llama":
            ready_urls["llama"] = (
                ENV.get("LLAMA_BASE_URL", "http://127.0.0.1:8080/v1").removesuffix(
                    "/v1"
                )
                + "/health"
            )
        for name, key in [
            ("embedding", "EMBEDDING_BASE_URL"),
            ("reranker", "RERANKER_BASE_URL"),
        ]:
            if ENV.get(key):
                ready_urls[name] = ENV[key].removesuffix("/v1") + "/health"
        if ready_urls:
            print(
                "Waiting for configured native services. Logs: artifacts/run/",
                flush=True,
            )
            for _ in range(120):
                ready_urls = {
                    name: url for name, url in ready_urls.items() if not available(url)
                }
                if not ready_urls:
                    break
                if any(p.poll() is not None for p in children):
                    raise RuntimeError(
                        "A native service exited. See artifacts/run/*.log."
                    )
                time.sleep(1)
            if ready_urls:
                print(
                    "Unavailable services will use disclosed fallbacks: "
                    + ", ".join(ready_urls),
                    flush=True,
                )
        command = [
            python(),
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
        if mode == "dev":
            command += ["--reload", "--reload-dir", "backend"]
        start("api", command)
        if mode == "dev":
            start(
                "frontend", [pnpm(), "--dir", "frontend", "dev", "--host", "127.0.0.1"]
            )
        print(
            f"VoxPrep HK: http://localhost:{5173 if mode == 'dev' else 8000} (provider: {provider})",
            flush=True,
        )
        while all(p.poll() is None for p in children):
            time.sleep(1)
        raise RuntimeError("A service exited unexpectedly.")
    except KeyboardInterrupt:
        pass
    finally:
        stop()


def main():
    local_python = ROOT / ".venv/bin/python"
    if local_python.exists() and Path(sys.prefix) != ROOT / ".venv":
        os.execv(str(local_python), [str(local_python), __file__, *sys.argv[1:]])
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["bootstrap", "dev", "demo", "test", "build", "eval"]
    )
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
    elif args.command in ["dev", "demo"]:
        serve(args.command)
    elif args.command == "build":
        run([pnpm(), "--dir", "frontend", "build"])
    elif args.command == "eval":
        run([python(), "-m", "evaluation.run", "smoke"])
        run([python(), "-m", "evaluation.collect"])
        run(
            [
                python(),
                "-m",
                "evaluation.run",
                "retrieval",
                "--input",
                "evaluation/results/retrieval_observations.jsonl",
                "--diagnostic",
            ]
        )
    elif args.command == "test":
        run([python(), "-m", "ruff", "check", "backend", "ml", "evaluation", "scripts"])
        run(
            [
                python(),
                "-m",
                "pytest",
                "backend/tests",
                "ml/tests",
                "evaluation/tests",
                "scripts/tests",
                "-q",
            ]
        )
        run([pnpm(), "--dir", "frontend", "test"])
        run([pnpm(), "--dir", "frontend", "lint"])
        run([pnpm(), "--dir", "frontend", "build"])
        run([pnpm(), "--dir", "e2e", "test"])


if __name__ == "__main__":
    main()
