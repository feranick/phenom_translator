"""phnt EDS bring-up tests, round 2 (2026-11-23). Same conditions as eds_tests.py: live-imaging a robust sample
(the C-Ni sample is fine), nothing touched in the Phenom UI meanwhile.   py -3.12 eds_tests2.py

  Q19  a call that really stops a spectrum early (Spectrometer.Stop, then StopAcquireSpectrum + reading the
       spectrometer directly)
  Q20  the 'spot' pulse-processor preset applied before a spectrum: its calibration and count rate; the 'map'
       preset is applied again afterwards, on every path
  Q17  the cost of moving the EDS spot between points (10 points, 0.5 s each, asynchronous path)
  Q6   non-square fields: 960x540 images, full and half-size at (0, 0.25) and (0.25, 0), to register
  Q7   EdsLiveMap(phenom): constructed only, never started

Changes: the viewing mode (spot mode, restored on every path) and the pulse-processor preset (map preset restored).
No stage moves, no kV / spot / vacuum / detector changes. Writes eds_tests2_<time>/; send the folder.
"""
import json
import time
from pathlib import Path

import PyPhenom as ppi

OUT = Path(f"eds_tests2_{time.strftime('%Y%m%d_%H%M%S')}")
OUT.mkdir()
LOG = open(OUT / "log.txt", "w", encoding="utf-8")
RESULTS = {}


def say(*parts):
    msg = " ".join(str(x) for x in parts)
    print(msg)
    LOG.write(msg + "\n")
    LOG.flush()


def plain(o, depth=2):
    if o is None or isinstance(o, (bool, float, str)):
        return o
    if isinstance(o, int):
        return o if type(o) is int else str(o)
    if isinstance(o, (list, tuple)):
        return [plain(x, depth) for x in o[:64]]
    if depth <= 0:
        return str(o)
    out = {}
    for name in dir(o):
        if name.startswith("_"):
            continue
        try:
            value = getattr(o, name)
        except Exception as e:
            out[name] = f"<error {e!r}>"
            continue
        if not callable(value):
            out[name] = plain(value, depth - 1)
    return out or str(o)


def step(name, fn):
    say(f"\n== {name}")
    t0 = time.perf_counter()
    try:
        result = fn()
        RESULTS[name] = {"ok": True, "s": round(time.perf_counter() - t0, 3), "result": result}
        say(f"   ok ({RESULTS[name]['s']} s): {json.dumps(result, default=str)[:600]}")
    except Exception as e:
        RESULTS[name] = {"ok": False, "s": round(time.perf_counter() - t0, 3), "error": repr(e)}
        say(f"   FAILED: {e!r}")


def spectrum_record(name, spec, meta=None):
    data = list(spec.data)
    rec = {"offset": spec.offset, "dispersion": spec.dispersion, "bins": len(data), "counts": spec.counts}
    if meta is not None:
        rec["metadata"] = plain(meta)
    (OUT / f"{name}.json").write_text(json.dumps({**rec, "data": data}, default=str), encoding="utf-8")
    return rec


def async_spectrum(name, seconds):
    t0 = time.perf_counter()
    p.StartAcquireSpectrum(seconds, ppi.EdsTimeType.LiveTime)
    while p.IsAcquiringSpectrum():
        time.sleep(0.05)
    eds = p.GetSpectrum()
    rec = spectrum_record(name, eds.spectrum, eds.metadata)
    rec["wall_s"] = round(time.perf_counter() - t0, 3)
    return rec


def set_spot(x, y):
    vm = p.GetSemViewingMode()
    sp = vm.scanParams
    sp.center = ppi.Position(x, y)
    vm.scanParams = sp
    vm.scanMode = ppi.ScanMode.Spot
    p.SetSemViewingMode(vm)


# Q19 -----------------------------------------------------------------------------------------------------------
def stop_via_spectrometer():
    p.StartAcquireSpectrum(5.0, ppi.EdsTimeType.AcquisitionTime)
    time.sleep(1.5)
    t0 = time.perf_counter()
    p.Spectrometer.Stop()
    stop_s = round(time.perf_counter() - t0, 3)
    time.sleep(0.2)
    rec = {"stop_call_s": stop_s, "acquiring_after": p.IsAcquiringSpectrum(),
           "status_after": plain(p.Spectrometer.GetStatus())}
    rec["spectrometer_spectrum"] = spectrum_record("q19_a_spectrometer", p.Spectrometer.GetSpectrum())
    t1 = time.perf_counter()
    eds = p.GetSpectrum()
    rec["phenom_getspectrum_s"] = round(time.perf_counter() - t1, 3)
    rec["phenom_spectrum"] = spectrum_record("q19_a_phenom", eds.spectrum, eds.metadata)
    return rec


