"""remove primary key start_timestamp for track session

Revision ID: 91c06e2442d9
Revises: a79a951fe69f
Create Date: 2025-07-01 15:21:12.601789

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 # add geoalchemy to the migration file


# revision identifiers, used by Alembic.
revision: str = '91c06e2442d9'
down_revision: Union[str, Sequence[str], None] = 'a79a951fe69f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # First, drop the primary key constraint if it exists
    op.drop_constraint('track_sessions_pkey', 'track_sessions', type_='primary')

    # Then recreate the primary key with just session_id
    op.create_primary_key('track_sessions_pkey', 'track_sessions', ['session_id'])

    # If you want to keep start_timestamp as a regular column (not null)
    op.alter_column('track_sessions', 'start_timestamp',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)


def downgrade():
    # To revert, first drop the primary key
    op.drop_constraint('track_sessions_pkey', 'track_sessions', type_='primary')

    # Then recreate the primary key with both columns
    op.create_primary_key('track_sessions_pkey', 'track_sessions',
                          ['session_id', 'start_timestamp'])