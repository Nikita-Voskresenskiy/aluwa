"""check primary key

Revision ID: c10031ea57e4
Revises: efaab7385454
Create Date: 2025-07-29 20:59:44.837199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 # add geoalchemy to the migration file


# revision identifiers, used by Alembic.
revision: str = 'c10031ea57e4'
down_revision: Union[str, Sequence[str], None] = 'efaab7385454'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # First clean up any existing duplicates
    op.execute("""
        DELETE FROM locations 
        WHERE ctid NOT IN (
            SELECT min(ctid) 
            FROM locations 
            GROUP BY track_id, custom_timestamp
        )
    """)

    # Then create the primary key constraint
    op.create_primary_key(
        'pk_locations',
        'locations',
        ['track_id', 'custom_timestamp']
    )


def downgrade():
    # Remove the primary key constraint
    op.drop_constraint(
        'pk_locations',
        'locations',
        type_='primary'
    )