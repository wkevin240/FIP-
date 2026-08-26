from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_one_head_and_one_allocation_table_creator():
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend/app/db/migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    migration_files = list((root / "backend/app/db/migrations/versions").glob("*.py"))
    creators = [
        path
        for path in migration_files
        if 'create_table(\n        "supplier_payment_allocations"' in path.read_text()
    ]
    assert [path.name for path in creators] == ["0029_ap_advanced_allocations.py"]
