"""Run the application's retrieval code on an isolated synthetic corpus."""

import argparse
import asyncio

from ml.dataset import read_jsonl, write_jsonl


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", default="evaluation/fixtures/retrieval_corpus.jsonl"
    )
    parser.add_argument(
        "--queries", default="evaluation/fixtures/retrieval_queries.jsonl"
    )
    parser.add_argument(
        "--output", default="evaluation/results/retrieval_observations.jsonl"
    )
    args = parser.parse_args()
    from backend.app.config import Settings
    from backend.app.db import Base, ChunkRecord, make_database
    from backend.app.retrieval import index_chunks, retrieve

    # Never modify the user's interview database. This collector deliberately
    # measures the in-memory retrieval fallback; pgvector needs its own benchmark.
    engine, factory = make_database("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = Settings(database_url="sqlite:///:memory:", _env_file=None)
    corpus = read_jsonl(args.corpus)
    queries = read_jsonl(args.queries)
    records = []
    with factory() as db:
        chunks = [
            ChunkRecord(
                id=r["id"],
                source=r["source"],
                text=r["text"],
                job_profile_id=None,
                embedding=None,
            )
            for r in corpus
        ]
        db.add_all(chunks)
        db.commit()
        indexed = await index_chunks(db, chunks, settings)
        for query in queries:
            passages = await retrieve(
                db, "evaluation", query["query"], settings, limit=5
            )
            records.append(
                {
                    **query,
                    "retrieved_ids": [p.chunk_id for p in passages],
                    "collector": "isolated_sqlite_application_retrieval",
                    "embeddings_indexed": indexed,
                    "database": "sqlite",
                    "diagnostic_only": True,
                }
            )
    engine.dispose()
    write_jsonl(args.output, records)
    print(
        f"Collected {len(records)} real retrieval outputs in {args.output}; diagnostic corpus, not assessed evidence."
    )


if __name__ == "__main__":
    asyncio.run(main())
