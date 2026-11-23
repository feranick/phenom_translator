"""format.py — the study format: one schema per block and per kind, used both to validate studies and to generate
`study_format()`, so the two cannot drift apart (ls6t's deferred refactor 3, here from the start).

A request is {name: study}; each study has a `kind` and the blocks that kind accepts. Units are in the key names
(µm, mm, kV, s). Stage positions are offsets in µm from the home spot (where the operator left the stage); the
scan centre and EDS spots are fractions of the field *width* in image axes (+x right, +y down), measured on the XL.
"""
from __future__ import annotations

import math

from . import plan

ELEMENTS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
            "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm "
            "Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf").split()
DETECTORS = ("All", "A", "B", "C", "D", "NorthSouth", "EastWest", "Sed", "Mix")


class F:
    """One field: its type, unit, default, range or choices, and what it means. lo/hi/choices may be functions of
    the profile (ranges that come from the instrument)."""

    def __init__(self, type_, doc, unit=None, default=None, lo=None, hi=None, choices=None):
        self.type, self.doc, self.unit, self.default = type_, doc, unit, default
        self.lo, self.hi, self.choices = lo, hi, choices

    def _v(self, x, prof):
        return x(prof) if callable(x) else x

    def describe(self, prof) -> dict:
        d = {"type": self.type, "doc": self.doc}
        for k in ("unit", "default"):
            if getattr(self, k) is not None:
                d[k] = getattr(self, k)
        lo, hi, ch = self._v(self.lo, prof), self._v(self.hi, prof), self._v(self.choices, prof)
        if lo is not None or hi is not None:
            d["range"] = [lo, hi]
        if ch is not None:
            d["choices"] = list(ch)
        return d

    def check(self, v, prof) -> str | None:
        lo, hi, ch = self._v(self.lo, prof), self._v(self.hi, prof), self._v(self.choices, prof)
        t = self.type
        if t == "bool":
            return None if isinstance(v, bool) else "must be true or false"
        if t == "str":
            return None if isinstance(v, str) else "must be text"
        if t == "choice":
            return None if v in ch else f"must be one of {', '.join(map(str, ch))}"
        if t in ("number", "int", "number_or_preset"):
            if t == "number_or_preset" and isinstance(v, str):
                return None if v in (ch or ()) else f"must be a number or a preset: {', '.join(ch or ())}"
            if not _num(v) or (t == "int" and not isinstance(v, int)):
                return "must be " + ("an integer" if t == "int" else "a number")
            return _range(v, lo, hi, self.unit)
        if t in ("pair", "pair_int"):
            if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(x) for x in v)):
                return "must be two numbers [x, y]" if t == "pair" else "must be two integers [x, y]"
            if t == "pair_int" and not all(isinstance(x, int) for x in v):
                return "must be two integers [x, y]"
            for x in v:
                if (e := _range(x, lo, hi, self.unit)):
                    return e
            return None
        if t == "pairs":
            if not (isinstance(v, list) and v and all(isinstance(p, (list, tuple)) and len(p) == 2
                                                      and all(_num(x) for x in p) for p in v)):
                return "must be a non-empty list of [x, y] pairs"
            return None
        if t == "elements":
            if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                return "must be a list of element symbols, e.g. [\"Ni\", \"P\", \"O\"]"
            bad = [x for x in v if x not in ELEMENTS]
            return f"unknown element symbol(s): {', '.join(bad)}" if bad else None
        if t == "expect":
            if not isinstance(v, list) or not all(isinstance(e, dict) and "quantity" in e and "value" in e for e in v):
                return "must be a list of {quantity, value, tol}"
            return None
        return None


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _range(v, lo, hi, unit) -> str | None:
    u = f" {unit}" if unit else ""
    if lo is not None and v < lo:
        return f"is {v}{u}, below the minimum {lo}{u}"
    if hi is not None and v > hi:
        return f"is {v}{u}, above the maximum {hi}{u}"
    return None


