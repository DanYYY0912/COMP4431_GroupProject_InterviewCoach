import hashlib
import json
import math
import re
from collections import Counter

import httpx
from sqlalchemy import or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from .config import ROOT, Settings
from .db import ChunkRecord
from .ingestion import chunk_text
from .schemas import Citation


def tokens(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", value.lower())
    return words + [a + b for a, b in zip(words, words[1:]) if len(a) == len(b) == 1]


def lexical_ranking(query: str, chunks: list[ChunkRecord]) -> list[str]:
    query_terms = set(tokens(query))
    counts = [Counter(tokens(chunk.text)) for chunk in chunks]
    frequency = Counter(term for count in counts for term in count)
    scores = []
    for chunk, count in zip(chunks, counts):
        score = sum(
            (1 + math.log(count[t])) * math.log(1 + len(chunks) / (1 + frequency[t]))
            for t in query_terms
            if count[t]
        )
        scores.append((score, chunk.id))
    return [key for _, key in sorted(scores, reverse=True)]


def reciprocal_rank_fusion(rankings: list[list[str]]) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda key: (-scores[key], key))


def citation(chunk: ChunkRecord) -> Citation:
    return Citation(chunk_id=chunk.id, source=chunk.source, text=chunk.text)


def seed_knowledge(db):
    for path in (ROOT / "knowledge").glob("*.txt"):
        for chunk in chunk_text(path.read_text(), path.stem, path.name):
            if db.get(ChunkRecord, chunk["id"]) is None:
                db.add(ChunkRecord(**chunk, job_profile_id=None, embedding=None))
    db.commit()


# The installed PostgreSQL column is vector(1024). Other provider dimensions stay
# in JSON and use the same cosine metric in Python; never cast them into that column.
PGVECTOR_DIMENSIONS = 1024
MAX_EMBEDDING_DIMENSIONS = 65536
EMBEDDING_BATCH_SIZE = 16


def invalidate_embeddings(db) -> None:
    """Clear caches locally; the caller owns the commit. No provider is contacted."""
    db.execute(update(ChunkRecord).values(embedding=None))
    if db.bind.dialect.name == "postgresql":
        db.execute(text("UPDATE source_chunks SET embedding_vector = NULL"))
    db.flush()


def embedding_provider(settings: Settings) -> str:
    # Include credential identity because some gateways route the same model name
    # to different models per account. Only the digest is persisted, never the key.
    identity = [
        settings.embedding_base_url.rstrip("/"),
        settings.embedding_model,
        settings.embedding_api_key,
    ]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def validated_vector(value, dimensions: int | None = None) -> list[float]:
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= MAX_EMBEDDING_DIMENSIONS
        or (dimensions is not None and len(value) != dimensions)
        or any(type(v) not in (int, float) for v in value)
    ):
        raise ValueError("Embedding service returned an invalid vector shape")
    try:
        vector = [float(v) for v in value]
        norm = math.hypot(*vector)
    except OverflowError as error:
        raise ValueError("Embedding service returned an invalid vector value") from error
    if not all(math.isfinite(v) for v in vector) or not math.isfinite(norm) or norm == 0:
        raise ValueError("Embedding service returned an invalid vector value")
    # Normalization preserves cosine similarity and prevents float32 overflow in
    # PostgreSQL as well as large intermediate products in the Python fallback.
    return [v / norm for v in vector]


def cached_vector(chunk: ChunkRecord, provider: str, dimensions: int) -> list[float] | None:
    metadata = chunk.embedding
    if not isinstance(metadata, dict) or metadata.get("provider") != provider:
        return None  # Old untagged arrays have unknown provenance and must be rebuilt.
    if type(metadata.get("dimensions")) is not int or metadata["dimensions"] != dimensions:
        return None
    try:
        return validated_vector(metadata.get("vector"), dimensions)
    except ValueError:
        return None


