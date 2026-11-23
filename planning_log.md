# phenom-translator: development log

What was done, found and decided, by date (oldest first). The current design is in [planning.md](planning.md); what
changed per version, in [CHANGELOG.md](CHANGELOG.md); the evidence, in [docs/discovery](docs/discovery/README.md).

## State log

- 2026-11-23: plan. ls6t read as the model (FUNCTIONALITY.md, planning.md, the MCP server, the changelog): a local
  translator on the instrument PC, run by the LLM app over stdio. LabSpec needed a VBS bridge because it has no Python
  API; PyPhenom is Python, so phnt has no bridge, only an adapter with fixed verbs. Name `phnt`.
- 2026-11-23: PyPhenom. Not on PyPI; already installed on the instrument PC: PyPhenom 2.1.0 as
  `C:\Program Files\Python312\DLLs\PyPhenom.pyd`, so phnt runs on Python 3.12 there (3.14 not possible with this
  build). `ppi.Phenom()` connects with the license installed on the PC; `ppi.Phenom('Simulator', '', '')` is the
  simulator. API dumped (`pyphenom_api.txt`, `pyphenom_modules.txt`) and the XL probed read-only
  (`phenom_probe.txt`): XL with the manual-height holder (type 100), stroke ±50 mm, kV reported negative
  (−4.8 … −20.5 kV), WD 1–60 mm, SED, charge reduction Off/Low/High, Amptek EDS at 234.7 K.
- 2026-11-23: licenses. `HasLicense` False for all nine PPI add-on features. On the simulator, imaging, autofocus and
  RoughFocus work; Spectrometer, AcquireSpectrum and Identify raise "Missing license: Spectroscopy".