def _kv_presets(p):
    return tuple(p["presets"]["kv"])


def _spot_presets(p):
    return tuple(p["presets"]["spot"])


BLOCKS = {
    "sample": {
        "name": F("str", "the sample's name (into the results and the image data bar label)"),
        "notes": F("str", "free notes kept with the results"),
        "sensitive": F("bool", "beam-sensitive: lower kV and spot caps apply (limits.*_sensitive)", default=False),
    },
    "setup": {
        "kv": F("number_or_preset", "high tension, or a preset name", unit="kV",
                lo=lambda p: p["ranges"]["kv"][0], hi=lambda p: p["ranges"]["kv"][1], choices=_kv_presets),
        "spot": F("number_or_preset", "spot size (PyPhenom's unit), or a preset name",
                  lo=lambda p: p["ranges"]["spot"][0], hi=lambda p: p["ranges"]["spot"][1], choices=_spot_presets),
        "emission": F("choice", "emission current preset", choices=lambda p: tuple(p["presets"]["emission_ua"])),
        "charge_reduction": F("choice", "vacuum charge reduction (changes the chamber pressure; slow)",
                              choices=("Off", "Low", "High")),
        "detector": F("choice", "BSD (All, a segment, NorthSouth, EastWest), the SED, or Mix", choices=DETECTORS),
        "wd_mm": F("number", "working distance (focus)", unit="mm",
                   lo=lambda p: p["ranges"]["wd_mm"][0], hi=lambda p: p["ranges"]["wd_mm"][1]),
    },
    "acquire": {
        "size_px": F("pair_int", "image size [width, height]", unit="px", default=[1024, 1024], lo=16,
                     hi=lambda p: p["ranges"]["image_px_max"]),
        "frames": F("int", "frames averaged", default=2, lo=1, hi=lambda p: p["limits"]["frames_max"]),
        "dwell_us": F("number", "dwell time per pixel (default: the Phenom's)", unit="µs", lo=0.05,
                      hi=lambda p: p["limits"]["dwell_us_max"]),
        "hdr": F("bool", "16-bit raw image without contrast/brightness", default=False),
        "drift_correction": F("bool", "drift correction while averaging", default=False),
        "hfw_um": F("number", "horizontal field width (or pixel_um)", unit="µm",
                    lo=lambda p: p["ranges"]["hfw_um"][0], hi=lambda p: p["ranges"]["hfw_um"][1]),
        "pixel_um": F("number", "pixel size (or hfw_um)", unit="µm", lo=0.0005, hi=1000.0),
        "scan_center": F("pair", "centre of a sub-field, fractions of the field width, +x right, +y down",
                         default=[0.0, 0.0], lo=-0.5, hi=0.5),
        "scan_scale": F("number", "sub-field size as a fraction of the field", default=1.0, lo=0.01, hi=1.0),
    },
    "focus": {
        "mode": F("choice", "auto (Phenom's), fine, curve (WD sweep scored by sharpness), fixed_wd, none",
                  default="auto", choices=("auto", "fine", "curve", "fixed_wd", "none")),
        "every_n": F("int", "focus again every N points or tiles (0: once)", default=0, lo=0, hi=10000),
        "wd_mm": F("number", "the WD for fixed_wd", unit="mm", lo=lambda p: p["ranges"]["wd_mm"][0],
                   hi=lambda p: p["ranges"]["wd_mm"][1]),
        "range_mm": F("number", "half-range of the WD sweep for curve", unit="mm", default=0.3, lo=0.01, hi=5.0),
        "steps": F("int", "steps of the WD sweep for curve", default=21, lo=5, hi=201),
    },
    "points": {},  # a list of [x_um, y_um] stage offsets (checked in _check_points)
    "move": {
        "x_um": F("number", "stage offset from home, +x right", unit="µm", default=0.0),
        "y_um": F("number", "stage offset from home, +y up (stage axes)", unit="µm", default=0.0),
        "to_home": F("bool", "go back to the home spot", default=False),
        "stay": F("bool", "the new position becomes home", default=False),
    },
    "navcam": {
        "overview": F("bool", "the overview the Phenom keeps, instead of a new NavCam image", default=False),
        "size_px": F("pair_int", "NavCam image size (912 native)", unit="px", default=[912, 912], lo=16, hi=2048),
    },
    "montage": {
        "tiles": F("pair_int", "tiles [nx, ny] (or area_um)", lo=1, hi=200),
        "area_um": F("pair", "area [width, height] to cover (or tiles)", unit="µm", lo=1.0, hi=100000.0),
        "overlap": F("number", "overlap between tiles", default=0.15, lo=0.05, hi=0.5),
    },
    "series": {
        "count": F("int", "number of images", lo=1, hi=lambda p: p["limits"]["series_count_max"]),
        "interval_s": F("number", "time between image starts (0: back to back)", unit="s", default=0.0, lo=0.0,
                        hi=86400.0),
    },
    "calibration": {
        "target": F("choice", "grid (pixel size, scale, rotation), stage_repeatability (backlash moves there and "
                    "back), navcam_offset (NavCam -> SEM), eds_energy (peak positions on a known sample)",
                    choices=("grid", "stage_repeatability", "navcam_offset", "eds_energy")),
        "pitch_um": F("number", "the grid's pitch, for grid", unit="µm", lo=0.01, hi=10000.0),
        "repeats": F("int", "repeats, for stage_repeatability", default=5, lo=1, hi=100),
        "elements": F("elements", "the elements present, for eds_energy"),
    },
    "particles": {
        "threshold": F("number_or_preset", "BSD threshold (0–1 of the range) or auto", default="auto", lo=0.0,
                       hi=1.0, choices=("auto",)),
        "min_diameter_um": F("number", "smallest particle kept", unit="µm", default=1.0, lo=0.0, hi=100000.0),
        "max_particles": F("int", "at most this many (the largest first)", default=200, lo=1, hi=100000),
        "exclude_edge": F("bool", "drop particles cut by the image edge", default=True),
    },
    "eds": {
        "live_s": F("number", "live time per spectrum (a spectrum cannot be stopped early, so keep it short and "
                    "use repeats)", unit="s", default=2.0, lo=0.1, hi=lambda p: p["limits"]["eds_live_s_max"]),
        "repeats": F("int", "spectra per point, summed (also a stability check)", default=1, lo=1, hi=100),
        "elements": F("elements", "elements to look for (default: identify from the spectrum)"),
        "spots": F("pairs", "beam spots in the current field, fractions of the field width, +x right, +y down "
                   "(default: one spectrum over the scanned field)"),
    },
    "eds_grid": {
        "grid": F("pair_int", "points [nx, ny]", lo=2, hi=256),
        "area": F("pair", "the area covered, fractions of the field width [width, height] (default: the field)",
                  lo=0.01, hi=1.0),
    },
}

