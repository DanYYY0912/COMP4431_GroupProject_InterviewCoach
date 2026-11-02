from sqlalchemy import create_engine

from alembic import context
from app.config import Settings
from app.db import Base

config = context.config
target_metadata = Base.metadata


def migrate_connection(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate_connection(config.attributes["connection"])
else:
    engine = create_engine(Settings().database_url)
    with engine.connect() as connection:
        migrate_connection(connection)
