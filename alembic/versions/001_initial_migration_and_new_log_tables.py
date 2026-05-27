"""Initial migration and new log tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables (including new log tables)."""

    # --- camera_logs ---
    op.create_table(
        'camera_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('camera_id', sa.Integer(), nullable=False),
        sa.Column('camera_label', sa.String(), server_default=''),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('now()')),
    )
    op.create_index('ix_camera_logs_camera_id', 'camera_logs', ['camera_id'])
    op.create_index('ix_camera_logs_event', 'camera_logs', ['event'])
    op.create_index('ix_camera_logs_timestamp', 'camera_logs', ['timestamp'])

    # --- payment_logs ---
    op.create_table(
        'payment_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('plate_number', sa.String(), nullable=False),
        sa.Column('api_url', sa.String(), nullable=True),
        sa.Column('request_payload', sa.Text(), nullable=True),
        sa.Column('response_payload', sa.Text(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('api_reachable', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('now()')),
    )
    op.create_index('ix_payment_logs_plate_number', 'payment_logs', ['plate_number'])
    op.create_index('ix_payment_logs_timestamp', 'payment_logs', ['timestamp'])

    # --- system_logs ---
    op.create_table(
        'system_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('service_name', sa.String(), nullable=False),
        sa.Column('level', sa.String(), nullable=False, server_default='INFO'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('traceback', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('now()')),
    )
    op.create_index('ix_system_logs_service_name', 'system_logs', ['service_name'])
    op.create_index('ix_system_logs_timestamp', 'system_logs', ['timestamp'])

    # --- Add composite index on entry table ---
    op.create_index('ix_entry_vehicle_status', 'entry', ['vehicle_id', 'status'])


def downgrade() -> None:
    """Drop new log tables."""
    op.drop_index('ix_entry_vehicle_status', table_name='entry')
    op.drop_table('system_logs')
    op.drop_table('payment_logs')
    op.drop_table('camera_logs')
