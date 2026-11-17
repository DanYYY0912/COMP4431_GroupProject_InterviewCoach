import json

import httpx
import pytest

from app.coach import generate_question
from app.config import Settings
from app.schemas import Citation
from app.speech import transcribe


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_citation", [False, True])
async def test_agent_auth_and_json_mode_fallback_preserves_grounding(monkeypatch, bad_citation):
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url) == "https://provider.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-secret"
        body = json.loads(request.content)
        assert body["model"] == "custom-agent"
        if len(requests) == 1:
            assert body["response_format"]["type"] == "json_schema"
            return httpx.Response(
                400, json={"error": {"message": "response_format json_schema is unsupported"}}
            )
        assert body["response_format"] == {"type": "json_object"}
        assert "citation_ids" in body["messages"][0]["content"]
        output = {
            "interviewer_text": "Tell me about Python.",
            "question_type": "opening",
            "targeted_competencies": ["Python"],
            "adaptive_follow_up_reason": None,
            "citation_ids": ["invented" if bad_citation else "source"],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    mock_http(monkeypatch, handler)
    settings = Settings(
        model_provider="openai",
        llama_base_url="https://provider.example/v1",
        model_name="custom-agent",
        agent_api_key="synthetic-secret",
    )
    question, provider = await generate_question(
        settings,
        ["Python"],
        "en-HK",
        "standard",
        0,
        None,
        [Citation(chunk_id="source", source="job", text="Python")],
    )
    assert len(requests) == 2
    assert provider == ("demo-fallback" if bad_citation else "openai")
    assert question.citations[0].chunk_id == "source"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429, 500])
async def test_agent_does_not_retry_auth_rate_limit_or_server_failures(monkeypatch, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, text="synthetic-secret")

    mock_http(monkeypatch, handler)
    _, provider = await generate_question(
        Settings(model_provider="openai"), ["Python"], "en-HK", "standard", 0, None, []
    )
    assert provider == "demo-fallback"
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("language,code", [("en-HK", "en"), ("zh-HK", "zh")])
@pytest.mark.parametrize(
    "audio,extension,mime",
    [
        (b"RIFF" + b"x" * 20, ".wav", "audio/wav"),
        (b"\x1aE\xdf\xa3" + b"x" * 20, ".webm", "audio/webm"),
        (b"OggS" + b"x" * 20, ".ogg", "audio/ogg"),
        (b"\x00\x00\x00\x18ftypM4A " + b"x" * 20, ".m4a", "audio/mp4"),
    ],
)
async def test_openai_asr_routes_auth_model_language_and_mime(
    monkeypatch, language, code, audio, extension, mime
):
    def handler(request):
        assert str(request.url) == "https://asr.example/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer speech-secret"
        body = request.content.decode(errors="replace")
        assert f'filename="recording{extension}"' in body
        assert f"Content-Type: {mime}" in body
        assert 'name="model"\r\n\r\ncustom-asr' in body
        assert f'name="language"\r\n\r\n{code}' in body
        return httpx.Response(200, json={"text": "A synthetic answer."})

    mock_http(monkeypatch, handler)
    result = await transcribe(
        audio,
        "wrong.exe",
        language,
        Settings(
            asr_base_url="https://asr.example/v1",
            asr_model="custom-asr",
            asr_api_key="speech-secret",
        ),
    )
    assert result == {"text": "A synthetic answer.", "provider": "openai-compatible"}
