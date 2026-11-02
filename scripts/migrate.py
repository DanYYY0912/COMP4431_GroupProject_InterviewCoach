"""Upgrade the selected database; safely adopt only known pre-migration SQLite schemas."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.app.config import Settings
from backend.app.db import Base, make_database

ROOT = Path(__file__).resolve().parents[1]


def migrate(url):
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine, _ = make_database(url)
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    # env.py uses the URL from Settings, so supply a connection to preserve this exact target.
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if (
            engine.dialect.name == "sqlite"
            and tables
            and "alembic_version" not in tables
        ):
            expected_tables = set(Base.metadata.tables)
            known = tables == expected_tables
            for name, table in Base.metadata.tables.items():
                actual = (
                    {column["name"] for column in inspector.get_columns(name)}
                    if name in tables
                    else set()
                )
                expected = set(table.columns.keys())
                if name == "sessions":
                    known = known and actual in (expected, expected - {"report_data"})
                else:
                    known = known and actual == expected
            if not known:
                raise ValueError(
                    "Unknown SQLite schema. Back up the database and request a migration review; no data was changed."
                )
            current = {c["name"] for c in inspector.get_columns("sessions")}
            command.stamp(config, "0002" if "report_data" in current else "0001")
        command.upgrade(config, "head")
    engine.dispose()


if __name__ == "__main__":
    migrate(Settings().database_url)
