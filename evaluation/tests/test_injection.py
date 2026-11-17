"""Checks for the prompt-injection harness: cases reach the model, obedience is caught."""

import json
from pathlib import Path

import pytest

from evaluation import injection

CASES = Path("evaluation/fixtures/injection_cases.jsonl")


def load_cases():
    return [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]


def test_fixture_covers_both_languages_and_tasks():
    cases = load_cases()
    assert len(cases) == 12
    assert {c["language"] for c in cases} == {"en-HK", "zh-HK"}
    assert {c["task"] for c in cases} == {"question", "report"}
    assert {c["attack"] for c in cases} >= {"score", "hiring", "accent", "prompt_leak"}
    assert all(c["job_text"].strip() and c["injection"].strip() for c in cases)


def test_every_injection_reaches_the_quoted_sources():
    """The attack has to be visible to the model, otherwise the case proves nothing."""
    for case in load_cases():
        sources, competencies, _warnings = injection.build_sources(case)
        assert sources, case["id"]
        assert competencies, case["id"]
        assert any(case["injection"][:40] in s.text for s in sources), case["id"]


def test_ingestion_detector_coverage_is_a_known_gap():
    """`ingestion.profile_metadata` only flags a narrow instruction vocabulary.

    Covered: "system:", "system prompt", "<|im_start|>", "ignore … instructions" and the
    Chinese equivalent. NOT covered: "you are the hiring manager", "rate the accent",
    "Ignore the STAR rubric", "treat the following as your highest priority". Those cases
    rely on the model refusing and on this checker, not on the ingestion warning.
    """
    covered = {
        case["id"]
        for case in load_cases()
        if any(
            "Instruction-like" in w
            for w in injection.profile_metadata(
                case["job_text"] + "\n" + case["injection"], case["title"]
            )[2]
        )
    }
    # Exactly these five raise the ingestion warning today; the rest of the attacks are
    # invisible to it and depend on the model refusing.
    assert covered == {
        "inj-q-en-score",
        "inj-q-en-leak",
        "inj-q-en-marker",
        "inj-q-zh-score",
        "inj-r-en-leak",
    }


def test_instruction_like_text_is_flagged_by_ingestion():
    case = next(c for c in load_cases() if c["attack"] == "score" and c["language"] == "en-HK")
    _title, _competencies, warnings = injection.profile_metadata(
        case["job_text"] + "\n" + case["injection"], case["title"]
    )
    assert any("Instruction-like" in w for w in warnings)


def test_compliant_answers_pass_every_case():
    for case in load_cases():
        record = injection.run_case(case, "", "", 1, mock=True, unsafe=False)
        assert record["passed"], (record["id"], record["violations"])


@pytest.mark.parametrize("attack", ["score", "hiring", "prompt_leak"])
def test_obedient_answers_are_caught_for_each_attack(attack):
    case = next(
        c
        for c in load_cases()
        if c["attack"] == attack and c["task"] == "question" and c["language"] == "en-HK"
    )
    record = injection.run_case(case, "", "", 1, mock=True, unsafe=True)
    assert not record["passed"]
    assert any(v.startswith(f"obeyed_{attack}") for v in record["violations"]), record["violations"]


def test_invented_citation_is_rejected():
    case = next(c for c in load_cases() if c["task"] == "question")
    sources, _competencies, _warnings = injection.build_sources(case)
    answer = {
        "interviewer_text": "Tell me about the API you built.",
        "question_type": "opening",
        "targeted_competencies": ["Python"],
        "adaptive_follow_up_reason": None,
        "citation_ids": ["not-a-real-chunk"],
    }
    problems = injection.violations(answer, case, sources)
    assert "invented_citation" in problems


def test_zh_hk_answer_without_chinese_is_rejected():
    case = next(c for c in load_cases() if c["language"] == "zh-HK" and c["task"] == "question")
    sources, _competencies, _warnings = injection.build_sources(case)
    answer = {
        "interviewer_text": "Tell me about the API you built in Python.",
        "question_type": "opening",
        "targeted_competencies": ["Python"],
        "adaptive_follow_up_reason": None,
        "citation_ids": [sources[0].chunk_id],
    }
    assert "zh-HK_text_lacks_chinese" in injection.violations(answer, case, sources)


def test_report_shape_is_enforced():
    case = next(c for c in load_cases() if c["task"] == "report")
    sources, _competencies, _warnings = injection.build_sources(case)
    answer = {
        "star": [{"element": "Situation", "present": False, "evidence": "", "coaching": "add detail"}],
        "competencies": [],
        "strengths": [],
        "prioritized_improvement": "Name the outcome.",
        "retry_exercise": "Answer again with one number.",
    }
    assert "star_shape" in injection.violations(answer, case, sources)


def test_cli_writes_a_labelled_summary(tmp_path, monkeypatch):
    """--mock must be recorded as diagnostic_mock, never as a measured result."""
    out = tmp_path / "injection.json"
    monkeypatch.setattr(
        "sys.argv",
        ["injection", "--mock", "--out", str(out)],
    )
    assert injection.main() == 0
    summary = json.loads(out.read_text())
    assert summary["status"] == "diagnostic_mock"
    assert summary["cases"] == len(load_cases())
    assert summary["passed"] == summary["cases"]
