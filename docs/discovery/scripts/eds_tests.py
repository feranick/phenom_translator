"""phnt EDS bring-up tests (2026-11-23).

Run on the instrument PC while live-imaging a ROBUST sample (metal, mineral, a stub with a few phases; not a
polymer or anything beam-sensitive) in the Phenom UI, at the kV and spot you normally use for EDS:

    py -3.12 eds_tests.py

What it does (about a minute; do not touch the Phenom UI meanwhile):
  - reads the state, the instrument properties, the spectrometer's settings and pulse-processor presets;
  - field spectra: 1 s acquisition time, 2 s live time, 3 repeats of 1 s, timed;
  - a 5 s spectrum started asynchronously, polled, and stopped after 2 s;
  - spot mode: two 2 s spectra with the beam parked at two positions, then the viewing mode is restored;
  - three 512x512 images (full field, and half-size at two offsets) to find the units of the scan centre;
  - tries the functions that may need a license (msa export, line energies, Duane-Hunt, identify, EDS maps,
    image shift, focus criteria, pixel-to-stage transform) and records which are refused.

What it changes: only the SEM viewing mode (spot mode for two short spectra), restored on every path.
No stage moves, no kV / spot / vacuum / detector changes, no exclusive access.

Writes eds_tests_<time>/ (log.txt, results.json, spectra as .json, images as .tiff). Zip it and send it.
"""
import json
import time
from pathlib import Path

import PyPhenom as ppi

OUT = Path(f"eds_tests_{time.strftime('%Y%m%d_%H%M%S')}")
OUT.mkdir()
LOG = open(OUT / "log.txt", "w", encoding="utf-8")
RESULTS = {}
KEEP = {}  # objects reused by later steps


def say(*parts):
    msg = " ".join(str(x) for x in parts)
    print(msg)
    LOG.write(msg + "\n")
    LOG.flush()


def plain(o, depth=2):
    """PyPhenom object -> JSON-friendly data (attributes only, no calls)."""
    if o is None or isinstance(o, (bool, float, str)):
        return o
    if isinstance(o, int):
        return o if type(o) is int else str(o)  # enum members are int subclasses
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
        if callable(value):
            continue
        out[name] = plain(value, depth - 1)
    return out or str(o)


def step(name, fn):
    say(f"\n== {name}")
    t0 = time.perf_counter()
    try:
        result = fn()
        RESULTS[name] = {"ok": True, "s": round(time.perf_counter() - t0, 3), "result": result}
        say(f"   ok ({RESULTS[name]['s']} s): {json.dumps(result, default=str)[:500]}")
    except Exception as e:
        RESULTS[name] = {"ok": False, "s": round(time.perf_counter() - t0, 3), "error": repr(e)}
        say(f"   FAILED: {e!r}")


def save_spectrum(name, eds):
    sp = eds.spectrum
    data = list(sp.data)
    rec = {"offset": sp.offset, "dispersion": sp.dispersion, "bins": len(data), "counts": sp.counts,
           "metadata": plain(eds.metadata)}
    (OUT / f"{name}.json").write_text(json.dumps({**rec, "data": data}, default=str), encoding="utf-8")
    KEEP["last_eds"] = eds
    return rec


def spectrum(name, seconds, time_type):
    t0 = time.perf_counter()
    eds = p.AcquireSpectrum(seconds, time_type)
    rec = save_spectrum(name, eds)
    rec["wall_s"] = round(time.perf_counter() - t0, 3)
    return rec


def state():
    return {
        "operational_mode": str(p.GetOperationalMode()),
        "high_tension_V": p.GetSemHighTension(),
        "spot_size": p.GetSemSpotSize(),
        "emission_current_A": p.SemGetEmissionCurrent(),
        "wd_m": p.GetSemWD(),
        "hfw_m": p.GetHFW(),
        "hfw_range_m": plain(p.GetHFWRange()),
        "spot_range": plain(p.GetSemSpotSizeRange()),
        "viewing_mode": plain(p.GetSemViewingMode(), 3),
        "spectrometer_status": plain(p.Spectrometer.GetStatus()),
        "charge_reduction": plain(p.SemGetVacuumChargeReductionState()),
    }


def properties():
    out = {}
    for name in p.GetPropertyNames():
        for getter in (p.GetPropertyDouble, p.GetPropertyInt, p.GetPropertyBool, p.GetPropertyString):
            try:
                out[name] = getter(name)
                break
            except Exception:
                pass
        else:
            out[name] = None
    return out


def async_then_stop():
    trace = []
    p.StartAcquireSpectrum(5.0, ppi.EdsTimeType.AcquisitionTime)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2.0:
        trace.append({"t": round(time.perf_counter() - t0, 2), "acquiring": p.IsAcquiringSpectrum(),
                      "status": plain(p.Spectrometer.GetStatus())})
        time.sleep(0.5)
    p.StopAcquireSpectrum()
    time.sleep(0.3)
    after = p.IsAcquiringSpectrum()
    return {"trace": trace, "acquiring_after_stop": after, "partial": save_spectrum("async_partial", p.GetSpectrum())}


