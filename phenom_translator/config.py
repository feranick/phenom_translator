"""config.py — settings (environment variables only) and the folders phnt writes to.

| Variable | Meaning | Default |
|---|---|---|
| PHNT_MODE | phenom (the XL through PyPhenom), ppisim (PyPhenom's own simulator, Windows only) or fake (phnt's pure-Python XL, any OS) | phenom |
| PHNT_HOME | profile, discovery, remembered state, the instrument lock | ~/phnt |
| PHNT_OUT | request folders | ~/phnt_runs |
| PHNT_PROFILE | the machine profile (a person edits its limits) | $PHNT_HOME/profile.json |
| PHNT_MAX_MINUTES | ceiling for one study's estimated time (overrides the profile when lower) | unset |
| PHNT_PYPHENOM | the folder holding PyPhenom.pyd, when this Python does not import it by itself (a venv, a bundled Python) | unset |

There is no variable for credentials: PyPhenom connects with the PPI license installed on the instrument PC
(`PyPhenom.Phenom()` with no arguments), and phnt never reads, stores or prints license details.
"""
from __future__ import annotations

import os
from pathlib import Path

MODES = ("phenom", "ppisim", "fake")


def _path(var: str, default: Path) -> Path:
    v = os.environ.get(var, "").strip()
    return Path(v).expanduser() if v else default


def home() -> Path:
    return _path("PHNT_HOME", Path.home() / "phnt")


def out_dir() -> Path:
    return _path("PHNT_OUT", Path.home() / "phnt_runs")


def profile_path() -> Path:
    return _path("PHNT_PROFILE", home() / "profile.json")


def discovery_dir() -> Path:
    return home() / "discovery"


def mode() -> str:
    m = os.environ.get("PHNT_MODE", "phenom").strip().lower() or "phenom"
    if m not in MODES:
        raise ValueError(f"PHNT_MODE={m!r}: use one of {', '.join(MODES)}")
    return m


def simulated() -> bool:
    """True for both simulators: their records are kept apart from the instrument's (store.path)."""
    return mode() != "phenom"


def max_minutes_env() -> float | None:
    v = os.environ.get("PHNT_MAX_MINUTES", "").strip()
    try:
        return float(v) if v else None
    except ValueError:
        return None


def pyphenom_dir() -> Path | None:
    v = os.environ.get("PHNT_PYPHENOM", "").strip()
    return Path(v).expanduser() if v else None


def settings() -> dict:
    return {"PHNT_MODE": mode(), "PHNT_HOME": str(home()), "PHNT_OUT": str(out_dir()),
            "PHNT_PROFILE": str(profile_path()), "PHNT_MAX_MINUTES": max_minutes_env(),
            "PHNT_PYPHENOM": str(pyphenom_dir()) if pyphenom_dir() else None}
