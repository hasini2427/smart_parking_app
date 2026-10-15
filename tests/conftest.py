import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB_VARS = ["PARKING_DB_HOST", "PARKING_DB_PORT", "PARKING_DB_USER", "PARKING_DB_PASSWORD",
           "PARKING_DB_NAME", "PARKING_DB_SSL_MODE", "PARKING_DB_SSL_CA", "PARKING_DB_SSL_CA_PEM",
           "PARKING_DB_TIME_ZONE", "PARKING_ALLOW_DB_RESET", "PARKING_DB_CONNECT_TIMEOUT"]


@pytest.fixture
def load_config(monkeypatch):
    """Reload config/db with exactly the given environment (no secrets file)."""
    def _load(**env):
        for name in DB_VARS:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        import config
        import db
        monkeypatch.setattr(config, "_from_secrets", lambda name: None, raising=False)
        importlib.reload(config)
        monkeypatch.setattr(config, "_from_secrets", lambda name: None)
        importlib.reload(db)
        return config, db
    return _load