TOP = {"kind": "the study's kind", "images": "PNGs of the results (true/false)",
       "expect": "expected values [{quantity, value, tol}] checked after the run"}

KINDS = {
    "image": {"doc": "SEM images at the current spot or at stage `points` (µm offsets from home)",
              "blocks": ("sample", "setup", "acquire", "focus", "points"), "phase": 2},
    "navcam": {"doc": "a NavCam (optical) image, or the Phenom's overview; no beam", "blocks": ("sample", "navcam"),
               "phase": 2},
    "move": {"doc": "move the stage (backlash-corrected) to an offset from home, or home", "blocks": ("move",),
             "phase": 2},
    "focus": {"doc": "focus now (Phenom's autofocus, or a WD sweep scored by sharpness); the focus serves the "
                     "rest of the request", "blocks": ("setup", "acquire", "focus"), "phase": 2},
    "montage": {"doc": "tiles over an area, snake order, backlash-corrected moves, focus every N tiles; stitched "
                       "by phnt", "blocks": ("sample", "setup", "acquire", "focus", "montage"), "phase": 3},
    "series": {"doc": "repeated images at one spot (beam damage, drift, in-situ)",
               "blocks": ("sample", "setup", "acquire", "focus", "series"), "phase": 3},
    "calibration": {"doc": "pixel size and scale on a grid, stage repeatability, NavCam offset, EDS energy axis",
                    "blocks": ("sample", "setup", "acquire", "focus", "calibration", "eds"), "phase": 3},
    "particles": {"doc": "particles in a BSD image (sizes, shapes, positions); with an `eds` block, a spectrum on "
                         "each", "blocks": ("sample", "setup", "acquire", "focus", "particles", "eds"), "phase": 3},
    "eds_point": {"doc": "EDS spectra over the field or at spots; .msa files; peaks and element identification "
                         "(no quantification without Thermo's Spectroscopy license)",
                  "blocks": ("sample", "setup", "acquire", "focus", "eds"), "phase": 4, "eds": True},
    "eds_grid": {"doc": "a coarse element map from spot spectra on a grid (EdsMap is not licensed)",
                 "blocks": ("sample", "setup", "acquire", "focus", "eds", "eds_grid"), "phase": 4, "eds": True},
}

