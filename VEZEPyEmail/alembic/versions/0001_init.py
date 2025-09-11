from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mailboxes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False, server_default='INBOX'),
    )
    op.create_unique_constraint('uq_mailbox_user_name', 'mailboxes', ['user_email', 'name'])
    op.create_index('ix_mailboxes_user_email', 'mailboxes', ['user_email'])

    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('mailbox_id', sa.Integer(), sa.ForeignKey('mailboxes.id'), nullable=False),
        sa.Column('subject', sa.String(length=512), nullable=False),
        sa.Column('from_addr', sa.String(length=255), nullable=False),
        sa.Column('snippet', sa.Text(), nullable=False, server_default=''),
        sa.Column('date', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('flags', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('spam_score', sa.Float(), nullable=False, server_default='0'),
    )
    op.create_index('ix_messages_subject', 'messages', ['subject'])
    op.create_index('ix_messages_from', 'messages', ['from_addr'])


def downgrade() -> None:
    op.drop_index('ix_messages_from', table_name='messages')
    op.drop_index('ix_messages_subject', table_name='messages')
    op.drop_table('messages')
    op.drop_index('ix_mailboxes_user_email', table_name='mailboxes')
    op.drop_constraint('uq_mailbox_user_name', 'mailboxes', type_='unique')
    op.drop_table('mailboxes')
