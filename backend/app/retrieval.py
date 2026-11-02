import json
import math
import re
from collections import Counter

import httpx
from sqlalchemy import or_, select, text

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


async def embed(texts: list[str], settings: Settings) -> list[list[float]]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{settings.embedding_base_url}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": texts,
            },
        )
        response.raise_for_status()
        data = response.json()["data"]
    vectors = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
    if len(vectors) != len(texts) or any(
        len(x) != settings.embedding_dimensions
        or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in x)
        for x in vectors
    ):
        raise ValueError("Embedding service returned an invalid vector shape")
    return vectors


async def index_chunks(db, chunks: list[ChunkRecord], settings: Settings) -> bool:
    if not settings.embedding_base_url or not chunks:
        return False
    try:
        vectors = await embed([c.text for c in chunks], settings)
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
        db.flush()
        if db.bind.dialect.name == "postgresql":
            for chunk in chunks:
                db.execute(
                    text(
                        "UPDATE source_chunks SET embedding_vector = CAST(:v AS vector) WHERE id = :id"
                    ),
                    {"id": chunk.id, "v": json.dumps(chunk.embedding)},
                )
        return True
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return False


async def retrieve(
    db, profile_id: str, query: str, settings: Settings, limit: int = 4
) -> list[Citation]:
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
        # tokens() removes tsquery operators before constructing this bounded query.
        query_terms = list(dict.fromkeys(tokens(query)))[:64]
        tsquery = " | ".join(query_terms) or "voxprepnomatch"
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
            rankings.append(list(rows))
    if settings.embedding_base_url:
        try:
            vector = (
                await embed(
                    ["Instruct: Retrieve passages supporting interview coaching.\nQuery: " + query],
                    settings,
                )
            )[0]
            if db.bind.dialect.name == "postgresql":
                ids = (
                    db.execute(
                        text("""SELECT id FROM source_chunks WHERE
                    (job_profile_id = :profile OR job_profile_id IS NULL) AND embedding_vector IS NOT NULL
                    ORDER BY embedding_vector <=> CAST(:vector AS vector) LIMIT 12"""),
                        {"profile": profile_id, "vector": json.dumps(vector)},
                    )
                    .scalars()
                    .all()
                )
            else:
                norm = math.sqrt(sum(x * x for x in vector)) or 1
                scores = []
                for chunk in chunks:
                    if chunk.embedding and len(chunk.embedding) == len(vector):
                        dot = sum(a * b for a, b in zip(vector, chunk.embedding))
                        denominator = norm * (math.sqrt(sum(x * x for x in chunk.embedding)) or 1)
                        scores.append((dot / denominator, chunk.id))
                ids = [key for _, key in sorted(scores, reverse=True)[:12]]
            if ids:
                rankings.append(list(ids))
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass  # Lexical fallback remains available and health identifies configuration.
    selected = reciprocal_rank_fusion(rankings)[:12]
    if settings.reranker_base_url and selected:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{settings.reranker_base_url}/rerank",
                    json={
                        "model": settings.reranker_model,
                        "query": query,
                        "documents": [by_id[key].text for key in selected],
                        "top_n": min(limit, len(selected)),
                    },
                )
                response.raise_for_status()
                results = response.json()["results"]
                indices = [
                    x["index"]
                    for x in sorted(results, key=lambda x: x["relevance_score"], reverse=True)
                ]
                if (
                    not indices
                    or len(set(indices)) != len(indices)
                    or any(not isinstance(i, int) or i < 0 or i >= len(selected) for i in indices)
                ):
                    raise ValueError("Invalid reranking indices")
                selected = [selected[i] for i in indices]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
    return [citation(by_id[key]) for key in selected[:limit]]
