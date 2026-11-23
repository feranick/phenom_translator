"""profile.py — the machine profile: what this XL can do and the limits a person has set.

Three layers, as in ls6t:
  - DEFAULT: cautious limits and the values measured on the XL on 2026-11-23 (planning.md), used until a person
    reviews a profile;
  - propose(discovery): a proposal built from `phnt instrument discover` (ranges, presets, EDX geometry, licenses,
    holder) on top of the current profile's limits, written to profile.proposed.json for a person to read and edit;
  - import_file(): the edited proposal, checked and marked reviewed (a person only: the CLI, never the LLM).

Until a profile is reviewed, phnt can read the instrument and validate studies, but (from phase 2) it does not
switch the beam on for a study.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
from pathlib import Path

from . import config, store

DEFAULT = {
    "reviewed": False,
    "reviewed_at": None,
    "source": "default",
    "instrument": {"model": "Phenom XL", "instrument_id": None, "holder_type": 100, "holder": "XlManualHeight",
                   "features": ["XL 100 x 100 mm stage"]},
    "ranges": {  # what the instrument can do (discovery); limits below are what phnt may do
        "kv": [4.8, 20.5], "spot": [0.0, 5.8], "wd_mm": [1.0, 60.0], "hfw_um": [2.47, 877.0],
        "stage_x_mm": [-50.0, 50.0], "stage_y_mm": [-50.0, 50.0], "image_px_max": 2048,
        "live_view_px": [960, 540]},
    "limits": {  # set by a person
        "kv_max": 15.0, "kv_max_sensitive": 10.0,
        "spot_max": 5.1, "spot_max_sensitive": 3.3,
        "max_move_mm": 10.0,          # stage, from the home spot
        "frames_max": 64, "dwell_us_max": 100.0,
        "eds_live_s_max": 10.0,       # one spectrum: a spectrum cannot be stopped early (Q19)
        "eds_points_max": 4096,
        "montage_tiles_max": 400,
        "series_count_max": 500,
        "study_minutes_max": 60.0,      # one study (refused above)
        "request_minutes_max": 120.0},  # a whole request (warned above: the instrument is held that long)
    "presets": {
        "kv": {"AllMaterials": 5.3, "HighResolution": 10.0, "Analysis": 15.0},
        "spot": {"Low": 2.1, "Image": 3.3, "Point": 4.3, "Map": 5.1},
        "emission_ua": {"Nominal": 40.3, "Low": 20.0},
        "pressure_pa": {"High": 60.0, "Medium": 10.0, "Low": 0.1}},
    "edx": {"takeoff_deg": 28.5, "wd_optimal_mm": [4.5, 10.0], "wd_acceptable_mm": [3.0, 12.0],
            "detector": "Ametek Dp5, window C2, 25 mm2", "enabled": True,
            "energy_correction_ev": {}},   # per "kV": measured by an EDS calibration study (phase 4)
    "licenses": {"Spectroscopy": False, "Stitching": False, "ParticleMetric": False,
                 "RoughnessReconstruction": False, "AsbestosDetection": False, "LiveVideo": False,
                 "FastSpectrum": False, "EdsMap": False, "ResolutionMeasurement": False},
    "timing": {  # seconds; 'measured' ones from docs/discovery, 'assumed' until TESTING.md measures them
        "image_overhead_s": 0.1, "dwell_default_us": 0.32,
        "eds_overhead_s": 0.07, "eds_real_per_live": 1.2, "spot_move_s": 0.03,
        "stage_mm_per_s": 5.0, "stage_settle_s": 0.5, "autofocus_s": 3.0, "navcam_s": 2.0,
        "standby_to_operational_s": 30.0},
    "timing_source": {"image_overhead_s": "measured", "dwell_default_us": "measured (512x512x2 in 0.17 s)",
                      "eds_overhead_s": "measured", "eds_real_per_live": "measured", "spot_move_s": "measured",
                      "stage_mm_per_s": "assumed", "stage_settle_s": "assumed", "autofocus_s": "assumed",
                      "navcam_s": "assumed", "standby_to_operational_s": "instrument property"},
}

# keys only a person changes, and the bounds a value must stay within
LIMIT_BOUNDS = {"kv_max": (4.8, 20.5), "kv_max_sensitive": (4.8, 20.5), "spot_max": (0.0, 5.8),
                "spot_max_sensitive": (0.0, 5.8), "max_move_mm": (0.0, 50.0), "frames_max": (1, 256),
                "dwell_us_max": (0.05, 1000.0), "eds_live_s_max": (0.1, 120.0), "eds_points_max": (1, 100000),
                "montage_tiles_max": (1, 10000), "series_count_max": (1, 100000),
                "study_minutes_max": (1.0, 1440.0), "request_minutes_max": (1.0, 1440.0)}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    """The profile in use: the saved one on top of DEFAULT (new keys get their defaults), or DEFAULT."""
    saved = store.read_json(config.profile_path())
    return _merge(DEFAULT, saved) if saved else copy.deepcopy(DEFAULT)


def save(p: dict) -> dict:
    return store.write_json(config.profile_path(), p)


def proposed_path() -> Path:
    return config.profile_path().with_name("profile.proposed.json")


def propose(discovery: dict) -> dict:
    """A profile from a discovery (adapter.discover()) on top of the current profile; written next to the
    profile as profile.proposed.json. Limits are kept, except where the instrument's range is narrower."""
    p = load()
    p["reviewed"], p["reviewed_at"], p["source"] = False, None, "proposed from discovery"
    p["proposed_at"] = _now()
    d = discovery or {}
    h = d.get("holder") or {}
    p["instrument"].update({k: v for k, v in {"holder_type": h.get("type"), "holder": h.get("type_name"),
                                              "features": d.get("features")}.items() if v is not None})
    r = p["ranges"]
    if (ht := d.get("high_tension")) and ht.get("range_kv"):
        r["kv"] = [round(x, 2) for x in ht["range_kv"]]
    if (sp := d.get("spot")) and sp.get("range"):
        r["spot"] = list(sp["range"])
    if (wd := d.get("wd")) and wd.get("range_m"):
        r["wd_mm"] = [round(x * 1e3, 3) for x in wd["range_m"]]
    if (hf := d.get("hfw")) and hf.get("range_m"):
        r["hfw_um"] = [round(x * 1e6, 3) for x in hf["range_m"]]
        p.setdefault("notes", []).append("hfw range depends on the WD at discovery time")
    if (st := d.get("stroke")) and st.get("x_m"):
        r["stage_x_mm"] = [round(x * 1e3, 3) for x in st["x_m"]]
        r["stage_y_mm"] = [round(x * 1e3, 3) for x in st["y_m"]]
    if (vm := d.get("viewing_mode")) and vm.get("size_px"):
        r["live_view_px"] = list(vm["size_px"])
    if d.get("licenses"):
        p["licenses"].update(d["licenses"])
    props = d.get("properties") or {}
    _presets_from_properties(p, props)
    lim = p["limits"]
    lim["kv_max"] = min(lim["kv_max"], r["kv"][1])
    lim["spot_max"] = min(lim["spot_max"], r["spot"][1])
    store.write_json(proposed_path(), p)
    return p