def stop_then_read_spectrometer():
    p.StartAcquireSpectrum(5.0, ppi.EdsTimeType.AcquisitionTime)
    time.sleep(1.5)
    t0 = time.perf_counter()
    p.StopAcquireSpectrum()
    rec = {"stop_call_s": round(time.perf_counter() - t0, 3), "acquiring_after": p.IsAcquiringSpectrum(),
           "status_after": plain(p.Spectrometer.GetStatus())}
    rec["spectrometer_spectrum"] = spectrum_record("q19_b_spectrometer", p.Spectrometer.GetSpectrum())
    while p.IsAcquiringSpectrum():
        time.sleep(0.05)
    rec["phenom_spectrum"] = spectrum_record("q19_b_phenom", p.GetSpectrum().spectrum)
    return rec


# Q20 -----------------------------------------------------------------------------------------------------------
def spot_preset():
    presets = p.LoadPulseProcessorSettings()
    spot = presets.spot
    before = plain(p.Spectrometer, 1)
    p.Spectrometer.ApplySettings(spot)
    after = plain(p.Spectrometer, 1)
    rec = async_spectrum("q20_spot_preset", 2.0)
    return {"spectrometer_before": before, "spectrometer_after_apply": after, "spectrum": rec}


def map_preset_back():
    presets = p.LoadPulseProcessorSettings()
    p.Spectrometer.ApplySettings(presets.map)
    rec = async_spectrum("q20_map_preset_check", 2.0)
    return {"spectrometer": plain(p.Spectrometer, 1), "check_spectrum": rec}


# Q17 -----------------------------------------------------------------------------------------------------------
def spot_grid():
    points = [(-0.2 + 0.1 * i, -0.1 + 0.1 * (i % 3)) for i in range(10)]
    per_point = []
    t_all = time.perf_counter()
    for i, (x, y) in enumerate(points):
        t0 = time.perf_counter()
        set_spot(x, y)
        t_set = time.perf_counter() - t0
        rec = async_spectrum(f"q17_point{i}", 0.5)
        per_point.append({"xy": [x, y], "set_spot_s": round(t_set, 3), "wall_s": round(time.perf_counter() - t0, 3),
                          "counts": rec["counts"]})
    return {"total_s": round(time.perf_counter() - t_all, 3), "points": per_point}


# Q6 ------------------------------------------------------------------------------------------------------------
def image(name, w, h, scale, cx, cy):
    sp = ppi.ScanParams()
    sp.size = ppi.Size(w, h)
    sp.detector = ppi.DetectorMode.All
    sp.nFrames = 2
    sp.hdr = False
    sp.scale = scale
    sp.center = ppi.Position(cx, cy)
    acq = p.SemAcquireImage(sp)
    ppi.Save(acq, str(OUT / f"{name}.tiff"))
    md = acq.metadata
    return {"asked": [w, h, scale, cx, cy], "pixelSize": plain(md.pixelSize), "scanCenter": plain(md.scanCenter),
            "toWorld": plain(ppi.Application.ToWorld(acq))}


# ---------------------------------------------------------------------------------------------------------------

p = ppi.Phenom()
mode = p.GetOperationalMode()
say("PyPhenom", ppi.__version__, "| operational mode:", mode)
if mode != ppi.OperationalMode.LiveSem:
    LOG.close()
    raise SystemExit("Not in live SEM imaging: start imaging a sample in the Phenom UI, then run this again.")

original_mode = p.GetSemViewingMode()
try:
    step("q19_a_spectrometer_stop", stop_via_spectrometer)
    step("q19_b_stop_then_read_spectrometer", stop_then_read_spectrometer)
    step("baseline_after_q19", lambda: async_spectrum("baseline_after_q19", 1.0))

    try:
        step("q20_spot_preset", spot_preset)
    finally:
        step("q20_map_preset_restored", map_preset_back)

    try:
        step("q17_spot_grid_10_points", spot_grid)
    finally:
        p.SetSemViewingMode(original_mode)
        time.sleep(0.3)
        step("viewing_mode_restored", lambda: plain(p.GetSemViewingMode(), 3))

    step("q6_wide_full", lambda: image("wide_full", 960, 540, 1.0, 0.0, 0.0))
    step("q6_wide_half_y", lambda: image("wide_half_y", 960, 540, 0.5, 0.0, 0.25))
    step("q6_wide_half_x", lambda: image("wide_half_x", 960, 540, 0.5, 0.25, 0.0))

    step("q7_eds_live_map_construct", lambda: str(ppi.Application.EdsLiveMap(p)))
finally:
    try:
        p.SetSemViewingMode(original_mode)
    except Exception as e:
        say("could not restore the viewing mode:", repr(e))
    try:
        if p.IsAcquiringSpectrum():
            p.StopAcquireSpectrum()
    except Exception:
        pass
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=1, default=str), encoding="utf-8")
    bad = [k for k, v in RESULTS.items() if not v["ok"]]
    say(f"\nDone: {len(RESULTS) - len(bad)} ok, {len(bad)} failed: {bad}")
    say(f"Send the folder {OUT}")
    LOG.close()