def spot(name, x, y):
    vm = p.GetSemViewingMode()
    sp = vm.scanParams
    sp.center = ppi.Position(x, y)
    vm.scanParams = sp
    vm.scanMode = ppi.ScanMode.Spot
    p.SetSemViewingMode(vm)
    time.sleep(0.3)
    readback = plain(p.GetSemViewingMode(), 3)
    rec = spectrum(name, 2.0, ppi.EdsTimeType.LiveTime)
    rec["viewing_mode_readback"] = readback
    return rec


def image(name, scale, cx, cy, size=512):
    sp = ppi.ScanParams()
    sp.size = ppi.Size(size, size)
    sp.detector = ppi.DetectorMode.All
    sp.nFrames = 2
    sp.hdr = False
    sp.scale = scale
    sp.center = ppi.Position(cx, cy)
    acq = p.SemAcquireImage(sp)
    KEEP[name] = acq
    rec = {"asked": {"scale": scale, "center": [cx, cy], "size": size}, "hfw_m": p.GetHFW()}
    md = acq.metadata
    for field in ("pixelSize", "position", "scanCenter", "scanScale", "rotation", "workingDistance"):
        try:
            rec[field] = plain(getattr(md, field))
        except Exception as e:
            rec[field] = repr(e)
    try:
        ppi.Save(acq, str(OUT / f"{name}.tiff"))
        rec["saved"] = f"{name}.tiff"
    except Exception as e:
        rec["saved"] = repr(e)
    return rec


def to_msa():
    path = OUT / "field_1s_acq.msa"
    ppi.Spectroscopy.WriteMsaFile(KEEP["field_1s_acq"], str(path), True)
    return path.name


# ---------------------------------------------------------------------------------------------------------------

p = ppi.Phenom()
mode = p.GetOperationalMode()
say("PyPhenom", ppi.__version__, "| operational mode:", mode)
if mode != ppi.OperationalMode.LiveSem:
    LOG.close()
    raise SystemExit("Not in live SEM imaging: start imaging a sample in the Phenom UI, then run this again.")

original_mode = p.GetSemViewingMode()
try:
    step("state_before", state)
    step("properties", properties)
    step("spectrometer_settings", lambda: plain(p.Spectrometer, 1))
    step("pulse_processor_presets", lambda: plain(p.LoadPulseProcessorSettings(), 3))

    step("field_1s_acq", lambda: spectrum("field_1s_acq", 1.0, ppi.EdsTimeType.AcquisitionTime))
    KEEP["field_1s_acq"] = KEEP.get("last_eds")
    step("field_2s_live", lambda: spectrum("field_2s_live", 2.0, ppi.EdsTimeType.LiveTime))
    for i in range(3):
        step(f"field_1s_repeat{i}", lambda i=i: spectrum(f"field_1s_repeat{i}", 1.0, ppi.EdsTimeType.AcquisitionTime))
    step("async_start_poll_stop", async_then_stop)

    try:
        step("spot_center", lambda: spot("spot_center", 0.0, 0.0))
        step("spot_offset_0.1_0.1", lambda: spot("spot_offset", 0.1, 0.1))
    finally:
        p.SetSemViewingMode(original_mode)
        time.sleep(0.3)
        step("viewing_mode_restored", lambda: plain(p.GetSemViewingMode(), 3))

    step("image_full", lambda: image("image_full", 1.0, 0.0, 0.0))
    step("image_half_x0.25", lambda: image("image_half_x", 0.5, 0.25, 0.0))
    step("image_half_y0.25", lambda: image("image_half_y", 0.5, 0.0, 0.25))

    # functions that may need a license (Q1c)
    step("lic_write_msa", to_msa)
    step("lic_line_energy_FeKa1",
         lambda: ppi.Spectroscopy.LineEnergy(ppi.Spectroscopy.Element.Fe, ppi.Spectroscopy.Line.Ka1))
    step("lic_duane_hunt", lambda: ppi.Spectroscopy.DuaneHuntLimit(KEEP["field_1s_acq"]))
    step("lic_estimate_icr", lambda: ppi.Spectroscopy.EstimateIcr(KEEP["field_1s_acq"]))
    step("lic_identify", lambda: plain(ppi.Spectroscopy.Identify(KEEP["field_1s_acq"]), 3))
    step("lic_eds_live_map_construct", lambda: str(ppi.Application.EdsLiveMap()))
    step("lic_get_shift", lambda: plain(ppi.Processing.GetShift(KEEP["image_full"].image, KEEP["image_full"].image)))
    step("lic_focus_criteria", lambda: plain(ppi.Processing.GetFocusCriteria(KEEP["image_full"].image)))
    step("lic_to_world", lambda: plain(ppi.Application.ToWorld(KEEP["image_full"])))

    step("state_after", state)
finally:
    try:
        p.SetSemViewingMode(original_mode)
    except Exception as e:
        say("could not restore the viewing mode:", repr(e))
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=1, default=str), encoding="utf-8")
    ok = [k for k, v in RESULTS.items() if v["ok"]]
    bad = [k for k, v in RESULTS.items() if not v["ok"]]
    say(f"\nDone: {len(ok)} ok, {len(bad)} failed: {bad}")
    say(f"Zip and send the folder {OUT}")
    LOG.close()
