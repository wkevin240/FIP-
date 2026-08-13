<%text>#</%text> 
<%text>#</%text> revision: 
<%text>#</%text> down_revision: 
<%text>#</%text> branch_labels: 
<%text>#</%text> depends_on: 

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 
down_revision: Union[str, None] = 
branch_labels: Union[str, Sequence[str], None] = 
depends_on: Union[str, Sequence[str], None] = 


def upgrade() -> None:
    


def downgrade() -> None:
    
