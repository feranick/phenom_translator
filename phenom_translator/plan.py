"""plan.py — time estimates for studies, from the profile's timing (measured on the XL where marked, assumed
elsewhere until TESTING.md measures them). From phase 2 it also turns a study into the adapter's calls.

Measured on 2026-11-23 (docs/discovery): a 512x512 image of 2 frames in ~0.17 s (dwell ~0.32 µs); an EDS spectrum
on the clear-start-poll-get path takes ~1.2 s of wall time per live second asked (the live time overshoots by ~9 %,
dead time ~9 %) plus ~0.07 s (1.26–1.28 s for 1 s; 0.66–0.70 s for 0.5 s with the spot move); moving the EDS spot
0.01–0.03 s.
"""
from __future__ import annotations

import math


def _t(prof, k):
    return float(prof["timing"][k])


def image_s(acq: dict, prof: dict) -> float:
    w, h = acq.get("size_px") or [1024, 1024]
    frames = acq.get("frames", 2)
    dwell = acq.get("dwell_us", _t(prof, "dwell_default_us")) * 1e-6
    return _t(prof, "image_overhead_s") + frames * w * h * dwell


def spectrum_s(eds: dict, prof: dict) -> float:
    live = eds.get("live_s", 2.0)
    return eds.get("repeats", 1) * (live * _t(prof, "eds_real_per_live") + _t(prof, "eds_overhead_s"))


def move_s(dist_um: float, prof: dict) -> float:
    return dist_um / 1000.0 / _t(prof, "stage_mm_per_s") + _t(prof, "stage_settle_s")


def focus_s(focus: dict, acq: dict, prof: dict) -> float:
    mode = (focus or {}).get("mode", "auto")
    if mode in ("none", "fixed_wd"):
        return 0.2
    if mode == "curve":
        steps = focus.get("steps", 21)
        return steps * (image_s({"size_px": [512, 512], "frames": 1}, prof) + 0.1)
    return _t(prof, "autofocus_s")


def hfw_um(acq: dict, prof: dict) -> float:
    if "hfw_um" in acq:
        return acq["hfw_um"]
    if "pixel_um" in acq:
        return acq["pixel_um"] * (acq.get("size_px") or [1024, 1024])[0]
    return prof["ranges"]["hfw_um"][1] / 2  # unknown until run time: a mid-range guess


def montage_grid(s: dict, prof: dict) -> tuple[int, int, tuple[float, float]]:
    """(nx, ny, (width_um, height_um)) of a montage."""
    m, acq = s.get("montage") or {}, s.get("acquire") or {}
    w_px, h_px = acq.get("size_px") or [1024, 1024]
    fw = hfw_um(acq, prof)
    fh = fw * h_px / w_px
    step_x, step_y = fw * (1 - m.get("overlap", 0.15)), fh * (1 - m.get("overlap", 0.15))
    if "tiles" in m:
        nx, ny = m["tiles"]
    else:
        aw, ah = m["area_um"]
        nx, ny = max(1, math.ceil((aw - fw) / step_x) + 1), max(1, math.ceil((ah - fh) / step_y) + 1)
    return nx, ny, (fw + (nx - 1) * step_x, fh + (ny - 1) * step_y)


def estimate(kind: str, s: dict, prof: dict) -> dict:
    acq, focus, eds = s.get("acquire") or {}, s.get("focus") or {}, s.get("eds") or {}
    parts = {}
    if kind == "image":
        pts = s.get("points") or [[0.0, 0.0]]
        prev, travel = (0.0, 0.0), 0.0
        for p in pts:
            travel += math.dist(prev, p)
            prev = p
        travel += math.dist(prev, (0.0, 0.0))
        parts["moves"] = (len(pts) + 1) * _t(prof, "stage_settle_s") + travel / 1000 / _t(prof, "stage_mm_per_s") \
            if s.get("points") else 0.0
        n_focus = _n_focus(focus, len(pts))
        parts["focus"] = n_focus * focus_s(focus, acq, prof)
        parts["images"] = len(pts) * image_s(acq, prof)
    elif kind == "navcam":
        parts["navcam"] = _t(prof, "navcam_s")
    elif kind == "move":
        m = s.get("move") or {}
        parts["move"] = move_s(math.hypot(m.get("x_um", 0.0), m.get("y_um", 0.0)), prof)
    elif kind == "focus":
        parts["focus"] = focus_s(focus, acq, prof)
    elif kind == "montage":
        nx, ny, ext = montage_grid(s, prof)
        n = nx * ny
        step = ext[0] / max(nx, 1)
        parts["moves"] = n * move_s(step, prof) + move_s(math.hypot(*ext) / 2, prof)
        parts["focus"] = _n_focus(focus, n) * focus_s(focus, acq, prof)
        parts["images"] = n * image_s(acq, prof)
        parts["stitching"] = 0.05 * n
    elif kind == "series":
        sr = s.get("series") or {}
        cnt = sr.get("count", 1)
        parts["focus"] = focus_s(focus, acq, prof) if focus.get("mode", "auto") != "none" else 0.0
        parts["images"] = cnt * max(image_s(acq, prof), sr.get("interval_s", 0.0))
    elif kind == "calibration":
        c = s.get("calibration") or {}
        t = c.get("target")
        if t == "stage_repeatability":
            parts["moves"] = 2 * c.get("repeats", 5) * move_s(500.0, prof)
            parts["images"] = (2 * c.get("repeats", 5) + 1) * image_s(acq, prof)
        elif t == "eds_energy":
            parts["spectra"] = spectrum_s(eds or {"live_s": 10, "repeats": 3}, prof)
        else:
            parts["images"] = 3 * image_s(acq, prof)
            parts["moves"] = 2 * move_s(200.0, prof)
        parts["focus"] = focus_s(focus, acq, prof)
    elif kind == "particles":
        parts["focus"] = focus_s(focus, acq, prof)
        parts["images"] = image_s(acq, prof)
        parts["analysis"] = 2.0
        if s.get("eds") is not None:
            n = (s.get("particles") or {}).get("max_particles", 200)
            parts["spectra"] = n * (spectrum_s(eds, prof) + _t(prof, "spot_move_s"))
    elif kind == "eds_point":
        n = max(len(eds.get("spots") or []), 1)
        parts["focus"] = focus_s(focus, acq, prof)
        parts["image"] = image_s(acq, prof)
        parts["spectra"] = n * (spectrum_s(eds, prof) + _t(prof, "spot_move_s"))
    elif kind == "eds_grid":
        nx, ny = (s.get("eds_grid") or {}).get("grid", [1, 1])
        parts["focus"] = focus_s(focus, acq, prof)
        parts["image"] = image_s(acq, prof)
        parts["spectra"] = nx * ny * (spectrum_s(eds, prof) + _t(prof, "spot_move_s"))
    total = sum(parts.values())
    assumed = sorted({k for k, v in prof.get("timing_source", {}).items() if str(v).startswith("assumed")})
    return {"minutes": round(total / 60.0, 2), "seconds": round(total, 1),
            "parts_s": {k: round(v, 1) for k, v in parts.items()}, "assumed_timing": assumed}


def _n_focus(focus: dict, n: int) -> int:
    mode = (focus or {}).get("mode", "auto")
    if mode in ("none",):
        return 0
    every = (focus or {}).get("every_n", 0)
    return 1 + ((n - 1) // every if every else 0)