def _presets_from_properties(p: dict, props: dict):
    pre = p["presets"]
    for k in ("AllMaterials", "HighResolution", "Analysis"):
        if (v := props.get(f"HighTension.{k}")) is not None:
            pre["kv"][k] = round(abs(v) / 1000.0, 3)
    for k in ("Low", "Image", "Point", "Map"):
        if (v := props.get(f"SpotSize.{k}")) is not None:
            pre["spot"][k] = v
    for k in ("Nominal", "Low"):
        if (v := props.get(f"EmissionCurrent.{k}")) is not None:
            pre["emission_ua"][k] = round(v * 1e6, 3)
    for k in ("High", "Medium", "Low"):
        if (v := props.get(f"SamplePressure.{k}")) is not None:
            pre["pressure_pa"][k] = v
    e = p["edx"]
    if (v := props.get("EDX.TakeOffAngle")) is not None:
        e["takeoff_deg"] = v
    lo, hi = props.get("EDX.WdOptimalLowerBound"), props.get("EDX.WdOptimalUpperBound")
    if lo is not None and hi is not None:
        e["wd_optimal_mm"] = [round(lo * 1e3, 3), round(hi * 1e3, 3)]
    lo, hi = props.get("EDX.WdAcceptableLowerBound"), props.get("EDX.WdAcceptableUpperBound")
    if lo is not None and hi is not None:
        e["wd_acceptable_mm"] = [round(lo * 1e3, 3), round(hi * 1e3, 3)]
    det = [props.get(k) for k in ("EDX.Detector.Manufacturer", "EDX.Detector.Type")]
    if all(det):
        win, area = props.get("EDX.Detector.Window"), props.get("EDX.Detector.SurfaceArea")
        e["detector"] = f"{det[0]} {det[1]}" + (f", window {win}" if win else "") + \
            (f", {area * 1e6:.0f} mm2" if area else "")


