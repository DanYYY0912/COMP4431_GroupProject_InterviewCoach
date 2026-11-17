import sqlite3

import pytest

from scripts.migrate import migrate


def test_new_sqlite_database_gets_current_schema(tmp_path):
    path = tmp_path / "new.db"
    migrate(f"sqlite:///{path}")
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003"
        )
        assert {"report_data", "interviewer"} <= {
            row[1] for row in db.execute("PRAGMA table_info(sessions)")
        }


def test_current_metadata_database_is_adopted_without_data_loss(tmp_path):
    from backend.app.db import Base, JobRecord, SessionRecord, make_database

    path = tmp_path / "legacy.db"
    engine, sessions = make_database(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with sessions() as db:
        job = JobRecord(title="Synthetic role", competencies=[], warnings=[])
        db.add(job)
        db.flush()
        db.add(
            SessionRecord(
                job_profile_id=job.id,
                role_title=job.title,
                language="en-HK",
                difficulty="standard",
                question_count=3,
                provider="demo",
                interviewer="jamie",
            )
        )
        db.commit()
    engine.dispose()
    migrate(f"sqlite:///{path}")
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003"
        )
        assert db.execute("SELECT interviewer FROM sessions").fetchone()[0] == "jamie"


def test_unknown_legacy_schema_is_not_stamped_or_deleted(tmp_path):
    path = tmp_path / "unknown.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE precious_data (value TEXT)")
        db.execute("INSERT INTO precious_data VALUES ('keep me')")
    with pytest.raises(ValueError, match="Back up"):
        migrate(f"sqlite:///{path}")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM precious_data").fetchone()[0] == "keep me"


@pytest.mark.parametrize("with_report_cache", [False, True])
def test_historical_metadata_database_keeps_sessions_when_upgrading(
    tmp_path, with_report_cache
):
    from backend.app.db import Base, make_database

    path = tmp_path / "baseline.db"
    engine, _ = make_database(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE sessions DROP COLUMN interviewer")
        if not with_report_cache:
            db.execute("ALTER TABLE sessions DROP COLUMN report_data")
        db.execute(
            "INSERT INTO job_profiles VALUES ('job', 'Retain this role', '[]', '[]')"
        )
        db.execute(
            "INSERT INTO sessions (id,job_profile_id,role_title,language,difficulty,question_count,state,created_at,provider,version_id) VALUES ('session','job','Retain this role','en-HK','standard',3,'listening','2026-11-02T00:00:00Z','demo',1)"
        )
    migrate(f"sqlite:///{path}")
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT role_title,report_data,interviewer FROM sessions WHERE id='session'"
        ).fetchone() == ("Retain this role", None, "alex")
        assert (
            db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0003"
        )
