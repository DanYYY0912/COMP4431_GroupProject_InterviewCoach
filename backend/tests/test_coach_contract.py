"""Shared runtime contracts used by the app, dataset authoring and evaluation."""

import copy
import json

import pytest

from app.coach import (
    REPORT_INSTRUCTIONS,
    SYSTEM_PROMPT,
    ModelCoachTurn,
    ModelReport,
    answer_excerpts,
    check_question_output,
    check_report_output,
    question_messages,
    quoted_source_excerpts,
    report_messages,
)
from app.schemas import AnswerSubmission, Citation


@pytest.fixture
def sources():
    return [Citation(chunk_id="job:0", source="Job", text="Python testing.\n資料測試。")]


@pytest.fixture
def question():
    return {
        "interviewer_text": "可唔可以講下你點樣用 Python？",
        "question_type": "opening",
        "targeted_competencies": ["Python"],
        "adaptive_follow_up_reason": None,
        "citation_ids": ["job:0"],
    }


@pytest.fixture
def report():
    return {
        "star": [
            {
                "element": element,
                "present": element == "Action",
                "evidence": "我寫咗 Python 測試。" if element == "Action" else "",
                "coaching": "講清楚你嘅做法。",
            }
            for element in ["Situation", "Task", "Action", "Result"]
        ],
        "competencies": [
            {
                "name": "Python",
                "evidence": "Python 測試",
                "feedback": "補充測試結果。",
                "citation_ids": ["job:0"],
            }
        ],
        "strengths": [{"text": "講出行動。", "evidence": "我寫咗 Python 測試。"}],
        "prioritized_improvement": "補充你點樣驗證結果。",
        "retry_exercise": "用一分鐘再講一次你嘅例子。",
    }


def test_question_prompt_preserves_runtime_payload(sources):
    previous = AnswerSubmission(transcript="我寫咗測試。", language="zh-HK", elapsed_seconds=30)
    messages = question_messages(["Python"], "zh-HK", "stretch", 2, previous, sources)
    payload = {
        "language": "zh-HK",
        "difficulty": "stretch",
        "question_number": 3,
        "allowed_competencies": ["Python"],
        "previous_answer": previous.model_dump(),
        "quoted_sources": quoted_source_excerpts(sources, "Python"),
    }
    assert messages == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    assert (
        json.loads(
            question_messages(["Python"], "en-HK", "standard", 0, None, sources)[1]["content"]
        )["previous_answer"]
        is None
    )


def test_answer_context_preserves_exact_unit_and_character_boundaries():
    english = " ".join(["word"] * 200)
    chinese = "我" * 200
    long_word = "x" * 1500
    answers = [english, chinese, long_word, "", "   "]
    assert answer_excerpts(answers) == [" ".join(["word"] * 160), "我" * 160, "x" * 1000, "", "   "]
    assert answer_excerpts([]) == []
    assert answer_excerpts(["word! " * 100])[0] == "word! " * 79 + "word!"


def test_report_prompt_preserves_runtime_payload(sources):
    excerpts = ["我寫咗 Python 測試。"]
    messages = report_messages("zh-HK", ["Python"], excerpts, sources)
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT + REPORT_INSTRUCTIONS}
    assert messages[1]["content"] == json.dumps(
        {
            "task": "Give reflective STAR coaching for these interview answers. Do not score the person.",
            "language": "zh-HK",
            "allowed_competencies": ["Python"],
            "quoted_answer_excerpts": excerpts,
            "quoted_sources": quoted_source_excerpts(sources, "Python"),
        },
        ensure_ascii=False,
    )


def test_question_validation_hydrates_and_deduplicates_citations(question, sources):
    question["citation_ids"] *= 2
    turn = check_question_output(
        ModelCoachTurn.model_validate(question), ["Python"], "zh-HK", sources
    )
    assert turn.citations == sources


@pytest.mark.parametrize(
    "patch",
    [
        {"citation_ids": ["forged"]},
        {"targeted_competencies": ["Unknown"]},
        {"interviewer_text": "Tell me about Python."},
    ],
)
def test_question_validation_rejects_invalid_grounding_and_language(question, sources, patch):
    with pytest.raises(ValueError):
        check_question_output(
            ModelCoachTurn.model_validate({**question, **patch}), ["Python"], "zh-HK", sources
        )


def test_report_validation_accepts_exact_evidence(report, sources):
    before = copy.deepcopy(report)
    feedback = check_report_output(
        ModelReport.model_validate(report), ["Python"], "zh-HK", ["我寫咗 Python 測試。"], sources
    )
    assert feedback[0].citations == sources
    assert report == before


@pytest.mark.parametrize(
    "failure",
    [
        "star_repeat",
        "presence",
        "star_evidence",
        "competency_evidence",
        "strength_evidence",
        "citation",
        "competency",
        "language",
    ],
)
def test_report_validation_rejects_invalid_evidence_and_language(report, sources, failure):
    if failure == "star_repeat":
        report["star"][0]["element"] = "Action"
    elif failure == "presence":
        report["star"][2]["present"] = False
    elif failure == "star_evidence":
        report["star"][2]["evidence"] = "I improved accuracy."
    elif failure == "competency_evidence":
        report["competencies"][0]["evidence"] = "I wrote Python tests."
    elif failure == "strength_evidence":
        report["strengths"][0]["evidence"] = "Python test"
    elif failure == "citation":
        report["competencies"][0]["citation_ids"] = ["forged"]
    elif failure == "competency":
        report["competencies"][0]["name"] = "Unknown"
    else:
        report["prioritized_improvement"] = "Explain the result."
        report["retry_exercise"] = "Retry your example."
    with pytest.raises(ValueError):
        check_report_output(
            ModelReport.model_validate(report),
            ["Python"],
            "zh-HK",
            ["我寫咗 Python 測試。"],
            sources,
        )


def test_english_sessions_reject_chinese_drift(question, sources):
    """A 4B model asked for en-HK still slips into Chinese when the JD or labels are Chinese."""
    english = {**question, "interviewer_text": "Tell me about a time you used Python."}
    assert check_question_output(
        ModelCoachTurn.model_validate(english), ["Python"], "en-HK", sources
    ).interviewer_text.startswith("Tell me")

    with pytest.raises(ValueError):
        check_question_output(
            ModelCoachTurn.model_validate(question), ["Python"], "en-HK", sources
        )


def test_english_report_rejects_chinese_coaching(report, sources):
    excerpts = [item["evidence"] for item in report["star"] if item["evidence"]]
    english = {
        **report,
        "star": [{**item, "coaching": "Say what you did."} for item in report["star"]],
        "competencies": [{**item, "feedback": "Add the result."} for item in report["competencies"]],
        "strengths": [{**item, "text": "You named the action."} for item in report["strengths"]],
        "prioritized_improvement": "Add one sentence on the result.",
        "retry_exercise": "Answer the same question in one minute.",
    }
    assert check_report_output(
        ModelReport.model_validate(english), ["Python"], "en-HK", excerpts, sources
    )
    with pytest.raises(ValueError):
        check_report_output(
            ModelReport.model_validate(report), ["Python"], "en-HK", excerpts, sources
        )
