import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import UploadFile

from .config import Settings
from .db import Base, ChunkRecord, JobRecord, SessionRecord, make_database, new_id
from .ingestion import MAX_FILE_BYTES, chunk_text, extract_file, profile_metadata, validate_text
from .retrieval import index_chunks, seed_knowledge
from .schemas import (
    AnswerSubmission,
    ClientEvent,
    Control,
    Profile,
    ProfileInput,
    Session,
    SessionInput,
    SessionReport,
    SpeechConsent,
)
from .service import InterviewService, profile_view, session_view
from .speech import speech_token, transcribe


class LocalBoundary:
    """Protect the unauthenticated localhost app against foreign browser origins and huge bodies."""

    def __init__(self, app, origins: set[str]):
        self.app, self.origins = app, origins

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode()
        host = headers.get(b"host", b"").decode().split(":")[0]
        invalid = (origin and origin not in self.origins) or host not in {
            "localhost",
            "127.0.0.1",
            "testserver",
            "api",
            "[",
            "",
        }
        if invalid:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse(
                {"detail": "Only approved local origins may access this application."}, 403
            )(scope, receive, send)
        if scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH"}:
            total, parts = 0, []
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body = message.get("body", b"")
                total += len(body)
                if total > 12 * 1024 * 1024:
                    return await JSONResponse({"detail": "Request body exceeds 12 MB."}, 413)(
                        scope, receive, send
                    )
                parts.append(body)
                if not message.get("more_body", False):
                    break
            consumed = False
            original_receive = receive

            async def buffered_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": b"".join(parts), "more_body": False}
                return await original_receive()

            receive = buffered_receive
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    engine, sessions = make_database(settings.database_url)
    service = InterviewService(sessions, settings)

    @asynccontextmanager
    async def lifespan(app):
        if engine.dialect.name == "sqlite":
            Base.metadata.create_all(engine)
        with sessions() as db:
            seed_knowledge(db)
            missing = [
                chunk for chunk in db.scalars(select(ChunkRecord)) if chunk.embedding is None
            ]
            # Bound cold-start embedding work; rerun `python -m app.index_knowledge` for all sources.
            if settings.embedding_base_url and missing:
                await index_chunks(db, missing[:64], settings)
                db.commit()
        yield
        for task in list(service.active.values()):
            task.cancel()
        engine.dispose()

    app = FastAPI(title="VoxPrep HK", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.sessions, app.state.service = settings, sessions, service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(LocalBoundary, origins=settings.origins)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(
            {
                "detail": "The local database is unavailable. Restart it and retry; no answer was committed."
            },
            status_code=503,
        )

    @app.post("/api/job-profiles", response_model=Profile, status_code=201)
    async def create_profile(request: Request):
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            async with request.form(
                max_files=1, max_fields=1, max_part_size=MAX_FILE_BYTES + 1
            ) as form:
                file = form.get("file")
                if not isinstance(file, UploadFile):
                    raise HTTPException(422, "Provide one job-description file.")
                content = await file.read(MAX_FILE_BYTES + 1)
                body = await asyncio.to_thread(extract_file, file.filename or "", content)
                filename = Path(file.filename or "upload").name
                title = None
        else:
            try:
                data = ProfileInput.model_validate(await request.json())
            except (ValidationError, json.JSONDecodeError) as exc:
                detail = (
                    exc.errors(include_input=False, include_url=False)
                    if isinstance(exc, ValidationError)
                    else "Invalid JSON."
                )
                raise HTTPException(422, detail) from exc
            body, title, filename = validate_text(data.text), data.title, "Pasted job description"
        title, competencies, warnings = profile_metadata(body, title)
        with sessions() as db:
            profile = JobRecord(
                id=new_id(), title=title, competencies=competencies, warnings=warnings
            )
            profile.chunks = [
                ChunkRecord(**chunk, embedding=None)
                for chunk in chunk_text(body, profile.id, filename)
            ]
            db.add(profile)
            db.flush()
            if settings.embedding_base_url and not await index_chunks(db, profile.chunks, settings):
                profile.warnings = warnings + [
                    "Embedding service unavailable; this job uses lexical retrieval until reindexed."
                ]
            db.commit()
            return profile_view(profile)

    @app.post("/api/sessions", response_model=Session, status_code=201)
    async def create_session(data: SessionInput):
        return await service.create(data)

    @app.get("/api/sessions", response_model=list[Session])
    async def list_sessions(limit: int = 100, offset: int = 0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise HTTPException(422, "Use limit 1–100 and a nonnegative offset.")
        with sessions() as db:
            return [
                session_view(s)
                for s in db.scalars(
                    select(SessionRecord)
                    .order_by(SessionRecord.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ]

    @app.get("/api/sessions/{session_id}", response_model=Session)
    async def get_session(session_id: str):
        with sessions() as db:
            return session_view(service.get(db, session_id))

    @app.post("/api/sessions/{session_id}/answer", response_model=Session)
    async def answer(session_id: str, data: AnswerSubmission):
        try:
            return await service.answer(session_id, data)
        except asyncio.CancelledError as exc:
            raise HTTPException(
                409,
                "Answer generation was cancelled. Your draft was not submitted; retry when ready.",
            ) from exc

    @app.post("/api/sessions/{session_id}/control", response_model=Session)
    async def control(session_id: str, data: Control):
        try:
            return await service.control(session_id, data)
        except asyncio.CancelledError as exc:
            raise HTTPException(
                409, "Question generation was cancelled; the interview has not advanced."
            ) from exc

    @app.get("/api/sessions/{session_id}/report", response_model=SessionReport)
    async def report(session_id: str):
        try:
            return await service.report(session_id)
        except asyncio.CancelledError as exc:
            raise HTTPException(
                409, "Report generation was cancelled. Request it again when ready."
            ) from exc

    @app.delete("/api/sessions/{session_id}", status_code=204)
    async def delete_session(session_id: str):
        await service.delete(session_id)
        return Response(status_code=204)

    @app.post("/api/speech/token")
    async def token(data: SpeechConsent):
        return await speech_token(settings)

    @app.post("/api/speech/transcribe")
    async def speech_transcribe(request: Request):
        async with request.form(max_files=1, max_fields=1, max_part_size=10 * 1024 * 1024) as form:
            file = form.get("file")
            if not isinstance(file, UploadFile):
                raise HTTPException(422, "Provide one recorded audio file.")
            content = await file.read(10 * 1024 * 1024 + 1)
            return await transcribe(
                content,
                file.filename or "recording.wav",
                str(form.get("language", "en-HK")),
                settings,
            )

    @app.get("/api/health")
    async def health():
        database = "ready"
        indexed = total = 0
        try:
            with sessions() as db:
                db.execute(select(SessionRecord).limit(1)).first()
                total = db.scalar(text("SELECT count(*) FROM source_chunks"))
                column = "embedding_vector" if engine.dialect.name == "postgresql" else "embedding"
                indexed = db.scalar(
                    text(f"SELECT count(*) FROM source_chunks WHERE {column} IS NOT NULL")
                )
        except SQLAlchemyError:
            database = "unavailable"

        async def reachable(url):
            if not url:
                return False
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                return True
            except httpx.HTTPError:
                return False

        llm_ready, embedding_ready, reranker_ready, whisper_ready = await asyncio.gather(
            reachable(
                f"{settings.llama_base_url}/models" if settings.model_provider == "llama" else ""
            ),
            reachable(
                f"{settings.embedding_base_url}/models" if settings.embedding_base_url else ""
            ),
            reachable(f"{settings.reranker_base_url}/models" if settings.reranker_base_url else ""),
            reachable(f"{settings.whisper_base_url}/"),
        )
        llm = "demo (not a language model)"
        if settings.model_provider == "llama":
            llm = (
                "ready (local model; training provenance in model manifest)"
                if llm_ready
                else "unavailable (deterministic fallback enabled)"
            )
        speech_status = (
            "Azure configured; availability checked on use; "
            if settings.azure_speech_key and settings.azure_speech_region
            else "Azure not configured; "
        )
        speech_status += (
            "local Whisper ready"
            if whisper_ready
            else "local Whisper unavailable; typed input ready"
        )
        retrieval_status = (
            f"hybrid ready ({indexed}/{total} chunks indexed)"
            if embedding_ready and indexed
            else "lexical fallback (embeddings unavailable or not indexed)"
        )
        retrieval_status += (
            "; reranker ready" if reranker_ready else "; reranker unavailable or not configured"
        )
        return {
            "status": "ready"
            if database == "ready" and not llm.startswith("unavailable")
            else "degraded",
            "database": database,
            "llm": llm,
            "speech": speech_status,
            "retrieval": retrieval_status,
            "provider": settings.model_provider,
        }

    @app.get("/api/methodology/metrics")
    async def metrics():
        if settings.evaluation_path.exists():
            try:
                data = json.loads(settings.evaluation_path.read_text())
                if isinstance(data, dict) and isinstance(data.get("evaluations"), list):
                    return {**data, "provider": settings.model_provider}
            except (ValueError, OSError):
                pass
        return {
            "status": "not_evaluated",
            "provider": settings.model_provider,
            "training": {"status": "not_trained", "adapter_available": False},
            "evaluations": [],
            "limitations": [
                "No measured quality results have been imported.",
                "A configured base model is not a fine-tuned model.",
                "Model report evidence is validated; keyword heuristics are a disclosed fallback. Human review is required.",
            ],
        }

    @app.websocket("/api/sessions/{session_id}/live")
    async def live(websocket: WebSocket, session_id: str):
        await websocket.accept()
        try:
            with sessions() as db:
                snapshot = session_view(service.get(db, session_id))
            await websocket.send_json(
                {"version": 1, "type": "session", "payload": snapshot.model_dump()}
            )
        except HTTPException:
            await websocket.close(code=1008, reason="Session not found")
            return
        pending = None
        send_lock = asyncio.Lock()

        async def emit(kind, payload):
            async with send_lock:
                await websocket.send_json({"version": 1, "type": kind, "payload": payload})

        async def submit(data):
            try:
                await emit("state", {"state": "thinking"})
                result = await service.answer(session_id, data)
                # Validated final text only: deltas are presentation chunks, not raw unchecked JSON.
                if result.state != "completed":
                    words = result.turns[-1].question.interviewer_text
                    for start in range(0, len(words), 80):
                        await emit("text_delta", {"text": words[start : start + 80]})
                await emit("session", result.model_dump())
            except asyncio.CancelledError:
                raise
            except (HTTPException, SQLAlchemyError) as exc:
                await emit(
                    "error",
                    {
                        "message": str(exc.detail)
                        if isinstance(exc, HTTPException)
                        else "Database unavailable; please retry.",
                        "recoverable": True,
                    },
                )

        async def skip_question(data):
            try:
                await emit("state", {"state": "thinking"})
                result = await service.control(session_id, data)
                await emit("session", result.model_dump())
            except asyncio.CancelledError:
                raise
            except (HTTPException, SQLAlchemyError) as exc:
                await emit(
                    "error",
                    {
                        "message": str(exc.detail)
                        if isinstance(exc, HTTPException)
                        else "Database unavailable; please retry.",
                        "recoverable": True,
                    },
                )

        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw) > 64000:
                    await emit("error", {"message": "Message is too large.", "recoverable": True})
                    continue
                try:
                    event = TypeAdapter(ClientEvent).validate_json(raw)
                    if event.type == "answer":
                        if pending and not pending.done():
                            raise HTTPException(409, "An answer is already being processed.")
                        pending = asyncio.create_task(submit(event.payload))
                    else:
                        if event.payload.action == "skip":
                            if pending and not pending.done():
                                raise HTTPException(409, "A question is already being processed.")
                            pending = asyncio.create_task(skip_question(event.payload))
                            continue
                        if (
                            event.payload.action in {"cancel", "pause", "end"}
                            and pending
                            and not pending.done()
                        ):
                            pending.cancel()
                            try:
                                await pending
                            except asyncio.CancelledError:
                                pass
                        result = await service.control(session_id, event.payload)
                        await emit("session", result.model_dump())
                except (ValidationError, HTTPException) as exc:
                    await emit(
                        "error",
                        {
                            "message": str(exc.detail)
                            if isinstance(exc, HTTPException)
                            else "Invalid version 1 message. Check the event schema.",
                            "recoverable": True,
                        },
                    )
        except WebSocketDisconnect:
            pass
        finally:
            if pending and not pending.done():
                pending.cancel()
                try:
                    await pending
                except asyncio.CancelledError:
                    pass

    if settings.frontend_dist.is_dir():
        assets = settings.frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "API route not found.")
            candidate = (settings.frontend_dist / path).resolve()
            if candidate.is_relative_to(settings.frontend_dist.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(settings.frontend_dist / "index.html")

    return app


app = create_app()
