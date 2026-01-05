"""Initial empty migration.

This is a foundation placeholder. Actual schema migrations are expected to be
managed primarily via Supabase migrations for the MVP.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Apply migration."""
    # Intentionally empty.


def downgrade() -> None:
    """Revert migration."""
    # Intentionally empty.


