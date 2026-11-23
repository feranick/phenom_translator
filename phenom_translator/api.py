"""api.py — what the CLI and the MCP server call. Every function returns JSON-friendly data; failures that a
person can act on come back as {"ok": false, "error": "..."} instead of exceptions.
"""
from __future__ import annotations

import datetime as _dt
import importlib.metadata
import json
import platform
import time
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


WATCH_KEYS = ("instrument_mode", "operational_mode", "sem_mode", "door")


def report(watch_s: float = 0.0, every_s: float = 2.0, ppisim: bool = True, out: str | None = None) -> dict:
    """Everything a test session at the instrument needs, in one call: versions, the instrument now (and how long a
    status read takes), the profile and its proposal, PyPhenom's simulator, and with watch_s > 0 the status read
    every every_s seconds for watch_s seconds while a person uses the Phenom UI (TESTING T1, T3): every change of
    mode, door, EDS acquisition, vacuum, SED, warnings or read errors, with the time since the start. Read only.
    Writes two files: the short text (out, default PHNT_OUT/report_<time>.txt) and the full report next to it
    (.json). Returns the paths and the text."""
    started = _dt.datetime.now()
    rep = {"report": started.isoformat(timespec="seconds"), "status": tool_status()}
    try:
        a = adapter.get()
    except adapter.AdapterError as e:
        rep["instrument"] = {"ok": False, "error": str(e)}
        a = None
    if a is not None:
        t0 = time.perf_counter()
        rep["instrument"] = {"ok": True, **a.discover()}
        rep["instrument"]["read_s"] = round(time.perf_counter() - t0, 3)
    p, prop = profile.load(), store.read_json(profile.proposed_path())
    rep["profile"] = {"in_use": {"reviewed": p.get("reviewed"), "source": p.get("source"), "limits": p["limits"]},
                      "proposal": ({"proposed_at": prop.get("proposed_at"), "limits": prop.get("limits"),
                                    "differs_from_in_use": _changes(p, prop)} if prop else None)}
    if ppisim and config.mode() == "phenom" and a is not None:
        try:
            s = adapter.PhenomAdapter(simulator=True).status()
            rep["ppisim"] = {"ok": True, "read_errors": s.get("read_errors"), "summary": s.get("summary")}
        except adapter.AdapterError as e:
            rep["ppisim"] = {"ok": False, "error": str(e)}
    if a is not None and watch_s > 0:
        rep["watch"] = _watch(a, watch_s, max(every_s, 0.2))
    txt = Path(out).expanduser() if out else config.out_dir() / f"report_{started.strftime('%Y%m%d_%H%M%S')}.txt"
    js = txt.with_suffix(".json")
    txt.parent.mkdir(parents=True, exist_ok=True)
    rep["files"] = {"text": str(txt), "json": str(js)}
    rep["text"] = _report_text(rep)
    store.write_json(js, rep)
    txt.write_text(rep["text"] + "\n", encoding="utf-8")
    return {"ok": True, "files": rep["files"], "text": rep["text"]}


def _watch_key(s: dict) -> dict:
    sm = s.get("summary") or {}
    return {**{k: s.get(k) for k in WATCH_KEYS},
            "eds_acquiring": (s.get("spectrometer") or {}).get("acquiring"),
            "scan": (s.get("viewing_mode") or {}).get("scan_mode"),
            "vacuum_stable": sm.get("vacuum_stable"), "sed": sm.get("sed"),
            "warnings": s.get("warnings") or [], "read_errors": sorted((s.get("read_errors") or {}).items())}


