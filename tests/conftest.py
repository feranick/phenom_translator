"""Every test runs on the fake XL in its own folders (PHNT_HOME, PHNT_OUT under tmp_path)."""
import sys

import pytest

from phenom_translator import adapter


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PHNT_MODE", "fake")
    monkeypatch.setenv("PHNT_OUT", str(tmp_path / "runs"))
    monkeypatch.setenv("PHNT_HOME", str(tmp_path / "home"))
    for v in ("PHNT_PROFILE", "PHNT_MAX_MINUTES", "PHNT_PYPHENOM"):
        monkeypatch.delenv(v, raising=False)
    adapter._PPI.clear()
    yield
    adapter._PPI.clear()
    sys.modules.pop("PyPhenom", None)