- 2026-11-23: **raw EDS works on the XL** without the license (25,743 counts in 1 s at 15 kV): EDS case 1 (spectra,
  phnt's own identification; no quantification, no maps). The simulator enforces the license, the XL does not.
- 2026-11-23: EDS round 1 (`eds_tests.py`, C–Ni sample): energy axis from each spectrum (map preset: 9.8616 eV/ch,
  offset −56.23 eV, 2048 ch); live and real time overshoot the request; dead time ~5 %; 1 s repeats within Poisson
  noise; `AcquireSpectrum` costs ~4 s on top of counting; spot mode works and restores; `ToWorld` (license-free) maps
  pixels to stage metres, row down = stage −Y; scan centre in fractions of the field, +x right, +y down; free:
  WriteMsaFile, LineEnergy, EstimateIcr, GetShift, GetFocusCriteria, ToWorld; licensed: Identify, Quantify,
  DuaneHuntLimit. Calibration from all spectra summed: gain right, axis ~12 eV low, ~130 eV at Mn Kα; the sample
  shows C, Ni, O, P (electroless Ni–P), traces of Al, Si, Cl.
- 2026-11-23: EDS round 2 (`eds_tests2.py`): nothing stops a spectrum early (`StopAcquireSpectrum` and
  `Spectrometer.Stop` block until it ends); `Spectrometer.GetSpectrum` reads empty after a stop; the spot preset
  changes what is reported but nothing measurable (dropped); spot moves 0.01–0.03 s, ~0.7 s per 0.5 s point;
  `ToWorld` ignores the scan centre; on 960×540 the scan centre's y is a fraction of the *width*, and beyond the
  field's edge the scan returns no signal; `EdsLiveMap` refused ("Missing license: EdsMap").
- 2026-11-23: EDS round 3 (`eds_tests3.py`): `StartAcquireSpectrum` adds to the previous spectrum (counts, live and
  real time all running totals), even after a synchronous acquisition; `Spectrometer.ClearSpectrum()` before each
  start gives fresh spectra at 1.26–1.28 s per 1 s spectrum. phnt's EDS path: clear, start, poll, get.
- 2026-11-23, 2026.11.23.1: **phase 1** written in the repo (github.com/feranick/phenom_translator): read-only
  adapter with the allowed/forbidden PyPhenom tables (checked by a test against the source), fake XL with the
  discovery's values, profile (defaults, proposal from discovery, import by a person), per-kind study schemas that
  validate and generate `study_format`, estimates from the measured timings, CLI and MCP server. 57 tests pass
  (Python 3.13, mcp 2.3, on the fake). Not yet run on the instrument PC: TESTING.md T0–T6.
- 2026-11-23, 2026.11.23.1 (continued): **create_new_translators.md read** and phase 1 checked against it (decisions in
  planning.md, "Following the template"): phnt stays outside llm-translators like p3dt and ls6t (instrument PC only,
  no runtime, SLURM or router) but keeps the contract. `validate` now returns `{name: result}` with a per-study time
  cap (`limits.study_minutes_max`) and a request-total warning, as ls6t; study names checked; `tool_status` with
  `translator`, `pyphenom` and `executor: local`; PyPhenom found by import, `PHNT_PYPHENOM`, the venv's base
  Python's DLLs, or the usual Windows installs; a PyPhenom stand-in (`tests/ppi_stub`) runs `PhenomAdapter`'s code in
  the tests; author address as the template; README in the template's order with "Assumptions about PyPhenom".
  `study_format` measured at 11.9 kB (template: 10–12 kB). 65 tests pass (Python 3.13 here).
- 2026-11-23, 2026.11.23.2: **first run on the XL** (Python 3.12.2 from the GitHub zip; TESTING T0, T2, T4):
  PyPhenom found by plain import; status with no read errors, kV positive, `can_image` and `eds_ready` true; discover
  with properties identical to the probe. Three fixes: the largest field depends on the WD (755 µm at 3.9 mm, 877 at
  6.3), so a discovery keeps the widest range and records the field per WD, and validation only warns; a vacuum that
  is not stable (12.9 Pa, target Off) and an SED `NotAllowed` are warned and in the summary; the holder's real name
  `XL Manual Height`. Still to do: T1 (Standby), T3 (status while the Phenom UI acquires), T4 import, T5, T6.
- 2026-11-23, 2026.11.23.3: discover rerun with .2 on the XL: clean (no warnings, no proposal changes; vacuum stable
  0.1 Pa, SED Disabled). `phnt report` added so a test session is one command and two files (Nicola chats from
  another computer): versions, the instrument now and its read time, profile and proposal, the PPI simulator, and a
  watch that lists every change and read error while the Phenom UI works (TESTING T1, T3, T5 in one run).
- 2026-11-23, 2026.11.23.4: the first `phnt report --watch 180` at the instrument looked stuck: silent for 180 s,
  and its notice on stderr shown by PowerShell ISE as a red NativeCommandError. The report now prints only to stdout,
  each change as it happens and a line every 30 s. Rule for phnt's CLI: nothing on stderr in normal use.
- 2026-11-23, 2026.11.23.5: the first watch report from the XL (with .3): clean reads (0.39 s each, no errors), a
  pump-down 18.8 → 0.1 Pa in ~36 s with the SED allowed below ~2 Pa, the PPI simulator connects (T5 pass); but each
  pressure step was a 'change', and no UI action was seen (T1, T3 not observed). The watch now uses quick reads every
  0.5 s with a full status every 30 s, logs changes of state only, keeps the pressure trace in the JSON. A third
  largest-field point (726 µm at WD 3.3 mm): the field by WD is interpolated, close to linear.
- 2026-11-23, 2026.11.23.6: second watch on the XL (with .5): images, a UI EDS spot spectrum and a sample exchange
  all seen (T3 pass). Two refusals are states, not faults: the UI's EDS holds the detector, and the HFW range is
  refused outside NavCam/SEM; both are reported as `unavailable`, and the summary has `eds` (idle, acquiring, busy
  elsewhere). The watch compares only quick reads, so the full status no longer repeats lines. 1003.2 µm at WD 8.7 mm.