def _watch(a, watch_s: float, every_s: float) -> dict:
    t_start, samples, changes, last = time.perf_counter(), 0, [], None
    durations, errors = [], {}
    while True:
        t = time.perf_counter() - t_start
        if t > watch_s:
            break
        t0 = time.perf_counter()
        s = a.status()
        durations.append(time.perf_counter() - t0)
        samples += 1
        for r, msg in (s.get("read_errors") or {}).items():
            key = f"{r} during {s.get('operational_mode')}"
            errors.setdefault(key, {"count": 0, "first": msg})["count"] += 1
        k = _watch_key(s)
        if k != last:
            changes.append({"t_s": round(t, 1), **k})
            last = k
        time.sleep(max(0.0, every_s - (time.perf_counter() - t0)))
    return {"seconds": watch_s, "every_s": every_s, "samples": samples,
            "read_s": {"mean": round(sum(durations) / len(durations), 3), "max": round(max(durations), 3)}
            if durations else None, "read_errors": errors, "changes": changes}


def _report_text(rep: dict) -> str:
    st, ins = rep["status"], rep.get("instrument") or {}
    pp = st.get("pyphenom") or {}
    lines = [f"phnt {st.get('translator')} | Python {st.get('python')} | mode {st.get('settings', {}).get('PHNT_MODE')}"
             f" | PyPhenom {pp.get('version') or pp.get('error') or pp.get('note')}"
             + (f" ({pp['found_by']})" if pp.get("found_by") else "")]
    if not ins.get("ok"):
        lines.append(f"INSTRUMENT: {ins.get('error')}")
    else:
        sm = ins.get("summary") or {}
        lines.append(f"NOW: {ins.get('instrument_mode')}/{ins.get('operational_mode')}, door {ins.get('door')}, "
                     f"{sm.get('kv')} kV, spot {(ins.get('spot') or {}).get('value')}, WD {sm.get('wd_mm')} mm, "
                     f"HFW {sm.get('hfw_um')} um, vacuum {'stable' if sm.get('vacuum_stable') else 'NOT stable'} "
                     f"{sm.get('pressure_pa')} Pa, SED {sm.get('sed')}, EDS "
                     f"{(ins.get('spectrometer') or {}).get('temperature_k')} K, can_image {sm.get('can_image')}")
        lines.append(f"STATUS READ: {ins.get('read_s')} s | warnings: {ins.get('warnings') or 'none'} | read errors: "
                     f"{ins.get('read_errors') or 'none'}")
    pr = rep["profile"]
    lines.append(f"PROFILE in use: reviewed {pr['in_use']['reviewed']} ({pr['in_use']['source']})"
                 + (f" | proposal of {pr['proposal']['proposed_at']}, differs: "
                    f"{list(pr['proposal']['differs_from_in_use']) or 'no'}" if pr.get("proposal") else
                    " | no proposal"))
    lim = (pr.get("proposal") or pr["in_use"]).get("limits") or {}
    lines.append("LIMITS: " + ", ".join(f"{k} {v}" for k, v in lim.items()))
    if "ppisim" in rep:
        x = rep["ppisim"]
        lines.append("PPISIM: " + (f"ok, read errors: {x.get('read_errors') or 'none'}" if x.get("ok")
                                   else f"{x.get('error')}"))
    w = rep.get("watch")
    if w:
        lines.append(f"WATCH {w['seconds']:g} s every {w['every_s']:g} s: {w['samples']} reads, read time "
                     f"{w['read_s']['mean']} s mean / {w['read_s']['max']} s max, read errors: "
                     + (", ".join(f"{k} x{v['count']} ({v['first']})" for k, v in w["read_errors"].items()) or "none"))
        for c in w["changes"]:
            lines.append(f"  +{c['t_s']:>6.1f} s  {c['instrument_mode']}/{c['operational_mode']}/{c['sem_mode']} "
                         f"scan {c['scan']}, door {c['door']}, EDS acquiring {c['eds_acquiring']}, vacuum stable "
                         f"{c['vacuum_stable']}, SED {c['sed']}"
                         + (f", warnings {c['warnings']}" if c["warnings"] else "")
                         + (f", READ ERRORS {dict(c['read_errors'])}" if c["read_errors"] else ""))
    lines.append(f"FILES: {rep['files']['text']} and {rep['files']['json']} (all details)")
    return "\n".join(lines)


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
