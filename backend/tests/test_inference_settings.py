import asyncio
import json
import stat

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        inference_settings_path=tmp_path / "inference-settings.json",
    )


def payload(**overrides):
    result = {
        name: {"base_url": "", "model": "", "api_key": ""}
        for name in ("agent", "asr", "embedding", "reranker")
    }
    result.update(overrides)
    return result


def component(url="https://provider.example/v1", key="synthetic-secret"):
    return {"base_url": url, "model": "test-model", "api_key": key}


def test_settings_persist_redacted_and_apply_without_restart(settings):
    with TestClient(create_app(settings)) as client:
        result = client.put("/api/inference-settings", json=payload(agent=component()))
        assert result.status_code == 200, result.text
        assert result.json()["agent"]["api_key_set"] is True
        assert "synthetic-secret" not in result.text
        assert client.app.state.settings.model_provider == "openai"
        assert stat.S_IMODE(settings.inference_settings_path.stat().st_mode) == 0o600
    with TestClient(create_app(settings)) as client:
        result = client.get("/api/inference-settings")
        assert result.json()["agent"] == {
            "base_url": "https://provider.example/v1",
            "model": "test-model",
            "api_key_set": True,
        }
        assert client.app.state.settings.agent_api_key == "synthetic-secret"


def test_key_retention_is_bound_to_destination(settings):
    with TestClient(create_app(settings)) as client:
        assert (
            client.put("/api/inference-settings", json=payload(agent=component())).status_code
            == 200
        )
        assert (
            client.put(
                "/api/inference-settings", json=payload(agent=component(key=None))
            ).status_code
            == 200
        )
        changed = payload(agent=component("https://different.example/v1", None))
        result = client.put("/api/inference-settings", json=changed)
        assert result.status_code == 422
        assert "synthetic-secret" not in result.text
        assert (
            client.get("/api/inference-settings").json()["agent"]["base_url"]
            == "https://provider.example/v1"
        )
        changed["agent"]["api_key"] = ""
        assert (
            client.put("/api/inference-settings", json=changed).json()["agent"]["api_key_set"]
            is False
        )
        assert client.put("/api/inference-settings", json=payload()).status_code == 200
        assert client.app.state.settings.model_provider == "demo"


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/v1",
        "https://u:secret@host.example/v1",
        "https://host.example/v1?key=secret",
        "https://host.example/#secret",
        "file:///tmp/model",
        "https://host.example:bad/v1",
    ],
)
def test_invalid_destination_and_validation_do_not_echo_secrets(settings, url):
    with TestClient(create_app(settings)) as client:
        result = client.put("/api/inference-settings", json=payload(agent=component(url)))
        assert result.status_code == 422
        assert "synthetic-secret" not in result.text
        assert "input" not in result.text
        assert not settings.inference_settings_path.exists()