CONVENTIONS = [
    "A request is {name: study}; each study has a kind. Units are in the key names.",
    "Stage positions (points, move) are offsets in µm from the home spot: where the operator left the stage, or "
    "where a move with stay: true went. +x right, +y up (stage axes). At the end the stage returns home.",
    "scan_center and eds.spots are fractions of the field WIDTH in image axes: +x right, +y down (= stage −y). "
    "Valid: |x| <= 0.5, |y| <= 0.5 x height/width (±0.28 on a 16:9 field), minus half a sub-field.",
    "kV is positive (PyPhenom reports it negative); presets by name: setup.kv \"Analysis\", setup.spot \"Map\".",
    "EDS: a spectrum cannot be stopped early: keep eds.live_s short (<= limits.eds_live_s_max) and use repeats. "
    "Raw spectra, peaks and element identification only: quantification and EDS maps need Thermo licenses "
    "this XL does not have.",
    "Phase 1: studies are validated and estimated; running them arrives with phase 2 (image, navcam, move, focus).",
]

EXAMPLE = {
    "overview": {"kind": "image", "sample": {"name": "C-Ni"}, "setup": {"kv": "Analysis", "detector": "All"},
                 "acquire": {"size_px": [1024, 1024], "frames": 4, "hfw_um": 500}, "focus": {"mode": "auto"},
                 "images": True},
    "three_spots": {"kind": "eds_point", "sample": {"name": "C-Ni"}, "setup": {"kv": 15, "spot": "Map", "wd_mm": 6.3},
                    "eds": {"live_s": 2, "repeats": 2, "spots": [[0, 0], [0.2, -0.1], [-0.25, 0.15]],
                            "elements": ["C", "O", "Ni", "P"]}},
}


def study_format(prof: dict) -> dict:
    blocks = {b: ({k: f.describe(prof) for k, f in fields.items()} if fields else
                  {"(list)": {"type": "pairs", "unit": "µm", "doc": "stage offsets [[x_um, y_um], ...] from home"}})
              for b, fields in BLOCKS.items()}
    kinds = {}
    for k, d in KINDS.items():
        avail, why = available(k, prof)
        kinds[k] = {"doc": d["doc"], "keys": list(TOP) + list(d["blocks"]), "runs_from_phase": d["phase"],
                    "available": avail, **({"why_not": why} if why else {})}
    return {"kinds": kinds, "top_level_keys": TOP, "blocks": blocks, "conventions": CONVENTIONS, "example": EXAMPLE}


def available(kind: str, prof: dict) -> tuple[bool, str | None]:
    if KINDS[kind].get("eds") and not prof["edx"].get("enabled", True):
        return False, "EDS is turned off in the profile (edx.enabled)"
    return True, None


