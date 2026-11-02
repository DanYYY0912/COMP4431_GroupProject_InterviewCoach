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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert "report_data" in {
            column["name"] for column in inspect(connection).get_columns("sessions")
        }
    engine.dispose()
