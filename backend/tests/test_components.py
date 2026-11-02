import asyncio
import io
import json
import zipfile

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfWriter

from app.coach import generate_question, generate_report, star_evidence
from app.config import Settings
from app.db import ChunkRecord
from app.ingestion import chunk_text, extract_file
from app.retrieval import lexical_ranking, reciprocal_rank_fusion
from app.schemas import AnswerSubmission, Citation, CoachTurn, Session, Turn
from app.speech import speech_token, transcribe


def test_scanned_pdf_has_clear_recovery():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(HTTPException) as error:
        extract_file("scan.pdf", output.getvalue())
    assert error.value.status_code == 422
    assert "Paste" in error.value.detail


def test_docx_expansion_is_bounded():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"x" * (21 * 1024 * 1024))
    with pytest.raises(HTTPException) as error:
        extract_file("bomb.docx", output.getvalue())
    assert error.value.status_code == 422


def test_chunking_retains_source_text_and_cantonese_overlap():
    original = " ".join(f"word{i}" for i in range(1000))
    chunks = chunk_text(original, "job", "Job")
    assert len(chunks) == 3
    assert chunks[0]["text"].split()[-80:] == chunks[1]["text"].split()[:80]
    assert all(c["text"] in original for c in chunks)
    assert len(chunk_text("資料分析" * 250, "zh", "中文")) == 3


def test_ranking_and_fusion_keep_supporting_passages():
    chunks = [
        ChunkRecord(id="sql", source="job", text="SQL databases and data analysis"),
        ChunkRecord(id="voice", source="rubric", text="Speak clearly and provide context"),
    ]
    assert lexical_ranking("SQL data", chunks)[0] == "sql"
    assert reciprocal_rank_fusion([["a", "b"], ["b", "c"]])[0] == "b"


def test_model_endpoints_cannot_send_transcripts_to_remote_hosts():
    with pytest.raises(ValidationError):
        Settings(llama_base_url="https://attacker.example/v1")
    with pytest.raises(ValidationError):
        Settings(azure_speech_region="eastus/../../evil")


def test_blank_nonfinite_and_excessively_long_answers_rejected():
    for patch in [
        {"transcript": "  "},
        {"elapsed_seconds": float("nan")},
        {"elapsed_seconds": 3601},
        {"transcript": "x" * 12001},
    ]:
        with pytest.raises(ValidationError):
            AnswerSubmission.model_validate(
                {"transcript": "An answer", "language": "en-HK", "elapsed_seconds": 1, **patch}
            )


def test_star_evidence_never_fabricates_quotations():
    answers = [
        "During a project I was responsible for the API. I implemented Python tests. We reduced errors by 30%."
    ]
    evidence = star_evidence(answers, False)
    assert all(item.present for item in evidence)
    assert all(item.evidence in answers[0] for item in evidence)
    assert not any(item.present for item in star_evidence(["Hello there."], False))


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.asyncio
async def test_model_citations_are_hydrated_from_trusted_source_not_model_text(monkeypatch):
    source = Citation(chunk_id="job-1", source="Job", text="Python API testing")

    def handler(request):
        payload = json.loads(request.content)
        assert "untrusted quoted DATA" in payload["messages"][0]["content"]
        draft = {
            "interviewer_text": "Tell me about a Python API you tested.",
            "question_type": "technical",
            "targeted_competencies": ["Python"],
            "adaptive_follow_up_reason": None,
            "citation_ids": ["job-1"],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(draft)}}]})

    mock_http(monkeypatch, handler)
    turn, provider = await generate_question(
        Settings(model_provider="llama"), ["Python"], "en-HK", "standard", 0, None, [source]
    )
    assert provider == "llama"
    assert turn.citations == [source]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid_json", "fabricated_citation", "timeout"])