async def embed(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    headers = (
        {"Authorization": f"Bearer {settings.embedding_api_key}"}
        if settings.embedding_api_key
        else {}
    )
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.post(
            f"{settings.embedding_base_url}/embeddings",
            headers=headers,
            json={"model": settings.embedding_model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or len(data) != len(texts):
        raise ValueError("Embedding service returned an invalid batch")
    indices = [item.get("index") if isinstance(item, dict) else None for item in data]
    if any(type(i) is not int for i in indices) or sorted(indices) != list(range(len(texts))):
        raise ValueError("Embedding service returned invalid batch indices")
    vectors = []
    for item in sorted(data, key=lambda item: item["index"]):
        vectors.append(
            validated_vector(item.get("embedding"), len(vectors[0]) if vectors else None)
        )
    return vectors


def store_vectors(db, chunks: list[ChunkRecord], vectors: list[list[float]], provider: str):
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = {
            "provider": provider,
            "dimensions": len(vector),
            "vector": vector,
            "pgvector": False,
        }
    db.flush()
    if db.bind.dialect.name != "postgresql":
        return
    try:
        # Optional acceleration must not abort the caller's transaction. JSON
        # remains usable even if the pgvector extension/index is unavailable.
        with db.begin_nested():
            for chunk, vector in zip(chunks, vectors, strict=True):
                if len(vector) == PGVECTOR_DIMENSIONS:
                    db.execute(
                        text(
                            "UPDATE source_chunks SET embedding_vector = CAST(:v AS vector) WHERE id = :id"
                        ),
                        {"id": chunk.id, "v": json.dumps(vector)},
                    )
                else:
                    db.execute(
                        text("UPDATE source_chunks SET embedding_vector = NULL WHERE id = :id"),
                        {"id": chunk.id},
                    )
    except SQLAlchemyError:
        return
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) == PGVECTOR_DIMENSIONS:
            chunk.embedding = {**chunk.embedding, "pgvector": True}
    db.flush()


async def index_chunks(
    db, chunks: list[ChunkRecord], settings: Settings, *, dimensions: int | None = None
) -> bool:
    if not settings.embedding_base_url or not chunks:
        return False
    # Fetch and validate the entire requested set before replacing any cache rows.
    # A provider changing dimensions mid-batch cannot leave a mixed index behind.
    vectors = []
    try:
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = await embed(
                [c.text for c in chunks[start : start + EMBEDDING_BATCH_SIZE]], settings
            )
            dimensions = dimensions if dimensions is not None else len(batch[0])
            if any(len(vector) != dimensions for vector in batch):
                raise ValueError("Embedding dimensions changed between requests")
            vectors.extend(batch)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return False
    store_vectors(db, chunks, vectors, embedding_provider(settings))
    return True


def cosine_ranking(
    vector: list[float], candidates: list[tuple[ChunkRecord, list[float]]]
) -> list[str]:
    scores = [
        (sum(a * b for a, b in zip(vector, cached, strict=True)), chunk.id)
        for chunk, cached in candidates
    ]
    return [key for _, key in sorted(scores, reverse=True)[:12]]


async def retrieve(
    db, profile_id: str, query: str, settings: Settings, limit: int = 4
) -> list[Citation]:
    if limit <= 0:
        return []
    chunks = list(
        db.scalars(
            select(ChunkRecord).where(
                or_(ChunkRecord.job_profile_id == profile_id, ChunkRecord.job_profile_id.is_(None))
            )
        )
    )
    if not chunks:
        return []
    by_id = {c.id: c for c in chunks}
    rankings = [lexical_ranking(query, chunks)]
    if db.bind.dialect.name == "postgresql":
        # OR semantics: long answer/title queries rarely share every token with one passage.
        query_terms = list(dict.fromkeys(tokens(query)))[:64]
        tsquery = " | ".join(query_terms) or "voxprepnomatch"
        try:
            with db.begin_nested():
                rows = (
                    db.execute(
                        text("""SELECT id FROM source_chunks
                    WHERE (job_profile_id = :profile OR job_profile_id IS NULL)
                    AND to_tsvector('simple', text) @@ to_tsquery('simple', :query)
                    ORDER BY ts_rank(to_tsvector('simple', text), to_tsquery('simple', :query)) DESC LIMIT 12"""),
                        {"profile": profile_id, "query": tsquery},
                    )
                    .scalars()
                    .all()
                )
            if rows:
                rankings.append([key for key in rows if key in by_id])
        except SQLAlchemyError:
            pass
    if settings.embedding_base_url:
        try:
            vector = (
                await embed(
                    ["Instruct: Retrieve passages supporting interview coaching.\nQuery: " + query],
                    settings,
                )
            )[0]
            provider = embedding_provider(settings)
            missing = [c for c in chunks if cached_vector(c, provider, len(vector)) is None]
            if missing:
                # Only this profile and shared knowledge are sent to the selected
                # provider, on an explicit retrieval operation rather than settings save.
                await index_chunks(db, missing, settings, dimensions=len(vector))
            candidates = [
                (c, cached)
                for c in chunks
                if (cached := cached_vector(c, provider, len(vector))) is not None
            ]
            ids = cosine_ranking(vector, candidates)
            if (
                db.bind.dialect.name == "postgresql"
                and len(vector) == PGVECTOR_DIMENSIONS
                and candidates
                and all(c.embedding.get("pgvector") is True for c, _ in candidates)
            ):
                try:
                    with db.begin_nested():
                        ids = (
                            db.execute(
                                text("""SELECT id FROM source_chunks WHERE
                            (job_profile_id = :profile OR job_profile_id IS NULL)
                            AND embedding_vector IS NOT NULL
                            AND embedding ->> 'provider' = :provider
                            AND embedding ->> 'dimensions' = '1024'
                            AND embedding ->> 'pgvector' = 'true'
                            ORDER BY embedding_vector <=> CAST(:vector AS vector) LIMIT 12"""),
                                {
                                    "profile": profile_id,
                                    "provider": provider,
                                    "vector": json.dumps(vector),
                                },
                            )
                            .scalars()
                            .all()
                        )
                except SQLAlchemyError:
                    pass  # The precomputed Python cosine ranking is still valid.
            if ids:
                rankings.append([key for key in ids if key in by_id])
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
    selected = reciprocal_rank_fusion(rankings)[:12]
    if settings.reranker_base_url and selected:
        try:
            headers = (
                {"Authorization": f"Bearer {settings.reranker_api_key}"}
                if settings.reranker_api_key
                else {}
            )
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.post(
                    f"{settings.reranker_base_url}/rerank",
                    headers=headers,
                    json={
                        "model": settings.reranker_model,
                        "query": query,
                        "documents": [by_id[key].text for key in selected],
                        "top_n": min(limit, len(selected)),
                    },
                )
                response.raise_for_status()
                payload = response.json()
                results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list) or not 1 <= len(results) <= len(selected):
                raise ValueError("Invalid reranking results")
            seen = set()
            for item in results:
                if not isinstance(item, dict):
                    raise ValueError("Invalid reranking result")
                index, score = item.get("index"), item.get("relevance_score")
                if (
                    type(index) is not int
                    or not 0 <= index < len(selected)
                    or index in seen
                    or type(score) not in (int, float)
                    or not math.isfinite(score)
                ):
                    raise ValueError("Invalid reranking index or score")
                seen.add(index)
            reranked = [
                selected[x["index"]]
                for x in sorted(results, key=lambda x: x["relevance_score"], reverse=True)
            ]
            # Some providers return fewer than top_n; retain valid supporting
            # passages after those results rather than silently discarding them.
            selected = reranked + [key for key in selected if key not in reranked]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            pass
    return [citation(by_id[key]) for key in selected[:limit]]
