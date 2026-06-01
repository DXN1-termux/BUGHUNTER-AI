import pytest
import os
from pathlib import Path
from slm.core.executor_guards import _QUARANTINE_FILE

@pytest.fixture(autouse=True)
def bypass_quarantine(monkeypatch):
    """Ensure quarantine file does not exist during tests to prevent locking."""
    if _QUARANTINE_FILE.exists():
        _QUARANTINE_FILE.unlink()
    # Also patch the quarantine flag location to a temporary file
    tmp_flag = Path("/tmp/pytest_quarantine.flag")
    monkeypatch.setattr("slm.core.executor_guards._QUARANTINE_FILE", tmp_flag)
    yield
    if tmp_flag.exists():
        tmp_flag.unlink()