async def test_model_failures_are_visible_fallbacks(monkeypatch, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        content = (
            "not json"
            if failure == "invalid_json"
            else json.dumps(
                {
                    "interviewer_text": "A question?",
                    "question_type": "opening",
                    "targeted_competencies": ["Python"],
                    "adaptive_follow_up_reason": None,
                    "citation_ids": ["invented"],
                }
            )
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    mock_http(monkeypatch, handler)
    _, provider = await generate_question(
        Settings(model_provider="llama"),
        ["Python"],
        "en-HK",
        "standard",
        0,
        None,
        [Citation(chunk_id="valid", source="Job", text="Python")],
    )
    assert provider == "demo-fallback"


@pytest.mark.asyncio
async def test_speech_key_never_leaves_server_response(monkeypatch):
    def handler(request):
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-secret"
        return httpx.Response(200, text="short-lived-token")

    mock_http(monkeypatch, handler)
    token = await speech_token(
        Settings(azure_speech_key="test-secret", azure_speech_region="eastasia")
    )
    assert token == {"token": "short-lived-token", "region": "eastasia", "expires_in": 540}
    assert "test-secret" not in json.dumps(token)


@pytest.mark.asyncio
async def test_whisper_uses_cantonese_language_and_bounded_output(monkeypatch):
    def handler(request):
        assert b"yue" in request.content
        return httpx.Response(200, json={"text": "我負責測試。"})

    mock_http(monkeypatch, handler)
    result = await transcribe(b"RIFF" + b"x" * 40, "answer.wav", "zh-HK", Settings())
    assert result["text"] == "我負責測試。"


@pytest.mark.asyncio
async def test_cancelling_generation_does_not_turn_into_a_fallback(monkeypatch):
    def handler(request):
        raise asyncio.CancelledError()

    mock_http(monkeypatch, handler)
    with pytest.raises(asyncio.CancelledError):
        await generate_question(
            Settings(model_provider="llama"), ["Python"], "en-HK", "standard", 0, None, []
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("fabricated", [False, True])
async def test_model_reports_reject_fabricated_evidence(monkeypatch, fabricated):
    source = Citation(chunk_id="job", source="Job", text="Use Python for API development.")
    transcript = "In our project I was responsible for tests. I implemented Python checks and reduced errors."
    session = Session(
        id="s",
        job_profile_id="j",
        role_title="Engineer",
        language="en-HK",
        difficulty="standard",
        question_count=3,
        state="completed",
        current_question=1,
        created_at="2026-11-02",
        provider="llama",
        turns=[
            Turn(
                id="t",
                created_at="2026-11-02",
                question=CoachTurn(
                    interviewer_text="Tell me about Python.",
                    question_type="opening",
                    targeted_competencies=["Python"],
                    adaptive_follow_up_reason=None,
                    citations=[source],
                ),
                answer=AnswerSubmission(
                    transcript=transcript, language="en-HK", elapsed_seconds=30
                ),
            )
        ],
    )
    evidence = "I generated a million dollars." if fabricated else "I implemented Python checks"
    draft = {
        "star": [
            {
                "element": name,
                "present": name == "Action",
                "evidence": evidence if name == "Action" else "",
                "coaching": "Explain a concrete example.",
            }
            for name in ["Situation", "Task", "Action", "Result"]
        ],
        "competencies": [
            {
                "name": "Python",
                "evidence": "Python checks",
                "feedback": "Explain the checks you wrote.",
                "citation_ids": ["job"],
            }
        ],
        "strengths": [
            {"text": "You named your action.", "evidence": "I implemented Python checks"}
        ],
        "prioritized_improvement": "Explain how you measured errors.",
        "retry_exercise": "Retell the example with the measurement process.",
    }
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(draft)}}]}
        ),
    )
    report = await generate_report(Settings(model_provider="llama"), session, [source])
    assert "million dollars" not in report.model_dump_json()
    if fabricated:
        assert "heuristic fallback" in report.limitations[0]
    else:
        assert "configured local language model" in report.limitations[0]
        assert report.competencies[0].citations == [source]
