"""phnt EDS bring-up tests, round 3 (2026-11-23): when does StartAcquireSpectrum add to the previous spectrum (Q21)?
Same conditions as before: live-imaging the C-Ni sample (field scan, not spot), nothing touched in the Phenom UI.
    py -3.12 eds_tests3.py
About 25 s. Changes nothing: no spot mode, no preset, no stage, no beam settings. Prints a table; also writes
eds_tests3_<time>/results.json.
"""
import json
import time
from pathlib import Path

import PyPhenom as ppi

OUT = Path(f"eds_tests3_{time.strftime('%Y%m%d_%H%M%S')}")
OUT.mkdir()
ROWS = []


def record(label, eds, wall):
    md = eds.metadata
    live, real, counts = md.liveTime, md.realTime, eds.spectrum.counts
    row = {"step": label, "counts": counts, "live_s": round(live, 3), "real_s": round(real, 3),
           "counts_per_live_s": round(counts / live) if live else None, "wall_s": round(wall, 2)}
    ROWS.append(row)
    print(f"{label:34s} counts {counts:8d}  live {live:6.3f}  real {real:6.3f}  cps(live) {row['counts_per_live_s']}"
          f"  wall {wall:5.2f}")


def sync(label, t=1.0):
    t0 = time.perf_counter()
    eds = p.AcquireSpectrum(t, ppi.EdsTimeType.LiveTime)
    record(label, eds, time.perf_counter() - t0)


def start(label, t=1.0, clear=False, time_type=ppi.EdsTimeType.LiveTime):
    t0 = time.perf_counter()
    if clear:
        p.Spectrometer.ClearSpectrum()
    p.StartAcquireSpectrum(t, time_type)
    while p.IsAcquiringSpectrum():
        time.sleep(0.05)
    record(label, p.GetSpectrum(), time.perf_counter() - t0)


p = ppi.Phenom()
if p.GetOperationalMode() != ppi.OperationalMode.LiveSem:
    raise SystemExit("Not in live SEM imaging: start imaging a sample in the Phenom UI, then run this again.")
try:
    sync("A1 sync 1 s (reference)")
    start("A2 start 1 s")
    start("A3 start 1 s")
    start("A4 start 1 s")
    start("A5 start 1 s, acquisition time", time_type=ppi.EdsTimeType.AcquisitionTime)
    sync("B1 sync 1 s")
    start("B2 start 1 s after sync")
    start("C1 clear + start 1 s", clear=True)
    start("C2 clear + start 1 s", clear=True)
    start("C3 clear + start 1 s", clear=True)
    start("D1 start 1 s (no clear)")
    sync("E1 sync 1 s (end)")
except Exception as e:
    print("FAILED:", repr(e))
    ROWS.append({"error": repr(e)})
finally:
    (OUT / "results.json").write_text(json.dumps(ROWS, indent=1), encoding="utf-8")
    print(f"\nWritten {OUT}/results.json")
