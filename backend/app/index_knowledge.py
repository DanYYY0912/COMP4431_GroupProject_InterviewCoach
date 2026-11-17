"""Explicitly rebuild embeddings for local knowledge and uploaded job descriptions."""

import asyncio

from sqlalchemy import select

from .config import Settings
from .db import ChunkRecord, make_database
from .inference_settings import load_saved_inference
from .retrieval import index_chunks


async def main():
    settings = load_saved_inference(Settings())
    if not settings.embedding_base_url:
        raise SystemExit("Configure an embedding service in Settings or EMBEDDING_BASE_URL first.")
    engine, sessions = make_database(settings.database_url)
    with sessions() as db:
        chunks = list(db.scalars(select(ChunkRecord)))
        for start in range(0, len(chunks), 16):
            if not await index_chunks(db, chunks[start : start + 16], settings):
                raise SystemExit("Embedding failed. Check service readiness, model and dimensions.")
            db.commit()
        print(f"Indexed {len(chunks)} source chunks.")
    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
