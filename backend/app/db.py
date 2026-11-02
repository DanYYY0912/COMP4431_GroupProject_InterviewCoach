from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def new_id() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class JobRecord(Base):
    __tablename__ = "job_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    competencies: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    chunks: Mapped[list["ChunkRecord"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class ChunkRecord(Base):
    __tablename__ = "source_chunks"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    job_profile_id: Mapped[str] = mapped_column(ForeignKey("job_profiles.id"), index=True)
    role_title: Mapped[str] = mapped_column(String(160))
    language: Mapped[str] = mapped_column(String(8))
    difficulty: Mapped[str] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(24), default="listening")
    created_at: Mapped[str] = mapped_column(String(40), default=now, index=True)
    provider: Mapped[str] = mapped_column(String(32))
    report_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    turns: Mapped[list["TurnRecord"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="TurnRecord.position"
    )
    __mapper_args__ = {"version_id_col": version_id}


class TurnRecord(Base):
    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[dict] = mapped_column(JSON)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


def make_database(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")

    return engine, sessionmaker(engine, expire_on_commit=False)
