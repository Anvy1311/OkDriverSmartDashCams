import os
import tempfile
from pathlib import Path

_test_db = Path(tempfile.gettempdir()) / f"okdriver-test-{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"
os.environ["SIMULATOR_ENABLED"] = "false"
os.environ["HEARTBEAT_ENABLED"] = "false"
os.environ["HEARTBEAT_INTERVAL_SECONDS"] = "3600"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-for-local-prototype"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    if _test_db.exists():
        _test_db.unlink()
