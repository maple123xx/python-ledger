"""Database location shared by the server and local utilities."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def database_path(override: str | Path | None = None) -> Path:
    """Use the project database unless an explicit path is supplied."""
    configured = override if override is not None else os.environ.get("LEDGER_DB")
    return Path(configured).resolve() if configured else PROJECT_DIR / "ledger.db"
