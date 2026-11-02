"""Create local interview records and PostgreSQL hybrid retrieval indexes."""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("competencies", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
    )
    op.create_table(
        "source_chunks",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column(
            "job_profile_id",
            sa.String(64),
            sa.ForeignKey("job_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
    )
    op.create_index("ix_source_chunks_job_profile_id", "source_chunks", ["job_profile_id"])
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "job_profile_id", sa.String(64), sa.ForeignKey("job_profiles.id"), nullable=False
        ),
        sa.Column("role_title", sa.String(160), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
    )
    op.create_index("ix_sessions_job_profile_id", "sessions", ["job_profile_id"])
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"])
    op.create_table(
        "turns",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.JSON(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE source_chunks ADD COLUMN embedding_vector vector(1024)")
        op.execute(
            "CREATE INDEX source_chunks_embedding_hnsw ON source_chunks USING hnsw (embedding_vector vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX source_chunks_text_gin ON source_chunks USING gin (to_tsvector('simple', text))"
        )


def downgrade():
    op.drop_table("turns")
    op.drop_table("sessions")
    op.drop_table("source_chunks")
    op.drop_table("job_profiles")
