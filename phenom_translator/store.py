"""store.py — the small JSON files phnt remembers between sessions.

One place for where they live (PHNT_HOME on the instrument; PHNT_OUT/sim_<name> with either simulator, so practice
runs never touch the instrument's records) and how they are written (a temporary file, then an atomic replace that
is retried while Windows holds the file for a moment). A missing or unreadable file reads as empty.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import config


def path(name: str) -> Path:
    """PHNT_HOME/<name> on the instrument; PHNT_OUT/sim_<name> with a simulator."""
    return (config.out_dir() / f"sim_{name}") if config.simulated() else (config.home() / name)


def read(name: str) -> dict:
    return read_json(path(name))


def read_json(p: Path) -> dict:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write(name: str, data: dict) -> dict:
    return write_json(path(name), data)


def write_json(p: Path, data: dict) -> dict:
    """Atomic: never a half-written file for a reader (the runner, the MCP server, another app)."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    replace_retry(tmp, p)
    return data


def replace_retry(src, dst, tries: int = 100, wait_s: float = 0.02):
    """os.replace, tried again while Windows refuses it (another process, e.g. a virus scanner or a reader, has
    one of the files open for a moment)."""
    for k in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if k == tries - 1:
                raise
            time.sleep(wait_s)
