# Discovery: the Phenom XL and PyPhenom (2026-11-23)

What was read and measured on the instrument before phnt was written. The conclusions are in
[../../planning.md](../../planning.md) ("The instrument" and "EDS on this XL"); this folder keeps the evidence.

| File | What it is |
|---|---|
| `pyphenom_api.txt` | Every top-level class and function of PyPhenom 2.1.0 with its docstring (`scripts/dump_pyphenom.py`) |
| `pyphenom_modules.txt` | The submodules: Application, Spectroscopy, Processing, Stitch, Features, … (`scripts/dump_modules.py`) |
| `phenom_probe.txt` | The XL's state, read only (`scripts/probe_phenom.py`); the license username removed |
| `license_checks.txt` | `HasLicense` for the nine PPI features (all False) and the simulator's answers (`scripts/license_sim.py`) |
| `eds_tests_20261123_142906/` | EDS round 1 (`scripts/eds_tests.py`): state, presets, field and spot spectra, async, the 512² scan-centre images, license-gated calls. `console.txt` is the run's output; the original folder's `log.txt` and `results.json` were not kept |
| `eds_tests2_20261123_144016/` | EDS round 2 (`scripts/eds_tests2.py`): stopping a spectrum, the spot preset, a 10-point spot grid, 960×540 scan-centre images, EdsLiveMap |
| `eds_tests3_20261123_150632/` | EDS round 3 (`scripts/eds_tests3.py`): when spectra accumulate, and `ClearSpectrum` |

Spectra are JSON (`offset` and `dispersion` in eV, `data` per channel, `metadata` as PyPhenom gave it); images are
TIFFs written by `PyPhenom.Save`. Conditions: the C–Ni sample (C, Ni, O, P from electroless Ni–P, traces of Al, Si,
Cl), 15 kV, spot 5.1 (Map preset), WD 6.3 mm, HFW 877 µm, live imaging.

Note for later readers: in rounds 2 and 3 several "asynchronous" spectra are running totals of the ones before them
(round 3 found why: `Spectrometer.ClearSpectrum()` is needed before each `StartAcquireSpectrum`). Read their counts,
live and real times as cumulative where the round's notes in planning.md say so.
