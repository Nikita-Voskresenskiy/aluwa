"""add some new columns

Revision ID: 9f3af74762c8
Revises: 819c311b721a
Create Date: 2025-07-01 15:23:46.953501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2 # add geoalchemy to the migration file


# revision identifiers, used by Alembic.
revision: str = '9f3af74762c8'
down_revision: Union[str, Sequence[str], None] = '819c311b721a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('locations', sa.Column('speed_mps', sa.Float(), nullable=True))
    op.add_column('track_sessions', sa.Column('distance_m_total', sa.Float(), nullable=True))
    op.add_column('track_sessions', sa.Column('speed_mps_max', sa.Float(), nullable=True))
    op.add_column('track_sessions', sa.Column('speed_mps_average', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('track_sessions', 'speed_mps_average')
    op.drop_column('track_sessions', 'speed_mps_max')
    op.drop_column('track_sessions', 'distance_m_total')
    op.drop_column('locations', 'speed_mps')
    # ### end Alembic commands ###
