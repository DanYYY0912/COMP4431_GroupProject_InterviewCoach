"""Persist validated reports and invalidate them when answers change."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # 0001 initially used metadata before release. Handle those local development databases.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("sessions")}
    if "report_data" not in columns:
        op.add_column("sessions", sa.Column("report_data", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("sessions", "report_data")
