"""Exercise actual local providers with synthetic answers. Not a quality benchmark."""

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"


def request(path, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    start = time.monotonic()
    with urlopen(
        Request(
            BASE + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        ),
        timeout=120,
    ) as response:
        raw = response.read()
        return (json.loads(raw) if raw else None), round(time.monotonic() - start, 3)


if __name__ == "__main__":
    results = {
        "diagnostic_only": True,
        "synthetic_inputs": True,
        "health": request("/api/health")[0],
        "sessions": [],
    }
    for language in ["en-HK", "zh-HK"]:
        profile, upload_time = request(
            "/api/job-profiles",
            {
                "title": "Synthetic local integration check",
                "text": (ROOT / "data/demo-job.txt").read_text(),
            },
        )
        session, first_time = request(
            "/api/sessions",
            {
                "job_profile_id": profile["id"],
                "language": language,
                "difficulty": "standard",
                "question_count": 3,
                "store_transcript": True,
            },
        )
        evidence = {
            "language": language,
            "profile_seconds": upload_time,
            "first_turn_seconds": first_time,
            "question_providers": [session["provider"]],
            "first_question": session["turns"][0]["question"],
            "answer_seconds": [],
        }
        try:
            answers = (
                [
                    "I helped on a project.",
                    "During our university project I was responsible for a slow Python API. I measured SQL queries, implemented an index and wrote tests. As a result response time fell by 30 percent.",
                    "I explained the test results to teammates and documented the tradeoff.",
                ]
                if language == "en-HK"
                else [
                    "我幫手做過一個專題。",
                    "喺大學專題入面，我負責改善一個緩慢嘅 Python API。我量度 SQL 查詢，加入索引，寫回歸測試。結果回應時間減少咗三成。",
                    "我同隊友解釋測試結果，並記錄各個方案嘅取捨。",
                ]
            )
            for transcript in answers:
                session, duration = request(
                    f"/api/sessions/{session['id']}/answer",
                    {
                        "turn_id": session["turns"][-1]["id"],
                        "transcript": transcript,
                        "language": language,
                        "elapsed_seconds": 35,
                        "corrected": False,
                    },
                )
                evidence["question_providers"].append(session["provider"])
                evidence["answer_seconds"].append(duration)
            report, duration = request(f"/api/sessions/{session['id']}/report")
            evidence.update(
                report_seconds=duration,
                report=report,
                completed=session["state"] == "completed",
                questions=[t["question"] for t in session["turns"]],
            )
        finally:
            request(f"/api/sessions/{session['id']}", method="DELETE")
        results["sessions"].append(evidence)
        (ROOT / "artifacts/verification/live-services.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2)
        )
        print(
            language,
            evidence["question_providers"],
            evidence["first_turn_seconds"],
            evidence["report_seconds"],
            flush=True,
        )
