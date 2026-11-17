from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_programmatic_migration_uses_supplied_connection_not_environment(tmp_path, monkeypatch):
    # This invalid ambient URL would fail if env.py opened a second engine.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused@127.0.0.1:1/unwanted")
    engine = create_engine(f"sqlite:///{tmp_path}/selected.db")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert "report_data" in {
            column["name"] for column in inspect(connection).get_columns("sessions")
        }
    engine.dispose()


def test_interviewer_migration_preserves_existing_sessions_and_defaults_to_alex(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text("INSERT INTO job_profiles VALUES ('job', 'Legacy role', '[]', '[]')")
        )
        connection.execute(
            text("""INSERT INTO sessions
            (id, job_profile_id, role_title, language, difficulty, question_count, state,
             created_at, provider, version_id, report_data)
            VALUES ('saved', 'job', 'Legacy role', 'zh-HK', 'standard', 3, 'paused',
                    '2026-11-18', 'demo', 1, '{"summary":"saved report"}')""")
        )
        connection.execute(
            text("""INSERT INTO turns
            (id, session_id, position, question, answer, created_at)
            VALUES ('turn', 'saved', 0, '{"text":"saved question"}',
                    '{"transcript":"saved answer"}', '2026-11-18')""")
        )
        original_session = connection.execute(text("SELECT * FROM sessions")).mappings().one()
        original_turn = connection.execute(text("SELECT * FROM turns")).mappings().one()
        command.upgrade(config, "head")
        upgraded = dict(connection.execute(text("SELECT * FROM sessions")).mappings().one())
        assert upgraded.pop("interviewer") == "alex"
        assert upgraded == original_session
        assert connection.execute(text("SELECT * FROM turns")).mappings().one() == original_turn
        columns = {column["name"]: column for column in inspect(connection).get_columns("sessions")}
        assert columns["interviewer"]["nullable"] is False
        assert columns["interviewer"]["default"] == "'alex'"
    engine.dispose()
