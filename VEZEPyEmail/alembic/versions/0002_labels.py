from alembic import op
import sqlalchemy as sa

revision = '0002_labels'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('labels', sa.String(length=255), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('messages', 'labels')