# validation -----------------------------------------------------------------------------------------------------

def validate(studies, prof: dict, max_minutes_env: float | None = None) -> dict:
    """{name: result} (the llm-translators contract). Each study is capped at limits.study_minutes_max (or
    PHNT_MAX_MINUTES, the lower); a request longer than limits.request_minutes_max in all gets a warning on each."""
    if not isinstance(studies, dict) or not studies:
        return {"_": {"ok": False, "errors": ["give the studies as {name: study}"], "warnings": []}}
    lim = prof["limits"]
    cap = lim["study_minutes_max"] if max_minutes_env is None else min(lim["study_minutes_max"], max_minutes_env)
    out = {}
    for n, s in studies.items():
        r = validate_study(n, s, prof)
        m = r.get("estimate", {}).get("minutes", 0)
        if r["ok"] and m > cap:
            r["errors"].append(f"estimated {m:g} min, above the {cap:g} min a study may take"
                               + (" (PHNT_MAX_MINUTES)" if cap == max_minutes_env else " (limits.study_minutes_max)")
                               + ": make it smaller or split it")
            r["ok"] = False
        out[n] = r
    total = round(sum(r.get("estimate", {}).get("minutes", 0) for r in out.values()), 2)
    if total > lim["request_minutes_max"]:
        for r in out.values():
            r["warnings"].append(f"the request together takes about {total:g} min (limits.request_minutes_max "
                                 f"{lim['request_minutes_max']:g}): the instrument is held that long")
    return out


def validate_study(name: str, s, prof: dict) -> dict:
    errors, warnings = [], []
    if not isinstance(s, dict):
        return {"ok": False, "errors": [f"{name}: a study must be an object with a kind"], "warnings": []}
    if not name or not all(c.isalnum() or c in "_-" for c in str(name)):
        errors.append(f"study name {name!r}: use letters, digits, _ and - (it names the study's folder)")
    kind = s.get("kind")
    if kind not in KINDS:
        return {"ok": False, "errors": errors + [f"kind {kind!r}: use one of {', '.join(KINDS)}"], "warnings": []}
    spec = KINDS[kind]
    allowed = set(TOP) | set(spec["blocks"])
    for k in s:
        if k not in allowed:
            errors.append(f"unknown key {k!r} for kind {kind}: allowed {', '.join(sorted(allowed))}")
    avail, why = available(kind, prof)
    if not avail:
        errors.append(f"kind {kind} is not available: {why}")
    for b in spec["blocks"]:
        if b not in s:
            continue
        if b == "points":
            _check_points(s[b], prof, errors)
            continue
        if not isinstance(s[b], dict):
            errors.append(f"{b} must be an object")
            continue
        for k, v in s[b].items():
            f = BLOCKS[b].get(k)
            if f is None:
                errors.append(f"unknown key {b}.{k}: allowed {', '.join(BLOCKS[b])}")
            elif (e := f.check(v, prof)):
                errors.append(f"{b}.{k} {e}")
    if "images" in s and not isinstance(s["images"], bool):
        errors.append("images must be true or false")
    if "expect" in s and (e := F("expect", "").check(s["expect"], prof)):
        errors.append(f"expect {e}")
    if not errors:
        _cross_checks(kind, s, prof, errors, warnings)
    est = plan.estimate(kind, s, prof) if not errors else {"minutes": 0}
    return {"ok": not errors, "kind": kind, "errors": errors, "warnings": warnings, "estimate": est,
            "runs_from_phase": spec["phase"]}


def _check_points(v, prof, errors):
    if not (isinstance(v, list) and v and all(isinstance(p, (list, tuple)) and len(p) == 2
                                              and all(_num(x) for x in p) for p in v)):
        errors.append("points must be a non-empty list of [x_um, y_um] stage offsets from home")
        return
    lim = prof["limits"]["max_move_mm"] * 1000.0
    for i, (x, y) in enumerate(v):
        if math.hypot(x, y) > lim:
            errors.append(f"points[{i}] = [{x}, {y}] µm is {math.hypot(x, y) / 1000:.2f} mm from home, beyond "
                          f"limits.max_move_mm {prof['limits']['max_move_mm']} mm")