def check(p: dict) -> list:
    """Errors that make a profile unusable (each says the fix)."""
    errors = []
    lim = p.get("limits") or {}
    for k, (lo, hi) in LIMIT_BOUNDS.items():
        v = lim.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            errors.append(f"limits.{k} must be a number ({lo} … {hi})")
        elif not lo <= v <= hi:
            errors.append(f"limits.{k} = {v} is outside {lo} … {hi}")
    r = p.get("ranges") or {}
    if lim.get("kv_max") and r.get("kv") and lim["kv_max"] > r["kv"][1]:
        errors.append(f"limits.kv_max {lim['kv_max']} is above the instrument's {r['kv'][1]} kV")
    if lim.get("kv_max_sensitive", 0) > lim.get("kv_max", 0):
        errors.append("limits.kv_max_sensitive must not exceed limits.kv_max")
    if lim.get("spot_max_sensitive", 0) > lim.get("spot_max", 0):
        errors.append("limits.spot_max_sensitive must not exceed limits.spot_max")
    return errors


def import_file(path: str | Path, who: str = "") -> dict:
    """A person's edited proposal -> the profile in use, marked reviewed. Refused with the errors if it fails check."""
    p = _merge(DEFAULT, json.loads(Path(path).read_text(encoding="utf-8")))
    errors = check(p)
    if errors:
        return {"ok": False, "errors": errors}
    p.update({"reviewed": True, "reviewed_at": _now(), "reviewed_by": who or None, "source": str(path)})
    save(p)
    return {"ok": True, "profile": str(config.profile_path()), "reviewed": True}


def set_value(key: str, value) -> dict:
    """One value by dotted key (a person, on the command line). A reviewed profile stays reviewed only if it still
    passes check()."""
    p = load()
    node = p
    parts = key.split(".")
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            return {"ok": False, "error": f"no section {part!r} in the profile"}
        node = node[part]
    node[parts[-1]] = value
    errors = check(p)
    if errors:
        return {"ok": False, "errors": errors}
    save(p)
    return {"ok": True, "key": key, "value": value}


def summary(p: dict) -> dict:
    """What study_format shows: the choices and limits, not the bookkeeping."""
    return {"reviewed": p.get("reviewed", False), "instrument": p["instrument"], "ranges": p["ranges"],
            "limits": p["limits"], "presets": p["presets"], "edx": {k: v for k, v in p["edx"].items()
                                                                     if k != "energy_correction_ev"},
            "licenses": p["licenses"]}


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")
