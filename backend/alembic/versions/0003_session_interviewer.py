"""Keep the selected interviewer with each session; existing sessions use Alex."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("sessions")}
    if "interviewer" not in columns:
        op.add_column(
            "sessions",
            sa.Column("interviewer", sa.String(16), nullable=False, server_default="alex"),
        )


def downgrade():
    op.drop_column("sessions", "interviewer")
