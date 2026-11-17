"""Saved-provider retrieval contracts: credentials, provenance, and vector dimensions."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import retrieval
from app.config import Settings
from app.db import Base, ChunkRecord, JobRecord, make_database


def settings(**changes):
    # Endpoint-policy validation belongs to the settings suite; these tests isolate retrieval.
    return Settings(_env_file=None).model_copy(
        update={
            "embedding_base_url": "https://embedding.example/v1",
            "embedding_model": "chosen-embedding",
            "embedding_api_key": "embedding-secret",
            "reranker_base_url": "",
            "reranker_api_key": "",
            **changes,
        }
    )


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.fixture
def db(tmp_path):
    engine, session_factory = make_database(f"sqlite:///{tmp_path / 'retrieval.db'}")
    Base.metadata.create_all(engine)
    with session_factory() as session:
        session.add_all(
            [
                JobRecord(id="current", title="Current", competencies=[], warnings=[]),
                JobRecord(id="other", title="Other", competencies=[], warnings=[]),
            ]
        )
        session.flush()
        session.add_all(
            [
                ChunkRecord(
                    id="a", source="current", text="current job text", job_profile_id="current"
                ),
                ChunkRecord(
                    id="b", source="shared", text="shared coaching text", job_profile_id=None
                ),
                ChunkRecord(
                    id="private",
                    source="other",
                    text="other private job text",
                    job_profile_id="other",
                ),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


@pytest.mark.asyncio
async def test_embedding_uses_saved_bearer_and_model_with_provider_dimensions(monkeypatch):
    def handler(request):
        assert str(request.url) == "https://embedding.example/v1/embeddings"
        assert request.headers["authorization"] == "Bearer embedding-secret"
        assert json.loads(request.content) == {"model": "chosen-embedding", "input": ["one", "two"]}
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0, 1, 0]},
                    {"index": 0, "embedding": [1, 0, 0]},
                ]
            },
        )

    mock_http(monkeypatch, handler)
    assert await retrieval.embed(["one", "two"], settings()) == [[1, 0, 0], [0, 1, 0]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [0, 1]}],
        [{"index": True, "embedding": [1]}, {"index": 0, "embedding": [1]}],
        [{"index": 0, "embedding": [1]}, {"index": 1, "embedding": [1, 0]}],
        [{"index": 0, "embedding": []}, {"index": 1, "embedding": []}],
        [{"index": 0, "embedding": [True]}, {"index": 1, "embedding": [1]}],
        [{"index": 0, "embedding": [0]}, {"index": 1, "embedding": [1]}],
        [{"index": 0, "embedding": "base64"}, {"index": 1, "embedding": [1]}],
        [{"index": 0, "embedding": [float("nan")]}, {"index": 1, "embedding": [1]}],
        [{"index": 0, "embedding": [float("inf")]}, {"index": 1, "embedding": [1]}],
    ],
)
async def test_embedding_rejects_malformed_or_inconsistent_vectors(monkeypatch, data):
    mock_http(monkeypatch, lambda _: httpx.Response(200, content=json.dumps({"data": data})))
    with pytest.raises(ValueError):
        await retrieval.embed(["one", "two"], settings())


@pytest.mark.asyncio
async def test_embedding_does_not_follow_redirects(monkeypatch):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://different.example/embeddings"})

    mock_http(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        await retrieval.embed(["secret source"], settings())
    assert requests == ["https://embedding.example/v1/embeddings"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"embedding_model": "replacement"},
        {"embedding_base_url": "https://replacement.example/v1"},
        {"embedding_api_key": "replacement-secret"},
    ],
)
async def test_changed_provider_reindexes_only_applicable_sources(monkeypatch, db, change):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append((str(request.url), payload))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [1, 0, 0]}
                    for index, _ in enumerate(payload["input"])
                ]
            },
        )

    mock_http(monkeypatch, handler)
    original = settings()
    all_chunks = list(db.scalars(select(ChunkRecord)))
    assert await retrieval.index_chunks(db, all_chunks, original)
    db.commit()
    old_private = db.get(ChunkRecord, "private").embedding
    calls.clear()
    changed = original.model_copy(update=change)
    result = await retrieval.retrieve(db, "current", "question", changed)
    assert {c.chunk_id for c in result} == {"a", "b"}
    sent = [text for _, payload in calls for text in payload["input"]]
    assert "current job text" in sent and "shared coaching text" in sent
    assert "other private job text" not in sent
    assert db.get(ChunkRecord, "private").embedding == old_private
    assert db.get(ChunkRecord, "a").embedding["provider"] != old_private["provider"]
    calls.clear()
    await retrieval.retrieve(db, "current", "second question", changed)
    assert len(calls) == 1  # Query only: this provider's source vectors are reused.


@pytest.mark.asyncio
async def test_invalidation_is_local_and_failed_reindex_never_uses_old_vectors(monkeypatch, db):
    for chunk in db.scalars(select(ChunkRecord)):
        chunk.embedding = [1, 0, 0]  # Legacy untagged vectors have unknown provenance.
    db.commit()
    retrieval.invalidate_embeddings(db)
    assert all(c.embedding is None for c in db.scalars(select(ChunkRecord)))
    db.commit()
    mock_http(monkeypatch, lambda _: httpx.Response(503))
    result = await retrieval.retrieve(db, "current", "current job", settings())
    assert result[0].chunk_id == "a"
    assert all(c.embedding is None for c in db.scalars(select(ChunkRecord)))


@pytest.mark.asyncio
async def test_query_and_source_dimensions_must_match(monkeypatch, db):
    def handler(request):
        values = json.loads(request.content)["input"]
        dimensions = 2 if values[0].startswith("Instruct:") else 3
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [1] + [0] * (dimensions - 1)}
                    for i, _ in enumerate(values)
                ]
            },
        )

    mock_http(monkeypatch, handler)
    result = await retrieval.retrieve(db, "current", "current job", settings())
    assert result[0].chunk_id == "a"
    assert db.get(ChunkRecord, "a").embedding is None


class PostgresFacade:
    """Exercise SQL branch selection and savepoint recovery using isolated SQLite records."""

    def __init__(self, db, fail_vectors=False):
        self.db = db
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        self.statements = []
        self.fail_vectors = fail_vectors
        self.in_savepoint = False
        self.recovered = False

    def __getattr__(self, name):
        return getattr(self.db, name)

    @contextmanager
    def begin_nested(self):
        assert not self.in_savepoint
        self.in_savepoint = True
        try:
            with self.db.begin_nested():
                yield
        except SQLAlchemyError:
            self.recovered = True
            raise
        finally:
            self.in_savepoint = False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params))
        if "embedding_vector" in sql:
            if self.fail_vectors:
                assert self.in_savepoint, (
                    "An optional vector failure must not poison the transaction"
                )
                raise SQLAlchemyError("simulated pgvector failure")
            if sql.lstrip().startswith("SELECT"):
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: ["a", "b"]))
            return None
        if "to_tsvector" in sql:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        return self.db.execute(statement, params or {})


@pytest.mark.asyncio
@pytest.mark.parametrize("dimensions", [3, 1024, 1536])
async def test_postgres_vector_casts_only_apply_to_1024_dimensions(monkeypatch, db, dimensions):
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [1] + [0] * (dimensions - 1)}
                    for i, _ in enumerate(json.loads(request.content)["input"])
                ]
            },
        ),
    )
    postgres = PostgresFacade(db)
    result = await retrieval.retrieve(postgres, "current", "current job", settings())
    assert len(result) == 2
    casts = [(sql, params) for sql, params in postgres.statements if "CAST(" in sql]
    if dimensions == 1024:
        assert casts
        vector_queries = [sql for sql, _ in casts if sql.lstrip().startswith("SELECT")]
        assert vector_queries and "provider" in vector_queries[0]
    else:
        assert not casts
    assert db.get(ChunkRecord, "a").embedding["dimensions"] == dimensions


@pytest.mark.asyncio
async def test_postgres_optional_failure_preserves_transaction_and_json_vectors(monkeypatch, db):
    mock_http(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [1] + [0] * 1023}
                    for i, _ in enumerate(json.loads(request.content)["input"])
                ]
            },
        ),
    )
    postgres = PostgresFacade(db, fail_vectors=True)
    db.get(JobRecord, "current").title = "Pending unrelated change"
    result = await retrieval.retrieve(postgres, "current", "current job", settings())
    assert result and postgres.recovered
    db.commit()
    assert db.get(JobRecord, "current").title == "Pending unrelated change"
    assert db.get(ChunkRecord, "a").embedding["pgvector"] is False


@pytest.mark.asyncio
async def test_reranker_uses_saved_model_and_bearer(monkeypatch, db):
    def handler(request):
        assert str(request.url) == "https://reranker.example/v1/rerank"
        assert request.headers["authorization"] == "Bearer rerank-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "chosen-reranker"
        assert "other private job text" not in payload["documents"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.8},
                    {"index": 0, "relevance_score": 0.2},
                ]
            },
        )

    mock_http(monkeypatch, handler)
    result = await retrieval.retrieve(
        db,
        "current",
        "current job",
        settings(
            embedding_base_url="",
            reranker_base_url="https://reranker.example/v1",
            reranker_model="chosen-reranker",
            reranker_api_key="rerank-secret",
        ),
    )
    assert [c.chunk_id for c in result] == ["b", "a"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "results",
    [
        [{"index": True, "relevance_score": 0.8}],
        [{"index": -1, "relevance_score": 0.8}],
        [{"index": 10, "relevance_score": 0.8}],
        [{"index": 1, "relevance_score": "1"}],
        [{"index": 1, "relevance_score": True}],
        [{"index": 1, "relevance_score": float("nan")}],
        [{"index": 1, "relevance_score": float("inf")}],
        [{"index": 1, "relevance_score": 1}, {"index": 1, "relevance_score": 2}],
        [],
    ],
)
async def test_invalid_reranking_falls_back_without_losing_passages(monkeypatch, db, results):
    mock_http(monkeypatch, lambda _: httpx.Response(200, content=json.dumps({"results": results})))
    result = await retrieval.retrieve(
        db,
        "current",
        "current job",
        settings(
            embedding_base_url="",
            reranker_base_url="https://reranker.example/v1",
        ),
    )
    assert [c.chunk_id for c in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_reranker_redirect_never_receives_documents_at_another_host(monkeypatch, db):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://different.example/rerank"})

    mock_http(monkeypatch, handler)
    result = await retrieval.retrieve(
        db,
        "current",
        "current job",
        settings(
            embedding_base_url="",
            reranker_base_url="https://reranker.example/v1",
            reranker_api_key="rerank-secret",
        ),
    )
    assert [c.chunk_id for c in result] == ["a", "b"]
    assert requests == ["https://reranker.example/v1/rerank"]


@pytest.mark.asyncio
async def test_real_postgres_dimensions_provenance_and_savepoint_recovery(monkeypatch):
    """Opt-in integration check; creates/drops only a unique test schema."""
    import os
    from uuid import uuid4

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    database_url = os.environ.get("VOXPREP_TEST_PG_URL")
    if not database_url:
        pytest.skip("Set VOXPREP_TEST_PG_URL for isolated PostgreSQL integration")
    schema = "voxprep_retrieval_test_" + uuid4().hex
    admin = create_engine(database_url)
    engine = None
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.extend(payload["input"])
        dimensions = 1536 if "1536" in payload["model"] else 1024
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [1] + [0] * (dimensions - 1)}
                    for index, _ in enumerate(payload["input"])
                ]
            },
        )

    mock_http(monkeypatch, handler)
    with admin.begin() as connection:
        # schema is generated locally from a fixed prefix and UUID hex, never user input.
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        engine = create_engine(
            database_url, connect_args={"options": f"-csearch_path={schema},public"}
        )
        Base.metadata.create_all(engine, checkfirst=False)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE source_chunks ADD COLUMN embedding_vector vector(1024)")
            )
        with Session(engine, expire_on_commit=False) as db:
            db.add_all(
                [
                    JobRecord(id="current", title="Current", competencies=[], warnings=[]),
                    JobRecord(id="other", title="Other", competencies=[], warnings=[]),
                ]
            )
            db.flush()
            db.add_all(
                [
                    ChunkRecord(
                        id="a", source="job", text="current job text", job_profile_id="current"
                    ),
                    ChunkRecord(
                        id="b", source="shared", text="shared coaching text", job_profile_id=None
                    ),
                    ChunkRecord(
                        id="private", source="other", text="private source", job_profile_id="other"
                    ),
                ]
            )
            db.commit()
            previous_provider = None
            for dimensions in [1024, 1536, 1024]:
                config = settings(embedding_model=f"model-{dimensions}-{previous_provider}")
                requests.clear()
                result = await retrieval.retrieve(db, "current", "current job", config)
                assert {item.chunk_id for item in result} == {"a", "b"}
                assert "current job text" in requests and "shared coaching text" in requests
                assert "private source" not in requests
                metadata = db.get(ChunkRecord, "a").embedding
                assert metadata["dimensions"] == dimensions
                assert metadata["provider"] != previous_provider
                previous_provider = metadata["provider"]
                actual_dimensions = db.scalar(
                    text("SELECT vector_dims(embedding_vector) FROM source_chunks WHERE id = 'a'")
                )
                assert actual_dimensions == (1024 if dimensions == 1024 else None)
                assert metadata["pgvector"] is (dimensions == 1024)
                db.commit()
                requests.clear()
                await retrieval.retrieve(db, "current", "next question", config)
                assert len(requests) == 1
            retrieval.invalidate_embeddings(db)
            db.commit()
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM source_chunks WHERE embedding IS NOT NULL OR embedding_vector IS NOT NULL"
                    )
                )
                == 0
            )
            # Deliberately remove acceleration only inside our disposable schema.
            db.execute(text("ALTER TABLE source_chunks DROP COLUMN embedding_vector"))
            db.commit()
            db.get(JobRecord, "current").title = "Unrelated update survives"
            result = await retrieval.retrieve(db, "current", "current job", config)
            assert result and db.get(ChunkRecord, "a").embedding["pgvector"] is False
            db.commit()  # Would raise InFailedSqlTransaction without SAVEPOINT recovery.
            assert db.get(JobRecord, "current").title == "Unrelated update survives"
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_failed_provider_change_cannot_rank_with_old_same_dimension_vectors(
    monkeypatch, db, legacy
):
    old = settings(embedding_model="old-provider")
    for chunk in db.scalars(select(ChunkRecord)):
        vector = [1, 0, 0] if chunk.id == "a" else [-1, 0, 0]
        chunk.embedding = (
            vector
            if legacy
            else {
                "provider": retrieval.embedding_provider(old),
                "dimensions": 3,
                "vector": vector,
                "pgvector": False,
            }
        )
    db.commit()

    def handler(request):
        inputs = json.loads(request.content)["input"]
        if inputs[0].startswith("Instruct:"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 0, 0]}]})
        return httpx.Response(503)

    mock_http(monkeypatch, handler)
    result = await retrieval.retrieve(db, "current", "shared coaching", settings(), limit=1)
    # With the stale dense ranking, reciprocal rank fusion would incorrectly choose a.
    assert result[0].chunk_id == "b"