def test_discovery_uses_stored_key_without_mutating_and_rejects_redirect(settings, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer synthetic-secret"
        if len(calls) == 1:
            return httpx.Response(200, json={"data": [{"id": "model-b"}, {"id": "model-a"}]})
        return httpx.Response(302, headers={"Location": "https://elsewhere.example/v1/models"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    with TestClient(create_app(settings)) as client:
        client.put("/api/inference-settings", json=payload(agent=component()))
        before = settings.inference_settings_path.read_bytes()
        request = {"base_url": "https://provider.example/v1", "api_key": None}
        result = client.post("/api/inference-settings/agent/models", json=request)
        assert result.status_code == 200, result.text
        assert result.json() == {"models": ["model-a", "model-b"]}
        result = client.post("/api/inference-settings/agent/models", json=request)
        assert result.status_code == 502
        assert len(calls) == 2
        assert settings.inference_settings_path.read_bytes() == before
        result = client.post(
            "/api/inference-settings/agent/models",
            json={**request, "base_url": "https://elsewhere.example/v1"},
        )
        assert result.status_code == 422
        assert len(calls) == 2


def test_save_failure_preserves_previous_configuration(settings, monkeypatch):
    with TestClient(create_app(settings)) as client:
        client.put("/api/inference-settings", json=payload(agent=component()))
        before = settings.inference_settings_path.read_bytes()
        monkeypatch.setattr(
            "os.replace", lambda *args: (_ for _ in ()).throw(OSError("secret filesystem path"))
        )
        result = client.put("/api/inference-settings", json=payload())
        assert result.status_code == 503
        assert "secret filesystem path" not in result.text
        assert settings.inference_settings_path.read_bytes() == before
        assert client.app.state.settings.model_provider == "openai"


def test_active_operation_blocks_save(settings):
    with TestClient(create_app(settings)) as client:
        with client.app.state.inference.operation():
            result = client.put("/api/inference-settings", json=payload(agent=component()))
        assert result.status_code == 409
        assert not settings.inference_settings_path.exists()


@pytest.mark.parametrize(
    "key", ["bad\nsecret", "廣東話secret", "x" * 4097, 42, {"secret": "value"}]
)
def test_invalid_keys_are_rejected_without_input_echo(settings, key):
    with TestClient(create_app(settings)) as client:
        result = client.put("/api/inference-settings", json=payload(agent=component(key=key)))
        assert result.status_code == 422
        assert "input" not in result.text
        assert "secret" not in result.text


def test_live_agent_asr_routes_and_authenticated_health(settings, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer synthetic-secret"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "A synthetic recorded answer."})
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        result = {
            "interviewer_text": "Tell me about your project.",
            "question_type": "opening",
            "targeted_competencies": context["allowed_competencies"][:1],
            "adaptive_follow_up_reason": None,
            "citation_ids": [context["quoted_sources"][0]["chunk_id"]],
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    with TestClient(create_app(settings)) as client:
        assert (
            client.put(
                "/api/inference-settings",
                json=payload(agent=component(), asr=component("https://asr.example/v1")),
            ).status_code
            == 200
        )
        profile = client.post(
            "/api/job-profiles", json={"text": "Software engineer using Python, SQL, and teamwork."}
        ).json()
        session = client.post(
            "/api/sessions", json={"job_profile_id": profile["id"], "store_transcript": True}
        ).json()
        assert session["provider"] == "openai"
        assert client.get("/api/health").json()["llm"] == "ready (configured inference provider)"
        result = client.post(
            "/api/speech/transcribe",
            files={"file": ("speech.wav", b"RIFF" + b"x" * 20)},
            data={"language": "zh-HK"},
        )
        assert result.json()["provider"] == "openai-compatible"
        assert (
            client.put(
                "/api/inference-settings",
                json=payload(
                    agent=component("https://second.example/v1"),
                    asr=component("https://asr.example/v1"),
                ),
            ).status_code
            == 200
        )
        result = client.post(
            f"/api/sessions/{session['id']}/answer",
            json={
                "transcript": "I wrote Python tests.",
                "language": "en-HK",
                "elapsed_seconds": 10,
            },
        )
        assert result.status_code == 200
        assert requests[-1].url.host == "second.example"


def test_foreign_origin_cannot_change_settings_or_discover_models(settings):
    with TestClient(create_app(settings)) as client:
        headers = {"Origin": "https://untrusted.example"}
        assert (
            client.put("/api/inference-settings", json=payload(), headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                "/api/inference-settings/agent/models", json=component(), headers=headers
            ).status_code
            == 403
        )
        assert not settings.inference_settings_path.exists()


@pytest.mark.parametrize("response", [{"data": [{}]}, {"data": [{"id": 42}]}, {"models": []}, []])
def test_malformed_discovery_response_is_sanitized(settings, monkeypatch, response):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
            **kwargs,
        ),
    )
    with TestClient(create_app(settings)) as client:
        result = client.post("/api/inference-settings/asr/models", json=component())
        assert result.status_code == 502
        assert "synthetic-secret" not in result.text
        assert not settings.inference_settings_path.exists()


def test_corrupt_persisted_settings_fail_closed_without_echo(settings):
    settings.inference_settings_path.write_text('{"agent":{"api_key":"synthetic-secret"}}')
    with pytest.raises(RuntimeError, match="could not be loaded") as error:
        create_app(settings)
    assert "synthetic-secret" not in str(error.value)


def test_restart_never_indexes_old_private_job_descriptions(settings, monkeypatch):
    with TestClient(create_app(settings)) as client:
        client.post(
            "/api/job-profiles",
            json={"text": "Private synthetic job requiring Python and teamwork."},
        )
    indexed_profiles = []

    async def record_index(db, chunks, settings):
        indexed_profiles.extend(chunk.job_profile_id for chunk in chunks)
        return False

    monkeypatch.setattr("app.main.index_chunks", record_index)
    with TestClient(
        create_app(
            settings.model_copy(update={"embedding_base_url": "https://embedding.example/v1"})
        )
    ):
        pass
    assert indexed_profiles
    assert all(profile is None for profile in indexed_profiles)


@pytest.mark.asyncio
async def test_real_question_operation_blocks_configuration_change(settings, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    from app.coach import demo_question

    async def delayed_question(
        snapshot, competencies, language, difficulty, index, previous, sources
    ):
        entered.set()
        await release.wait()
        assert snapshot.model_provider == "demo"
        return demo_question(competencies, language, difficulty, index, previous, sources), "demo"

    monkeypatch.setattr("app.service.generate_question", delayed_question)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            profile = (
                await client.post(
                    "/api/job-profiles",
                    json={"text": "Software engineer using Python and SQL databases."},
                )
            ).json()
            pending = asyncio.create_task(
                client.post(
                    "/api/sessions",
                    json={"job_profile_id": profile["id"], "store_transcript": True},
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            try:
                result = await client.put(
                    "/api/inference-settings", json=payload(agent=component())
                )
                assert result.status_code == 409
                assert app.state.settings.model_provider == "demo"
            finally:
                release.set()
                await pending
            result = await client.put("/api/inference-settings", json=payload(agent=component()))
            assert result.status_code == 200
            assert app.state.service.settings.model_provider == "openai"


def test_embedding_settings_change_clears_cached_vectors_without_provider_call(settings):
    from sqlalchemy import select

    from app.db import ChunkRecord

    with TestClient(create_app(settings)) as client:
        with client.app.state.sessions() as db:
            chunk = db.scalars(select(ChunkRecord)).first()
            chunk.embedding = [1, 0, 0]
            db.commit()
        response = client.put("/api/inference-settings", json=payload(embedding=component()))
        assert response.status_code == 200
        with client.app.state.sessions() as db:
            assert all(chunk.embedding is None for chunk in db.scalars(select(ChunkRecord)))


@pytest.mark.asyncio
async def test_index_cli_honors_saved_disabled_embedding(settings, monkeypatch):
    from app import index_knowledge

    with TestClient(create_app(settings)) as client:
        assert client.put("/api/inference-settings", json=payload()).status_code == 200
    monkeypatch.setattr(
        index_knowledge,
        "Settings",
        lambda: settings.model_copy(
            update={"embedding_base_url": "https://environment.example/v1"}
        ),
    )
    with pytest.raises(SystemExit, match="Configure an embedding service"):
        await index_knowledge.main()