def resolve_kv(v, prof):
    return prof["presets"]["kv"].get(v) if isinstance(v, str) else v


def resolve_spot(v, prof):
    return prof["presets"]["spot"].get(v) if isinstance(v, str) else v


def _cross_checks(kind, s, prof, errors, warnings):
    lim, rng = prof["limits"], prof["ranges"]
    sensitive = bool((s.get("sample") or {}).get("sensitive"))
    setup, acq, eds = s.get("setup") or {}, s.get("acquire") or {}, s.get("eds")
    if kind in ("eds_point", "eds_grid") and eds is None:
        warnings.append("no eds block: defaults apply (2 s live, one spectrum per point)")
        eds = {}
    # beam settings against the caps a person set
    if "kv" in setup:
        v = resolve_kv(setup["kv"], prof)
        cap, which = (lim["kv_max_sensitive"], "kv_max_sensitive") if sensitive else (lim["kv_max"], "kv_max")
        if v > cap:
            errors.append(f"setup.kv {v} kV is above limits.{which} = {cap} kV: lower it, or ask the maintainer")
    if "spot" in setup:
        v = resolve_spot(setup["spot"], prof)
        cap, which = (lim["spot_max_sensitive"], "spot_max_sensitive") if sensitive else (lim["spot_max"], "spot_max")
        if v > cap:
            errors.append(f"setup.spot {v} is above limits.{which} = {cap}: use a smaller spot (presets: "
                          + ", ".join(f"{k} {x}" for k, x in prof["presets"]["spot"].items()) + ")")
    if sensitive and "kv" not in setup:
        warnings.append(f"sensitive sample without setup.kv: the instrument's kV is used if within "
                        f"limits.kv_max_sensitive ({lim['kv_max_sensitive']} kV), otherwise the study stops")
    # image geometry
    if "hfw_um" in acq and "pixel_um" in acq:
        errors.append("acquire: give hfw_um or pixel_um, not both")
    size = acq.get("size_px") or BLOCKS["acquire"]["size_px"].default
    if "pixel_um" in acq:
        hfw = acq["pixel_um"] * size[0]
        lo, hi = rng["hfw_um"]
        if not lo <= hfw <= hi:
            errors.append(f"acquire.pixel_um {acq['pixel_um']} x {size[0]} px = {hfw:.1f} µm field, outside "
                          f"{lo} … {hi} µm")
    aspect = size[1] / size[0]
    sc, ss = acq.get("scan_center"), acq.get("scan_scale", 1.0)
    if sc is not None:
        mx, my = (1 - ss) / 2, (1 - ss) / 2 * aspect
        if abs(sc[0]) > mx + 1e-9 or abs(sc[1]) > my + 1e-9:
            errors.append(f"acquire.scan_center {sc} puts the sub-field outside the field: with scan_scale {ss} and "
                          f"{size[0]}x{size[1]} px, |x| <= {mx:.3f} and |y| <= {my:.3f} (fractions of the width)")
    # EDS
    if eds is not None:
        spots = eds.get("spots") or []
        live = eds.get("live_s", BLOCKS["eds"]["live_s"].default)
        if kind == "calibration" and (s.get("calibration") or {}).get("target") != "eds_energy":
            warnings.append("eds block ignored: only calibration target eds_energy uses it")
        view = rng.get("live_view_px") or [960, 540]
        a = (size[1] / size[0]) if acq.get("size_px") else view[1] / view[0]
        for i, (x, y) in enumerate(spots):
            if abs(x) > 0.5 or abs(y) > 0.5 * a + 1e-9:
                errors.append(f"eds.spots[{i}] = [{x}, {y}] is outside the field: |x| <= 0.5, |y| <= {0.5 * a:.3f} "
                              "(fractions of the field width, +y down)")
        n = max(len(spots), 1) * eds.get("repeats", 1)
        if kind == "eds_grid":
            g = (s.get("eds_grid") or {}).get("grid")
            if not g:
                errors.append("eds_grid.grid [nx, ny] is required")
            else:
                n = g[0] * g[1] * eds.get("repeats", 1)
            ar = (s.get("eds_grid") or {}).get("area")
            if ar and ar[1] > a + 1e-9:
                errors.append(f"eds_grid.area height {ar[1]} is taller than the field ({a:.3f} of the width)")
        if kind == "particles":
            n = (s.get("particles") or {}).get("max_particles", 200) * eds.get("repeats", 1)
        if n > lim["eds_points_max"]:
            errors.append(f"{n} spectra exceed limits.eds_points_max {lim['eds_points_max']}")
        if live * eds.get("repeats", 1) >= 30:
            warnings.append(f"{live * eds.get('repeats', 1):.0f} s of live time per point: fine for trace elements, "
                            "long for a survey (about 24,000 counts per live second on the C–Ni sample)")
        _check_eds_wd(setup, prof, errors, warnings)
        if sensitive and spots:
            warnings.append("spot spectra on a sensitive sample: the beam stays on each spot for the whole live time")
    # kind-specific
    if kind == "move":
        m = s.get("move") or {}
        if m.get("to_home") and ("x_um" in m or "y_um" in m):
            errors.append("move: give to_home or x_um/y_um, not both")
        d = math.hypot(m.get("x_um", 0.0), m.get("y_um", 0.0))
        if d > lim["max_move_mm"] * 1000:
            errors.append(f"move: {d / 1000:.2f} mm from home is beyond limits.max_move_mm {lim['max_move_mm']} mm")
    if kind == "montage":
        m = s.get("montage") or {}
        if ("tiles" in m) == ("area_um" in m):
            errors.append("montage: give tiles [nx, ny] or area_um [w, h] (one of them)")
        else:
            nx, ny, ext = plan.montage_grid(s, prof)
            if nx * ny > lim["montage_tiles_max"]:
                errors.append(f"montage: {nx} x {ny} = {nx * ny} tiles exceed limits.montage_tiles_max "
                              f"{lim['montage_tiles_max']}")
            if math.hypot(*ext) / 2 > lim["max_move_mm"] * 1000:
                errors.append(f"montage: its corners are {math.hypot(*ext) / 2000:.2f} mm from home, beyond "
                              f"limits.max_move_mm {lim['max_move_mm']} mm")
    if kind == "series" and "count" not in (s.get("series") or {}):
        errors.append("series.count is required")
    if kind == "calibration":
        c = s.get("calibration") or {}
        t = c.get("target")
        if not t:
            errors.append("calibration.target is required")
        if t == "grid" and "pitch_um" not in c:
            errors.append("calibration.pitch_um is required for target grid (the grid's pitch)")
        if t == "eds_energy" and not c.get("elements"):
            errors.append("calibration.elements is required for target eds_energy (what the sample contains)")


def _check_eds_wd(setup, prof, errors, warnings):
    e = prof["edx"]
    wd = setup.get("wd_mm")
    if wd is None:
        warnings.append(f"setup.wd_mm not given: the WD at run time is checked against the EDX windows "
                        f"(optimal {e['wd_optimal_mm']} mm, acceptable {e['wd_acceptable_mm']} mm)")
        return
    lo, hi = e["wd_acceptable_mm"]
    if not lo <= wd <= hi:
        errors.append(f"setup.wd_mm {wd} mm is outside the EDX-acceptable {lo} … {hi} mm: the detector does not see "
                      "the spot well there")
    elif not e["wd_optimal_mm"][0] <= wd <= e["wd_optimal_mm"][1]:
        warnings.append(f"setup.wd_mm {wd} mm is outside the EDX-optimal {e['wd_optimal_mm']} mm")
