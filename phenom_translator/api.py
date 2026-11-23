"""api.py — what the CLI and the MCP server call. Every function returns JSON-friendly data; failures that a
person can act on come back as {"ok": false, "error": "..."} instead of exceptions.
"""
from __future__ import annotations

import datetime as _dt
import importlib.metadata
import json
import platform
from pathlib import Path

from . import __version__, adapter, config, profile, store
from . import format as fmt

PHASE = 1
PHASE_NOTE = ("phase 1: read the instrument, validate and estimate studies; running studies arrives with phase 2 "
              "(image, navcam, move, focus)")


def tool_status() -> dict:
    """Versions and what this machine has (the shape of the llm-translators contract): translator, the backend
    (pyphenom: {version, path} or {error}), how it runs, the settings and the profile. Does not connect to the
    microscope (`instrument status` does)."""
    out = {"translator": __version__, "phase": PHASE, "phase_note": PHASE_NOTE,
           "python": platform.python_version(), "platform": platform.platform(terse=True),
           "executor": {"kind": "local", "note": "one request at a time on the instrument PC; no SLURM"}}
    try:
        out["settings"] = config.settings()
    except ValueError as exc:
        out["settings_error"] = str(exc)
        return out
    if config.mode() == "fake":
        out["pyphenom"] = {"version": None, "note": "PHNT_MODE=fake: phnt's own XL, PyPhenom not used"}
    else:
        out["pyphenom"] = adapter.find_pyphenom()[1]
    try:
        import numpy
        out["numpy"] = numpy.__version__
    except ImportError as exc:
        out["missing"] = str(exc)
    out["mcp"] = _version_of("mcp")
    prof = profile.load()
    out["profile"] = {"path": str(config.profile_path()), "exists": config.profile_path().exists(),
                      "reviewed": prof.get("reviewed", False), "source": prof.get("source")}
    return out


def _version_of(dist: str):
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def study_format() -> dict:
    prof = profile.load()
    return {"version": __version__, **fmt.study_format(prof), "profile": profile.summary(prof),
            "status": tool_status()}


def validate(studies) -> dict:
    """{name: {ok, kind, errors, warnings, estimate, runs_from_phase}} (the llm-translators contract)."""
    return fmt.validate(studies, profile.load(), config.max_minutes_env())


def all_ok(results: dict) -> bool:
    return bool(results) and all(r.get("ok") for r in results.values())


def instrument(action: str = "status") -> dict:
    """status: every read-only value the adapter has, with a summary and warnings. discover: the same plus the
    instrument's properties, saved to the discovery folder, and a profile proposal next to the profile."""
    if action not in ("status", "discover"):
        return {"ok": False, "error": f"action {action!r}: use status or discover"}
    try:
        a = adapter.get()
        if action == "status":
            return {"ok": True, **a.status()}
        d = a.discover()
    except adapter.AdapterError as e:
        return {"ok": False, "error": str(e)}
    folder = (config.out_dir() / "sim_discovery") if config.simulated() else config.discovery_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"discovery_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    store.write_json(path, {"version": __version__, "mode": config.mode(), **d})
    before = profile.load()
    prop = profile.propose(d)
    return {"ok": True, "discovery": str(path), "proposal": str(profile.proposed_path()),
            "summary": d.get("summary"), "warnings": d.get("warnings"), "read_errors": d.get("read_errors"),
            "changes": _changes(before, prop),
            "next": "a person reviews the proposal and runs: phnt profile import " + str(profile.proposed_path())}


def _changes(a: dict, b: dict, prefix: str = "") -> dict:
    out = {}
    for k in ("ranges", "presets", "edx", "licenses", "instrument") if not prefix else b:
        va, vb = a.get(k), b.get(k)
        key = f"{prefix}{k}"
        if isinstance(va, dict) and isinstance(vb, dict):
            out.update(_changes(va, vb, key + "."))
        elif va != vb:
            out[key] = {"was": va, "proposed": vb}
    return out


def profile_show() -> dict:
    return {"path": str(config.profile_path()), "exists": config.profile_path().exists(), "profile": profile.load()}


def profile_default() -> dict:
    if config.profile_path().exists():
        return {"ok": False, "error": f"{config.profile_path()} exists: edit it, or remove it first"}
    profile.save(profile.load())
    return {"ok": True, "profile": str(config.profile_path()), "reviewed": False}


def profile_propose(discovery_file: str | None = None) -> dict:
    """A proposal from a saved discovery (the newest one by default)."""
    if discovery_file:
        path = Path(discovery_file)
    else:
        folder = (config.out_dir() / "sim_discovery") if config.simulated() else config.discovery_dir()
        files = sorted(folder.glob("discovery_*.json"))
        if not files:
            return {"ok": False, "error": "no discovery yet: run phnt instrument discover"}
        path = files[-1]
    d = store.read_json(path)
    if not d:
        return {"ok": False, "error": f"{path} is not a discovery file"}
    before = profile.load()
    prop = profile.propose(d)
    return {"ok": True, "from": str(path), "proposal": str(profile.proposed_path()), "changes": _changes(before, prop)}


def profile_import(path: str, who: str = "") -> dict:
    return profile.import_file(path, who)


def profile_set(key: str, value_json: str) -> dict:
    try:
        value = json.loads(value_json)
    except ValueError:
        value = value_json
    return profile.set_value(key, value)


def dumps(o) -> str:
    return json.dumps(o, indent=1, default=str, ensure_ascii=False)
