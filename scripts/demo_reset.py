"""Reset only fixtures whose IDs this script previously recorded, through the local API."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("VOXPREP_URL", "http://127.0.0.1:8000")
if urlparse(BASE).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Demo reset may only target localhost.")
STATE = ROOT / "artifacts/demo-fixtures.json"


def request(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(
        Request(
            BASE + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        ),
        timeout=90,
    ) as response:
        body = response.read()
        return json.loads(body) if body else None


if __name__ == "__main__":
    if STATE.exists():
        previous = json.loads(STATE.read_text())
        if previous.get("base") == BASE:
            for session_id in previous.get("session_ids", []):
                try:
                    request(f"/api/sessions/{session_id}", method="DELETE")
                except HTTPError as error:
                    if error.code != 404:
                        raise
    text = (ROOT / "data/demo-job.txt").read_text()
    profile = request(
        "/api/job-profiles",
        {"title": "Graduate Software Engineer · demonstration", "text": text},
    )
    session = request(
        "/api/sessions",
        {
            "job_profile_id": profile["id"],
            "language": "en-HK",
            "difficulty": "standard",
            "question_count": 3,
            "store_transcript": True,
        },
    )
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(
        json.dumps({"base": BASE, "session_ids": [session["id"]]}, indent=2)
    )
    print("Demonstration session ready:", BASE + "/#/interview/" + session["id"])
