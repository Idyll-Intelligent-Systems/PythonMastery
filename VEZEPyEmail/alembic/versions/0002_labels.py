"""
No-op migration: labels column exists in initial migration.
"""

revision = '0002_labels'
down_revision = '0001_init'
branch_labels = None
depends_on = None

def upgrade() -> None:
	pass

def downgrade() -> None:
	pass
