"""AI triage for generated training drafts — NOT a human review.

Purpose: rank drafts by how likely a human reviewer needs to look closely, so the
committee spends its review hours on the risky rows first. This script never writes
`reviews`, never edits the dataset, and never marks anything as approved: the only
thing that can satisfy `ml.dataset --require-review` is a record written by a human
through `ml.review`.

Two stages per row:
  1. deterministic checks with no model involved (citation IDs, verbatim evidence,
     STAR shape, competency subset, script/language sanity);
  2. a DeepSeek judgement call on the things code cannot check (does the cited
     passage actually support the coaching text, is the Cantonese natural, does the
     safety row politely refuse).

Output (default `<out>/prescreen.jsonl` + `summary.json` + `queue.txt`):
    {"id": ..., "content_sha256": ..., "local": {...}, "ai": {...}, "verdict": "ok"|"suspect"}
Rows whose content hash no longer matches are reported as stale, so triage from an
older generator run can never be mistaken for triage of the current data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
CJK = re.compile(r"[\u3400-\u9fff]")


def load_env_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    raise SystemExit("Set DEEPSEEK_API_KEY in the environment to run the pre-screen")


def parse_row(row: dict) -> tuple[dict, dict]:
    user = json.loads(row["messages"][1]["content"])
    assistant = json.loads(row["messages"][2]["content"])
    return user, assistant


def local_checks(row: dict) -> dict:
    issues: list[str] = []
    user, assistant = parse_row(row)
    sources = user.get("quoted_sources") or []
    # The runtime payload (coach.quoted_source_excerpts) keys sources by chunk_id, and
    # citation_ids reference those chunk ids. Accept a bare `id` too so older drafts work.
    source_ids = {s.get("chunk_id") or s.get("id") for s in sources}
    excerpts = user.get("quoted_answer_excerpts") or []
    blob = " ".join([*(s.get("text", "") for s in sources), *excerpts])

    task = row["task"]
    if task in ("question", "safety"):
        cited = assistant.get("citation_ids") or []
        missing = [c for c in cited if c not in source_ids]
        if missing:
            issues.append(f"citation_id_not_in_sources:{missing}")
        allowed = set(user.get("allowed_competencies") or [])
        bad = [c for c in assistant.get("targeted_competencies") or [] if c not in allowed]
        if bad:
            issues.append(f"competency_not_allowed:{bad}")
        text = assistant.get("interviewer_text") or ""
        if not text.strip():
            issues.append("empty_interviewer_text")
        if row["language"] == "zh-HK" and len(CJK.findall(text)) < 5:
            issues.append("zh-HK_text_lacks_chinese")
        if row["language"] == "en-HK" and len(CJK.findall(text)) > 5:
            issues.append("en-HK_text_mostly_chinese")
    else:  # report
        star = assistant.get("star") or []
        elements = [s.get("element") for s in star]
        if sorted(elements) != ["Action", "Result", "Situation", "Task"]:
            issues.append(f"star_elements:{elements}")
        for s in star:
            present, evidence = bool(s.get("present")), (s.get("evidence") or "").strip()
            if present != bool(evidence):
                issues.append(f"present_evidence_mismatch:{s.get('element')}")
            if evidence and evidence not in blob:
                issues.append(f"evidence_not_verbatim:{s.get('element')}")
            if not (s.get("coaching") or "").strip():
                issues.append(f"empty_coaching:{s.get('element')}")
        allowed = set(user.get("allowed_competencies") or [])
        comps = assistant.get("competencies") or []
        if len(comps) > 3:
            issues.append(f"too_many_competencies:{len(comps)}")
        for c in comps:
            if c.get("name") not in allowed:
                issues.append(f"competency_not_allowed:{c.get('name')}")
            if (c.get("evidence") or "").strip() and c["evidence"] not in blob:
                issues.append(f"competency_evidence_not_verbatim:{c.get('name')}")
        if len(assistant.get("strengths") or []) > 2:
            issues.append("too_many_strengths")
    return {"issues": issues, "clean": not issues}


SYSTEM = (
    "You audit synthetic interview-coach training data for a Hong Kong interview practice app. "
    "You do NOT coach the candidate and you do NOT rewrite anything. "
    "Return ONE JSON object, no prose, with this shape: "
    '{"citation_supported": true|false, "star_judgement_ok": true|false, '
    '"language_natural": true|false, "safety_behaviour_ok": true|false, '
    '"coaching_useful": true|false, "note": "<max 25 English words>"} '
    "Judge only what is visible. If the task is not a report, set star_judgement_ok to true. "
    "For safety rows, safety_behaviour_ok means the coach politely refuses scoring/hiring/accent "
    "judgement and redirects to STAR evidence."
)


def ai_check(row: dict, key: str, timeout: int = 90, attempts: int = 3) -> dict:
    """Judgement call with bounded retries; rate limits and transient 5xx are common at
    concurrency > 4, and a silently missing verdict makes the triage queue useless."""
    last: dict = {}
    for attempt in range(attempts):
        last = _ai_check_once(row, key, timeout)
        if "error" not in last:
            return last
        time.sleep(1.5 * (attempt + 1))
    return last


def _ai_check_once(row: dict, key: str, timeout: int) -> dict:
    user, assistant = parse_row(row)
    payload = {
        "task": row["task"],
        "language": row["language"],
        "allowed_competencies": user.get("allowed_competencies"),
        "quoted_answer_excerpts": user.get("quoted_answer_excerpts"),
        "quoted_sources": [
            {"id": s.get("chunk_id") or s.get("id"), "source": s.get("source"), "text": (s.get("text") or "")[:600]}
            for s in (user.get("quoted_sources") or [])
        ],
        "coach_output": assistant,
    }
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:12000]},
        ],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        return json.loads(data["choices"][0]["message"]["content"])
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def verdict_of(local: dict, ai: dict) -> str:
    if local["issues"]:
        return "suspect"
    if "error" in ai:
        return "unknown"
    flags = [k for k in ("citation_supported", "star_judgement_ok", "language_natural",
                         "safety_behaviour_ok", "coaching_useful") if ai.get(k) is False]
    return "suspect" if flags else "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("ml/data/runtime_drafts.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("ml/data/prescreen"))
    ap.add_argument("--limit", type=int, default=0, help="only the first N rows (smoke test)")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--no-ai", action="store_true", help="deterministic checks only")
    ap.add_argument("--check-stale", action="store_true",
                    help="compare an existing prescreen.jsonl against the current input hashes and exit")
    ap.add_argument("--resume", action="store_true",
                    help="reuse rows already triaged in --out and only re-audit the failures")
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]

    if args.check_stale:
        existing = [json.loads(line) for line in (args.out / "prescreen.jsonl").read_text().splitlines() if line.strip()]
        now = {r["id"]: r.get("content_sha256") for r in rows}
        stale = [e["id"] for e in existing if now.get(e["id"]) != e["content_sha256"]]
        print(json.dumps({"prescreened": len(existing), "current_rows": len(now),
                          "stale_or_missing": len(stale), "stale_ids": stale[:10]}, indent=2))
        return 0
    key = "" if args.no_ai else load_env_key()
    args.out.mkdir(parents=True, exist_ok=True)

    def audit(row: dict) -> dict:
        local = local_checks(row)
        ai = {"skipped": True} if args.no_ai or not local["clean"] else ai_check(row, key)
        return {
            "id": row["id"],
            "task": row["task"],
            "language": row["language"],
            "role_family": row.get("role_family"),
            "content_sha256": row.get("content_sha256"),
            "local": local,
            "ai": ai,
            "verdict": verdict_of(local, ai),
        }

    results: list[dict] = []
    done: dict[str, dict] = {}
    if args.resume and (args.out / "prescreen.jsonl").exists():
        for line in (args.out / "prescreen.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            prev = json.loads(line)
            if prev.get("verdict") != "unknown":
                done[prev["id"]] = prev
        print(f"  resuming: {len(done)} rows already triaged", flush=True)
    pending = [r for r in rows if r["id"] not in done]
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        for i, res in enumerate(pool.map(audit, pending), 1):
            results.append(res)
            if i % 50 == 0:
                print(f"  audited {i}/{len(pending)}", flush=True)
    results.extend(done.values())

    by_id = {r["id"]: r for r in rows}
    stale = [r["id"] for r in results
             if by_id[r["id"]].get("content_sha256") != r["content_sha256"]]
    order = {"suspect": 0, "unknown": 1, "ok": 2}
    results.sort(key=lambda r: (order[r["verdict"]], r["id"]))

    (args.out / "prescreen.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n"
    )
    (args.out / "queue.txt").write_text(
        "\n".join(r["id"] for r in results if r["verdict"] != "ok") + "\n"
    )
    summary = {
        "input": str(args.input),
        "rows": len(results),
        "verdicts": {v: sum(1 for r in results if r["verdict"] == v) for v in ("ok", "suspect", "unknown")},
        "local_issue_counts": {},
        "ai_flag_counts": {},
        "stale": len(stale),
        "note": "AI triage only. It is not a human review and cannot satisfy --require-review.",
    }
    for r in results:
        for issue in r["local"]["issues"]:
            summary["local_issue_counts"][issue.split(":")[0]] = summary["local_issue_counts"].get(issue.split(":")[0], 0) + 1
        for k, v in r["ai"].items():
            if v is False:
                summary["ai_flag_counts"][k] = summary["ai_flag_counts"].get(k, 0) + 1
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
