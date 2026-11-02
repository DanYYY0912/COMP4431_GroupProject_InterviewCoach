import asyncio
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select

from .coach import generate_question, generate_report
from .db import JobRecord, SessionRecord, TurnRecord
from .retrieval import citation, retrieve
from .schemas import AnswerSubmission, Control, Profile, Session, SessionInput, SessionReport, Turn


def profile_view(record: JobRecord) -> Profile:
    return Profile(
        id=record.id,
        title=record.title,
        competencies=record.competencies,
        warnings=record.warnings,
        sources=[citation(c) for c in record.chunks],
    )


def session_view(record: SessionRecord) -> Session:
    return Session(
        id=record.id,
        job_profile_id=record.job_profile_id,
        role_title=record.role_title,
        language=record.language,
        difficulty=record.difficulty,
        question_count=record.question_count,
        state=record.state,
        current_question=len(record.turns),
        created_at=record.created_at,
        provider=record.provider,
        turns=[
            Turn(id=t.id, question=t.question, answer=t.answer, created_at=t.created_at)
            for t in record.turns
        ],
    )


class InterviewService:
    def __init__(self, sessions, settings):
        self.sessions = sessions
        self.settings = settings
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.active: dict[str, asyncio.Task] = {}

    def get(self, db, session_id: str) -> SessionRecord:
        record = db.get(SessionRecord, session_id)
        if record is None:
            raise HTTPException(404, "Interview session not found.")
        return record

    async def question(self, db, record, index, previous=None):
        profile = db.get(JobRecord, record.job_profile_id)
        query = (
            profile.title
            + " "
            + " ".join(profile.competencies)
            + (" " + previous.transcript if previous else "")
        )
        sources = await retrieve(db, profile.id, query, self.settings)
        question, provider = await generate_question(
            self.settings,
            profile.competencies,
            record.language,
            record.difficulty,
            index,
            previous,
            sources,
        )
        # Keep evidence of any fallback visible for the lifetime of the session.
        record.provider = (
            "demo-fallback" if "demo-fallback" in {record.provider, provider} else provider
        )
        return TurnRecord(position=index, question=question.model_dump(), answer=None)

    async def create(self, data: SessionInput) -> Session:
        with self.sessions() as db:
            profile = db.get(JobRecord, data.job_profile_id)
            if profile is None:
                raise HTTPException(404, "Job profile not found.")
            record = SessionRecord(
                job_profile_id=profile.id,
                role_title=profile.title,
                language=data.language,
                difficulty=data.difficulty,
                question_count=data.question_count,
                provider=self.settings.model_provider,
                state="listening",
            )
            record.turns.append(await self.question(db, record, 0))
            db.add(record)
            db.commit()
            return session_view(record)

    async def answer(self, session_id: str, data: AnswerSubmission) -> Session:
        if self.locks[session_id].locked():
            raise HTTPException(
                409, "An answer is already being processed. Wait for the current turn."
            )
        async with self.locks[session_id]:
            self.active[session_id] = asyncio.current_task()
            try:
                with self.sessions() as db:
                    record = self.get(db, session_id)
                    if record.state != "listening":
                        raise HTTPException(
                            409, "Resume the interview before submitting an answer."
                        )
                    if not record.turns or record.turns[-1].answer is not None:
                        raise HTTPException(409, "This question has already been answered.")
                    if data.turn_id is not None and data.turn_id != record.turns[-1].id:
                        raise HTTPException(
                            409,
                            "This answer belongs to a previous question. Refresh the interview state.",
                        )
                    record.turns[-1].answer = data.model_dump()
                    record.report_data = None
                    record.language = data.language
                    if len(record.turns) >= record.question_count:
                        record.state = "completed"
                    else:
                        record.turns.append(
                            await self.question(db, record, len(record.turns), data)
                        )
                        record.state = "listening"
                    record.version_id += 1
                    db.commit()
                    return session_view(record)
            finally:
                self.active.pop(session_id, None)

    async def control(self, session_id: str, data: Control) -> Session:
        if data.action in {"cancel", "pause", "end"}:
            active = self.active.get(session_id)
            if active and active is not asyncio.current_task():
                active.cancel()
                try:
                    await active
                except asyncio.CancelledError:
                    pass
        async with self.locks[session_id]:
            with self.sessions() as db:
                record = self.get(db, session_id)
                record.report_data = None
                if data.action == "retry":
                    answered = [i for i, turn in enumerate(record.turns) if turn.answer is not None]
                    if not answered:
                        raise HTTPException(409, "There is no submitted answer to retry yet.")
                    index = answered[-1]
                    del record.turns[index + 1 :]
                    record.turns[index].answer = None
                    record.state = "listening"
                elif data.action == "end":
                    record.state = "completed"
                elif record.state == "completed":
                    raise HTTPException(
                        409, "The interview is complete. Retry an answer or start a new interview."
                    )
                elif data.action == "pause":
                    record.state = "paused"
                elif data.action in {"resume", "cancel"}:
                    record.state = "listening"
                elif data.action == "skip":
                    if record.state != "listening":
                        raise HTTPException(409, "Resume the interview before skipping.")
                    if len(record.turns) >= record.question_count:
                        record.state = "completed"
                    else:
                        self.active[session_id] = asyncio.current_task()
                        try:
                            record.turns.append(await self.question(db, record, len(record.turns)))
                        finally:
                            self.active.pop(session_id, None)
                record.version_id += 1
                db.commit()
                return session_view(record)

    async def delete(self, session_id: str):
        active = self.active.get(session_id)
        if active:
            active.cancel()
            try:
                await active
            except asyncio.CancelledError:
                pass
        async with self.locks[session_id]:
            with self.sessions() as db:
                record = self.get(db, session_id)
                profile_id = record.job_profile_id
                db.delete(record)
                db.flush()
                # Once no sessions reference a job, remove its private source text too.
                if (
                    db.scalar(
                        select(SessionRecord.id)
                        .where(SessionRecord.job_profile_id == profile_id)
                        .limit(1)
                    )
                    is None
                ):
                    profile = db.get(JobRecord, profile_id)
                    if profile:
                        db.delete(profile)
                db.commit()

    async def report(self, session_id: str):
        async with self.locks[session_id]:
            with self.sessions() as db:
                record = self.get(db, session_id)
                if record.report_data:
                    return SessionReport.model_validate(record.report_data)
                session = session_view(record)
                profile = db.get(JobRecord, record.job_profile_id)
                sources_by_id = {
                    source.chunk_id: source
                    for turn in session.turns
                    for source in turn.question.citations
                }
                sources_by_id.update({chunk.id: citation(chunk) for chunk in profile.chunks})
                self.active[session_id] = asyncio.current_task()
                try:
                    result = await generate_report(
                        self.settings, session, list(sources_by_id.values())
                    )
                finally:
                    self.active.pop(session_id, None)
                record.report_data = result.model_dump()
                db.commit()
                return result
