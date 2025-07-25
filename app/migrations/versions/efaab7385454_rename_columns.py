"""rename columns

Revision ID: efaab7385454
Revises: 74ca75936791
Create Date: 2025-07-25 22:00:00.304491

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 # add geoalchemy to the migration file


# revision identifiers, used by Alembic.
revision: str = 'efaab7385454'
down_revision: Union[str, Sequence[str], None] = '74ca75936791'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Rename the table first
    op.rename_table('track_sessions', 'tracks')

    # Rename the primary key column in tracks table
    op.alter_column(
        'tracks',
        'session_id',
        new_column_name='track_id',
        existing_type=sa.Integer(),
        autoincrement=True,
        existing_nullable=False,
        existing_primary_key=True
    )

    # Rename the foreign key column in locations table
    op.alter_column(
        'locations',
        'session_id',
        new_column_name='track_id',
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_primary_key=True
    )

    # Drop and recreate the foreign key constraint with new name
    op.drop_constraint('locations_session_id_fkey', 'locations', type_='foreignkey')
    op.create_foreign_key(
        'locations_track_id_fkey',
        'locations', 'tracks',
        ['track_id'], ['track_id']
    )


def downgrade():
    # Reverse the foreign key changes first
    op.drop_constraint('locations_track_id_fkey', 'locations', type_='foreignkey')
    op.create_foreign_key(
        'locations_session_id_fkey',
        'locations', 'tracks',
        ['track_id'], ['track_id']
    )

    # Rename columns back
    op.alter_column(
        'locations',
        'track_id',
        new_column_name='session_id',
        existing_type=sa.Integer(),
        existing_nullable=False,
        existing_primary_key=True
    )

    op.alter_column(
        'tracks',
        'track_id',
        new_column_name='session_id',
        existing_type=sa.Integer(),
        autoincrement=True,
        existing_nullable=False,
        existing_primary_key=True
    )

    # Finally rename the table back
    op.rename_table('tracks', 'track_sessions')