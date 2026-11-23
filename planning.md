# phenom-translator (phnt): planning and session context

A new chat starts with: "Read planning.md and start." Follow ~/Software/llm-translators/docs/create_new_translators.md
(the template; read 2026-11-23, decisions below under "Following the template"), with ~/Software/labspec_translator
(ls6t) as the model: a *local* translator on the Windows instrument PC, with an installer, `connect` for the LLM
apps, operator confirmations, an instrument lock, a simulator with benchmarks and a test mode for bring-up. No SLURM,
no router, no llmt-runtime dependency.

## Names

| Thing | Value | Note |
|---|---|---|
| Repository | github.com/feranick/phenom_translator | underscore, like labspec_translator (the template says `<name>-translator`) |
| Package | `phenom_translator` | |
| Key = command | `phnt` | ends in t, like the others |
| MCP server | `phnt-mcp` | |
| Settings prefix | `PHNT_` | |
| HTTP port | 8772 | 8766–8770 llm-translators, 8771 ls6t |
| Output folder | `~/phnt_runs` (`PHNT_OUT`); state in `~/phnt` (`PHNT_HOME`) | as ls6t |

## Scope and typical requests

First version: imaging (BSD all, segments, N–S, E–W, SED, mix), focus, stage moves, NavCam; montages, series,
particles, calibration; EDS spectra at spots or on grids, with element identification. Out of scope: quantification
and EDS maps (licensed), calibration / alignment / power / users / licenses (never), beam writing (patterning),
loading and unloading inside a study (operator only).

Typical requests:
1. "Image the middle of the sample at 500 µm and at 50 µm, BSD, 15 kV." (`image` with two studies, or `points`)
2. "Make a 2 × 1.5 mm overview of the sample." (`montage`)
3. "Find the particles in this powder and give me their size distribution." (`particles`)
4. "Which elements are in these three spots / in that bright phase?" (`eds_point`, spots picked from an image)
5. "Where is the P in this Ni–P coating? A coarse map is fine." (`eds_grid`)
6. "The same spot every 30 s for 10 minutes: does the beam damage it?" (`series`)
7. "Is the stage repeatable / is the pixel size right on the grid / is the EDS energy axis right?" (`calibration`)
8. "What state is the Phenom in, and can I image now?" (`instrument status`)

## Following the template (create_new_translators.md), decisions of 2026-11-23

- **Not part of llm-translators** (decided by Nicola, 2026-11-23), like p3dt (Mac only) and ls6t: phnt runs only on
  the instrument PC, one request at a time, so no llmt-runtime, no SLURM, no router, no `run` key, no
  `translators.json` entry, and Part 2 of the template does not apply.
- **The contract is kept** so the model and the tools treat it like the others: `study_format()` compact (11.9 kB,
  a test keeps it under 13 kB) with `status`; `validate` -> `{name: {ok, errors, warnings, estimate}}` with every
  error saying the fix (`estimate` has minutes; `procs` / `mem_mb` mean nothing here and are left out);
  `tool_status()` with `translator`, the backend key `pyphenom` (found: `{version, path}`, missing: `{error}`) and
  `executor: {kind: local}`; `phnt status` prints JSON; `<key>-mcp`; `initialize` answered at once.
- **Phase 2 adds the rest of the contract**: `run(studies, wait)`, `start`, `status(request, wait)`, `jobs`,
  `cancel(request, names)` (a `cancel` flag file in the study folder, read by the runner between steps), `read_file`
  (under `PHNT_OUT` only), `inputs` (the PyPhenom calls of one study, without running: `get_inputs`), `bench` and
  `bench_status`; request folders `PHNT_OUT/run_<date>_<time>_<id>/` with `request.json`, `studies.json`,
  `<name>/<name>.json` written atomically; results with `ok`, `reliable`, `unreliable_because`, `warnings`, `checks`,
  `expect` (`{quantity, value, got, tol, pass}`), dotted result keys, `images`, `files`, `seconds`, and `execution`
  (`{executor: "local", lock, instrument: {id, software}}`); clock times with the PC's UTC offset; MCP `wait_s` ≤ 50.
- **Deliberate differences**: the version is set only in `__init__.py` (ls6t's 2026.11.23.4 decision), not in every
  module's docstring and `pyproject.toml`; the MCP wrapper is ls6t's, not `llmt_runtime.server.Server`; the tests are
  split by subsystem (adapter, profile, format, CLI/MCP), with a PyPhenom stand-in (`tests/ppi_stub`) instead of
  "backend tests that skip"; the benchmarks run on the fake XL (and later the PPI simulator), never on the instrument.
- **Research items** (template, "Research first"): backend version and finding: "The instrument" and README
  "Install"; inputs and outputs: "What PyPhenom offers" and "EDS on this XL"; assumptions, each with what catches it:
  README "Assumptions about PyPhenom"; checks: "What phnt checks"; size and cost: `plan.py` estimates from measured
  timings (the instrument, not CPU, is the cost; a request holds it for its whole time); interconnections: none with
  llm-translators; with ls6t an open idea (correlative Raman–SEM on the same sample, shared fiducials).

## What this is

SEM studies (JSON) -> Thermo Scientific Phenom XL (with EDS) through PyPhenom (the Phenom Programming Interface), on
the Windows PC connected to the microscope, with checked results, a CLI (`phnt`) and an MCP server (`phnt-mcp`) that
the Claude app runs locally on that PC, like ls6t.

Unlike LabSpec, PyPhenom *is* a Python API: there is no bridge script. The runner calls PyPhenom directly, but only
through one adapter class with a fixed set of verbs (the equivalent of ls6t's bridge protocol): nothing else in phnt
imports PyPhenom, so the guarantee "only fixed verbs reach the instrument" still holds.

## The instrument (discovery, 2026-11-23)

From `pyphenom_api.txt`, `pyphenom_modules.txt` and `phenom_probe.txt` (keep them in `docs/discovery/`, with the
license username removed from the probe before committing).

- PyPhenom **2.1.0**, a compiled `PyPhenom.pyd` for **Python 3.12** (`C:\Program Files\Python312\DLLs\`). phnt targets
  3.12; 3.14 is not possible with this build. The `.pyd` is proprietary and licensed to the instrument: never bundled,
  never committed.
- The PPI license is installed on the PC: `ppi.Phenom()` with no arguments connects to the XL. The simulator:
  `ppi.Phenom('Simulator', '', '')`. Credentials never appear in the repo, logs or answers.
- Activated instrument feature: "XL 100 x 100 mm stage". Stage stroke under the SEM: X and Y −50 … +50 mm.
- Sample holder: type 100 = `XlManualHeight` (height set by hand at loading), status Present. No multi-axis stage.
- High tension: reported **negative** (−15000 V now; range −20500 … −4800 V). Studies use positive kV; the adapter
  converts, and the sign of `SetSemHighTension` is checked on the simulator first (TESTING Q2).
- Spot size range 0 … 5.8 (PyPhenom's unit, A/√V); presets as properties: `SpotSize.Image / Point / Map`,
  `EmissionCurrent.Nominal / Low`, `HighTension.AllMaterials / HighResolution / Analysis`,
  `SamplePressure.High / Medium / Low`. Measured: `HighTension.AllMaterials` 5.3 kV, `HighResolution` 10 kV,
  `Analysis` 15 kV (reported negative); the spot and emission values are in `results.json` (Q8).
- `TransitionTime.StandbyToOperational` 30 s (the API docstring's "about 5 minutes" is generic),
  `OffToOperational` 52200 s; `SpotPosition.Accuracy` 0.005 (likely a fraction of the field).
- Operational, at WD 6.3 mm: HFW 2.47 µm … 877 µm; at WD 3.9 mm: … 755 µm (**the largest field shrinks at short
  WD**), and at WD 3.3 mm: … 726 µm; close to linear, ~560 µm + 50.4 µm per mm of WD; validation interpolates.
  Live view 960×540, 4 frames. `SampleHolderType.Name(100)` is "XL Manual Height".
- Vacuum: right after the 16:08 run the charge reduction read target Off but not stable at ~12.9 Pa, and the SED
  was `NotAllowed` (it needs high vacuum) while BSD imaging went on. A pump-down seen by the watch (.3): 18.8 → 0.1 Pa
  in ~36 s, stable at ~50 s; the SED went from `NotAllowed` to `Disabled` (allowed, off) between 2.5 and 1.8 Pa.
- A full status read takes 0.39 s mean, 0.92 s max on the XL (0.9 s with the properties): the watch and the
  phase-2 watchdog read only what changes quickly (`Adapter.quick()`) and a full status every 30 s.
- **The Phenom UI's EDS holds the detector**: while it took a spot spectrum (~7 s, scan mode `Spot`, after a 0.5 s
  `AcquireSemImage`), `Spectrometer.GetStatus` from phnt was refused (`Access denied trying to open Spectrometer
  device - is another application using it?`); every other read went on. So phnt and the UI cannot both use the EDS;
  phnt reports it as `eds: busy elsewhere`. phnt's status read every 0.5 s did not disturb the UI's spectrum (Q22). A phase-4 EDS study takes the instrument lock (exclusive access) first.
- A sample exchange from the UI, as the watch saw it: `Unloading` 33 s (the pressure reads ~0 while venting), `Loadpos`
  with the door open, `SelectingNavCam` 3 s, `LiveNavCam`, `SelectingSem` more than 40 s (pumping, 0.65 Pa).
  `GetHFWRange` is refused outside NavCam/SEM. A quick read takes 0.17 s mean (0.99 s max).
- **Standby** (watch of 2026-11-23 17:10): set from the UI's Settings > Status; woken by the box at the bottom left of
  the UI or the button on the microscope. Entering it, the instrument mode turns `Standby` at once but the operational
  mode keeps its last value (`LiveNavCam`) for ~20 s, then `Unavailable`: phnt must judge readiness by the instrument
  mode first (it does). The reported pressure went to ~60 Pa and the chamber pumped down again (1.85 Pa after ~90 s);
  Operational about 7 s after that, NavCam 20 s later. All reads worked in Standby. One quick read took **6.0 s**
  during the transitions: the phase-2 watchdog must allow a slow read (several seconds) before calling the
  instrument unreachable.
- The SED reads `NotAllowed` in NavCam whatever the vacuum (0.1 Pa, stable): only with the sample under the SEM does
  `NotAllowed` mean the vacuum is not ready.
- Largest field at WD 8.7 mm: 1003.2 µm (the four points 3.3, 3.9, 6.3, 8.7 mm: ~50–52 µm per mm of WD).
- PyPhenom's simulator differs from the XL: holder `XL1 Motorized Height`, 42 Pa, 5.3 kV, `can_image` false; it
  refuses the spectrometer (license) and the activated features (it tries a network host).
- WD range 1 … 60 mm. SED present. Vacuum charge reduction: Off / Low / High.
- EDS: an SDD (`FastSDD_C2`, 25 mm²) on an Amptek digital pulse processor, at 234.7 K (−38.5 °C). Take-off angle
  28.5°; EDX working distance optimal 4.5 … 10 mm, acceptable 3 … 12 mm. Details below.
- State at the probe: instrument Standby, operational mode Unavailable, door closed, no exclusive access held.
  HFW range 16.7 … 100 mm (the NavCam's; to re-read when operational).
- **PPI license: base only.** `ppi.HasLicense` is False for all nine add-on features (Spectroscopy, EdsMap,
  FastSpectrum, Stitching, ParticleMetric, RoughnessReconstruction, ResolutionMeasurement, AsbestosDetection,
  LiveVideo). On the simulator: `SemAcquireImage`, `SemAutoFocus` and `Application.RoughFocus` work;
  `Spectrometer.GetStatus`, `AcquireSpectrum` and `Spectroscopy.Identify` raise
  `RuntimeError('Missing license: Spectroscopy')`. **On the XL, raw EDS works without the license** (Q1b,
  2026-11-23): `p.AcquireSpectrum(1.0)` while imaging returned 25743 counts in 1 s, `metadata.highTension` 15000.0.
  The simulator enforces the license and the instrument does not, so EDS paths are tested on `fake.py` and the XL,
  never the PPI simulator. A later PyPhenom or Phenom software update could start enforcing it: a
  "Missing license" error at run time turns the EDS kinds off with that reason, it is not a crash.
- Sign of high tension: `GetSemHighTension` reports −15000 V, the EDS metadata +15000.0 V for the same setting.

### What PyPhenom offers that phnt builds on

- **Lock**: `GetExclusiveAccess(message)` / `ReleaseExclusiveAccess()`: one request at a time holds the XL, and the
  message probably shows on the Phenom's screen (Q3).
- **Errors**: `ppi.Error` with codes: `OM_CONTEXT` (busy: retry, `SetApiRetryCount`), `OM_CLIPPED` (value clipped:
  every setting is read back), `EXCLUSIVE`, `OM_UNCAL`, `ACCESSDENIED`, `UNREACHABLE`.
- **Imaging**: `SemAcquireImage(Ex)` (≤ 2048², frames, dwell, drift correction, interlace, 16-bit HDR raw),
  `BeginSemAcquisition` / `SemGetAcquisition` / `AbortAcquisition` (cancellable), `SemGetAcquisitionTimeEstimate`
  (estimates for validation), detectors (BSD all / segments / N-S / E-W, SED, mix factors).
  `Acquisition.metadata` records pixel size, stage position, kV, WD, spot, dwell, detector, pressure, holder, time:
  the JSON sidecar comes from it. `ppi.Save` writes the TIFF with Phenom metadata.
- **Focus**: `SemAutoFocus`, `Application.AutoFocus / FineFocus / RoughFocus` (RoughFocus returns the focus curve,
  with 15 focus criteria), `SemAutoStigmate`, `SemAutoContrastBrightness`, `Processing.GetFocusCriteria`.
- **Stage**: `MoveTo / MoveBy` with `NavigationAlgorithm.BacklashOnly`. The docstring: point-to-point about 35 µm,
  much better with backlash correction, and only if the previous moves also used it. phnt uses BacklashOnly for
  every move. `GetStageStroke`, `GetStageModeAndPosition` (NotHomed, moving), XL holder maps
  (`MakeXLSampleHolderMap`, the 2×2 and 3×3 filter inserts, `GetSampleHolderMap(type)`).
- **NavCam**: `NavCamAcquireImage` (912² native), `NavCamGetOverviewImage`, `SelectImagingDevice`,
  `Application.FindInOverview(overview, tile)` (where an SEM image sits in the NavCam overview).
- **EDS**: `AcquireSpectrum(time, LiveTime|AcquisitionTime)`, `Spectrometer.GetStatus()` (detector temperature,
  fast/slow counts), `Spectroscopy.Identify / Quantify / QuantifyEx` (composition, weight or atomic),
  `WriteMsaFile`, `DuaneHuntLimit` (effective beam energy: charging), `EstimateIcr` (input count rate: dead time),
  `Application.EdsLiveMap` (map streaming, identify, quantify, per-element images, `StreamTo` a file),
  `EdsGridSpectrum` (line and area sums from a map). `Spectroscopy.Simulate` makes a spectrum from a composition.
- **Free vs licensed in practice** (eds_tests.py on the XL): free: `AcquireSpectrum`, `StartAcquireSpectrum` /
  `StopAcquireSpectrum` / `GetSpectrum`, `Spectrometer` status and settings, pulse-processor presets, spot mode,
  `Spectroscopy.WriteMsaFile`, `Spectroscopy.LineEnergy` (line tables), `Spectroscopy.EstimateIcr`,
  `Processing.GetShift`, `Processing.GetFocusCriteria`, `Application.ToWorld`, `Application.RoughFocus`.
  Refused ("Missing license: Spectroscopy"): `Identify`, `Quantify`, `DuaneHuntLimit`. `EdsLiveMap(phenom)` not yet
  tried (EdsMap is not licensed).
- **Analysis**: `Application.ParticleFinder` (particles with area, axes, centroids in stage coordinates),
  `Stitch` / `TileStitcher` (optimal tile placement, DZI output), `Processing.GetShift` (drift), `MakeStatistics`,
  `GetResolutionIso20xx`, `Application.ToWorld` (pixel -> stage).
- **Simulator**: `Phenom.Simulate(acquisition)` feeds an image to the PPI simulator: phnt's synthetic samples can run
  through the real PyPhenom API (Q14).
- **Events**: door, operational mode, instrument mode, health, SED state, vacuum: the watchdog subscribes to them.
- `ppi.Features` lists the PPI license features; `ppi.HasLicense(feature)` says which this license has. None of them
  here (above), so **everything under EDS, the particle finder and the Stitch module is licensed and not available**
  unless Thermo adds the feature. phnt's own code covers particles and stitching; EDS depends on Q1b.
  `Application.TileStitcher(nx, ny, tileSize: int, overlap=0.1, encoding=Unsigned16)` for the record.
- At startup phnt reads `HasLicense` for every feature into the profile, and the study format offers only the kinds
  the license (or phnt's own code) supports: a newly bought feature turns its kinds on without a code change.

### EDS on this XL (measured 2026-11-23 with eds_tests.py, 15 kV, spot 5.1, WD 6.3 mm, live imaging)

- **Energy axis**: spectra come with the `map` pulse-processor preset's calibration: 2048 channels,
  9.8616 eV/channel, offset −56.23 eV (0 … ~20.1 keV); MnKα resolution 127.95 eV. The spectrometer's nominal
  settings say 10 eV/channel, offset 0, 135 eV: phnt always takes the axis from each spectrum, never from settings.
- **Times**: the time asked is approximate. 1 s acquisition time gave real 1.207 s, live 1.14 s; 2 s live time gave
  real 2.215 s, live 2.105 s. phnt normalises by the spectrum's own `liveTime` and records both times.
- **Dead time** (1 − live/real): 5–5.5 % on the field, 3–5 % in spot mode; input count rate ~21,400 cps
  (`EstimateIcr`). Repeat 1 s spectra: 24,715 / 24,742 / 24,659 / 24,901 counts, within Poisson noise: the beam
  current is stable.
- **Overhead**: each `AcquireSpectrum` call takes ~5 s of wall time for 1–2 s of counting (~4 s overhead). The
  asynchronous path does not have it: it counts from the first poll (0.495 s accumulated at 0.5 s), and polling gives
  live progress (fast/slow counts, accumulated time) for the watchdog and the ETA. phnt uses it, with a clear before
  each start (below).
- **Nothing stops a spectrum early** (Q19): `StopAcquireSpectrum` and `Spectrometer.Stop()` both *block* until the
  spectrum ends (called 1.5 s into a 5 s spectrum, each returned after 3.5 s; real time 5.001 s). A cancel waits for
  the spectrum in progress, so phnt keeps single spectra short (a few seconds; long ones as sums of short ones,
  which also gives drift and stability checks) and the watchdog's worst-case stop time is one spectrum.
- **Only Phenom-level EDS calls**, plus `Spectrometer.ClearSpectrum`: after `StopAcquireSpectrum` the pulse
  processor read empty (`Spectrometer.GetSpectrum`: 4096 channels at 10 eV, 0 counts) while `Phenom.GetSpectrum`
  still had the data. phnt never calls `Spectrometer.Start / Stop / GetSpectrum / ApplySettings`.
- **Spectra accumulate unless cleared** (Q21, eds_tests3.py): without a clear, each `StartAcquireSpectrum` adds to
  the previous spectrum: counts, live time and real time are all running totals (1 s each: 26,829 -> 53,354 ->
  79,533 -> 105,837 counts, live 1.09 -> 2.19 -> 3.28 -> 4.38 s), even right after a synchronous `AcquireSpectrum`
  (B2: 53,076). **`Spectrometer.ClearSpectrum()` before each `StartAcquireSpectrum` gives fresh spectra** (26,334 /
  26,513 / 26,396 counts in 1.09–1.10 s live) at 1.26–1.28 s of wall time per 1 s spectrum, against ~5 s for
  `AcquireSpectrum`. phnt's one EDS path: clear, start, poll (progress and watchdog), get; and it checks that every
  spectrum's real time is about the time asked (a multiple means a running total: refused).
- **Count rate** on the C–Ni field at 15 kV, spot 5.1 (Map): 24,100–24,500 counts per live second, dead time
  5–9 %, stable to Poisson noise across 12 spectra.
- **Presets** (Q20): the spectra use the `map` preset (1 µs peaking, 127.95 eV) even in spot mode.
  `Spectrometer.ApplySettings(presets.spot)` changes what the spectrometer *reports* (4 µs, 9.8914 eV/channel,
  offset −34.47 eV) but nothing measurable: the same count rate (21,981 vs 22,148 cps), dead time (6.1 %), line
  widths (Ni Kα 145 vs 140 eV) and peak positions as the map preset. phnt does not use presets.
- **Calibration** (Q18, the C–Ni sample, all eight spectra summed, 334,558 counts, Gaussian fits): the gain is right
  (Ni Lα, Kα, Kβ: slope 1.0004) and the axis reads **~12 eV low** everywhere (Ni Lα −11.9, Ni Kα −14.6, Ni Kβ
  −10.5 eV; C Kα −19.2 eV, a few eV more as usual for C). Resolution: Ni Kα FWHM 144 eV, MnKα-equivalent ~130 eV,
  as the preset says. Identification is unaffected (a channel is 9.9 eV); phnt still keeps an energy correction per
  preset and kV, measured by an EDS `calibration` study on a known sample (like ls6t's spectral zero), and applies
  it to its own peak positions, never to the raw spectrum.
- **Sample seen**: C Kα, Ni L and K lines, O Kα, a clear peak at 2.004 keV (2.014 after the correction: **P Kα**, as
  in electroless Ni–P), weak Al Kα, Si Kα and Cl Kα. Good test material for identification.
- **.msa files** from `Spectroscopy.WriteMsaFile` are standard EMSA/MAS 1.0 with kV, elevation angle 28.5°, live and
  real time, WD, detector distance, MnKα FWHM: readable by HyperSpy/exspy and other tools.
- **Spot mode**: `SetSemViewingMode` with `ScanMode.Spot` and `scanParams.center` works, reads back what was set,
  and the live view comes back on restoring the saved mode. 2 s live at two spots: 44,034 and 43,170 counts.
- **Pixels to stage**: `Application.ToWorld(acq)` is license-free and gives the affine map from image pixels
  (column, row from the top left) to stage metres: for a 512² image at HFW 877 µm, 1.7133 µm/px, the image centre
  at the stage position, and **row down = stage −Y**. Checked against the metadata's position.
  **`ToWorld` ignores the scan centre**: two half-size 960×540 images at centres (0, 0.25) and (0.25, 0) got the
  same transform, centred on the stage position. phnt adds `scanCenter × field` itself (and checks it on images).
  960×540 at HFW 877 µm: 0.9138 µm/px, square pixels: the HFW is the width.
- **Scan centre** (Q6): `ScanParams.center` (images and the EDS spot) is in fractions of the field, in **image
  axes: +x = image right, +y = image down** (= stage −Y). Registered: the half-size image at (0.25, 0) sits at
  +0.250 field widths to the right (correlation 0.99), the one at (0, 0.25) +0.250 field heights down (0.90). So a
  point picked in an image goes to the spot as ((col − w/2)/w, (row − h/2)/**w**), and to the stage through
  `ToWorld` plus the scan centre.
  **Both x and y are fractions of the field width** (Q6b): on 960×540, the half-size image at (0, 0.25) starts 239 px
  below the top of the full one's lower half, i.e. 0.25 × 960 px down (correlation 0.97), not 0.25 × 540. Beyond the
  field's bottom edge the scan returns no signal (that image is black past the edge). So the valid spot and image
  centres are |x| ≤ 0.5 and |y| ≤ 0.5·h/w (±0.28 for 16:9, minus half the scanned area); phnt validates both (the
  round-2 spot grid went to x = 0.7, outside the field, without an error from PyPhenom).
- **Presets measured** (Q8): spot `Low` 2.1, `Image` 3.3, `Point` 4.3, `Map` 5.1 (in use); emission `Nominal`
  40.3 µA, `Low` 20 µA; sample pressure `High` 60 Pa, `Medium` 10 Pa, `Low` 0.1 Pa. The EDS detector is an Amptek
  DP5 (USB), window C2, 25 mm².

## Architecture

```
Claude app -> phnt-mcp (Python 3.12) -> request folder + detached runner (`phnt run-request`)
                                          |
                                          v
                      adapter.py: fixed verbs, tiers, limits, read-back  <- the only module that imports PyPhenom
                          |                          |                          |
                   PyPhenom (the XL)      PyPhenom simulator (Windows)   fake.py (pure Python, any OS, CI)
operator panel (always-on-top window on the PC): STOP, Yes/No questions, who holds the instrument
```

- `config.py` settings (PHNT_*); `profile.py` machine profile (from discovery; limits set by a person only);
  `format.py` per-kind schemas that both validate and generate `study_format` (ls6t's deferred refactor 3, from day
  one); `plan.py` study -> adapter calls, estimates (`SemGetAcquisitionTimeEstimate` + stage + settle times);
  `adapter.py`; `fake.py`; `ppisim.py` (PPI simulator + injected images); `runner/` split from the start:
  `lifecycle.py` (request, lock, watchdog), `setup.py` (one instrument-setup path for studies and `instrument set`:
  ls6t refactor 1), `procedures/*.py` (one per kind), `analysis/` (images, focus, particles, stitching, EDS);
  `render.py` PNGs; `bench.py`; `api.py`, `cli.py`, `mcp_server.py`; `panel.py` (the operator window);
  `winsetup.py` + `installer/` (NSIS, as ls6t, but on the PC's Python 3.12 or a bundled 3.12 that finds the existing
  `PyPhenom.pyd`; the installer checks `import PyPhenom` and the version).
- Version: `YYYY.MM.DD.N`, set once in `phenom_translator/__init__.py`; CHANGELOG.md newest first;
  planning_log.md for the dated log (as ls6t).
- **Written so far (2026.11.23.1, phase 1)**: `config.py`, `store.py`, `profile.py`, `format.py`, `plan.py`
  (estimates only), `adapter.py` (tier 0, finding PyPhenom), `fake.py` (tier 0), `api.py`, `cli.py`,
  `mcp_server.py`; 65 tests (`tests/`: adapter incl. the static allow/forbid check of its PyPhenom names and
  `PhenomAdapter` on the PyPhenom stand-in `tests/ppi_stub`, profile, format, CLI, MCP over stdio).
  `PHNT_MODE=ppisim` is `PhenomAdapter(simulator=True)`; `ppisim.py` is needed only for image injection
  (`Phenom.Simulate`) in phase 2. Not yet: the runner and its lock, the operator panel, `connect`, the installer,
  test mode, `render.py`, `bench.py`.

### Adapter tiers (what PyPhenom calls phnt may make)

- **0, read**: modes, health, door, holder, stage position and stroke, ranges, current settings, SED and vacuum
  state, spectrometer status, properties, version, licenses (without the password), live image copies, overview,
  estimates. Always allowed.
- **1, imaging**: HFW, WD, autofocus / stigmation / contrast-brightness (each with its abort), detector and mix,
  gains, acquisitions (SEM, NavCam), spot mode for EDS, beam blank / unblank, spectra and EDS maps.
  kV, spot and emission preset, charge-reduction mode: in `setup`, within the profile's caps, read back.
  Inside a request that holds the instrument.
- **2, stage**: `MoveTo / MoveBy` (BacklashOnly) within the stroke, the holder map and the profile's
  `max_move_mm` from home; `SelectImagingDevice` (NavCam <-> SEM) after the operator's Yes the first time in a
  request.
- **3, operator only**, never in a study, each after the operator's Yes in the panel: `Load`, `UnloadSample`,
  `OpenDoor / CloseDoor`, `Activate` (Standby -> Operational, ~5 min), `Standby`.
- **Never**: calibration setters (`Set*Calibration*`, `SetVFWCalibrationRatio`), `SetSemSourceTilt`,
  `SemAutoSourceTilt` / `Application.AutoSourceTilt`, persistent stigmator, `PowerOff`, `Reboot`, `Hibernate`,
  `SetInstrumentMode`, users and passwords, `ActivateFeature`, licenses, `ConfirmBakeout`, `OverruleSafeStartupTime`,
  `ResetSpectrometer`, `SavePulseProcessorSettingsOnInstrument`, sample-holder registration and values, scan
  definitions and patterning (beam writing), `SemDegauss`, `CreateNewSourceStatistics`.

## Study kinds

A request is `{name: study}`; each study has a `kind`. All positions are offsets in µm (or mm) from the home spot
(where the operator left the stage, or where a `move` stayed); at the end the stage returns home.

| Kind | What it does |
|---|---|
| `image` | One SEM image at the current spot, or one per entry of `points` |
| `navcam` | A NavCam image, or the overview (no beam) |
| `move` | The stage to an offset, or onto a point picked in a snapshot or the overview; `stay` makes it home |
| `focus` | Autofocus (Phenom's), or a focus curve (`RoughFocus` with a criterion) with the best WD; the focus serves the rest of the request |
| `montage` | Tiles over an area with overlap, snake order, backlash-corrected moves, focus every N tiles or a focus map; stitched by phnt's own registration (phase correlation on the overlaps, then a global least-squares placement; the Stitch module only if Stitching is ever licensed) |
| `series` | Repeated images at one spot (time series: beam damage, drift, in-situ) |
| `calibration` | Pixel size and stage-to-image scale/rotation on a reference (grid); stage repeatability (BacklashOnly there and back); the NavCam -> SEM offset per holder (`FindInOverview`) |
| `particles` | Find particles in a BSD image with phnt's own segmentation (threshold, watershed, numpy/scipy): sizes, shapes, counts, positions in stage coordinates; optionally EDS on each when EDS exists |
| `eds_point` | Spectra at points (spot mode, placed from an image through `ToWorld`) or over the field; `.msa` written with `WriteMsaFile`; phnt's own background, peak fits and element identification using PyPhenom's free line energies (`LineEnergy`; a built-in table in `fake.py` off Windows); net intensities and ratios, no standardless quantification; with the Spectroscopy license some day: Thermo's identify and quantify |
| `eds_grid` | A coarse element map without the EdsMap license (`EdsLiveMap` is refused: "Missing license: EdsMap"): spot spectra on a grid with the clear-start-poll-get path (~0.2 s per point beyond the live time, moving the spot included: 32×32 points at 0.5 s live ≈ 12 min), per-element net-intensity maps |
| `eds_map` | *Only with EdsMap licensed.* An element map over the field (EdsLiveMap) |

Later: `ultrafocus` (focus stacking, height map) if it proves license-free; `roughness_3d` and `resolution` only if
licensed.

### EDS, three cases: **case 1 holds** (Q1b, 2026-11-23)

1. **Raw spectra work on the XL without the license** (this XL): `eds_point` with phnt's own analysis (line table,
   background, peak fits, identification, net intensities, ratios between points). Quantification stays out:
   standardless ZAF done badly is worse than none.
2. **Raw spectra are refused**: no EDS kinds; the Phenom's own EDS software stays the way to do EDS, and phnt can
   still drive the stage and imaging to the points an operator then analyses.
3. **Thermo adds Spectroscopy (and EdsMap)**: Thermo's identify, quantify and maps; ask for a quote for this XL's
   PPI license either way, to know the price of case 3.

### Options any study can use

| Key | What it does |
|---|---|
| `setup` | kV (or a preset name), spot preset or value, emission preset, charge reduction, detector and mix, WD; each read back |
| `acquire` | Size, frames, dwell, HDR, drift correction, interlace, HFW or pixel size; for EDS: time, live/acquisition, elements (or auto-identify) |
| `focus` | `auto`, `fine`, `curve`, `fixed_wd`; before the first point and every N points |
| `process` | Contrast normalisation, sharpness, particle segmentation, element lists for quantification |
| `expect` | Expected values (any result path) with tolerances, checked after the run |
| `images` | PNGs: images with scale bar, montages, focus curves, spectra with fits, element maps |
| `sample` | Name, notes (into the data bar label and sidecar), `sensitive` (lower kV and spot caps, charge reduction on) |

## What phnt checks

**Unreliable**: a setting clipped or not reached on read-back; the stage not within tolerance of its target; a
focus curve without an interior maximum or below the sharpness floor; saturated or empty images (HDR off);
charging (frame-to-frame shift, streaks; for EDS a Duane–Hunt limit well below the set kV); a door, mode, health or
vacuum change during the run; EDS with the detector not cold, dead time above the cap, too few counts, or WD outside
the acceptable EDX window; a stop before the end.

**Warnings**: WD outside the optimal EDX window; drift; low SNR; stale calibrations or NavCam offsets; a quantified
total far from 100 % before normalisation; elements found that were not asked for.

## Safety

- One request at a time holds the XL (`GetExclusiveAccess` with "phnt: <request>"; released on every path).
- The watchdog stops the request (abort acquisition, stop spectrum, blank the beam) on: the panel's STOP, a door or
  mode change, a health flag, the Phenom busy past a timeout, or the MCP client gone.
- Limits from the profile, set by a person: kV and spot caps (lower for `sensitive`), `max_move_mm` from home, the
  stroke and holder map, frames, dwell, EDS time, montage tiles, request minutes.
- The first beam-on of a request needs the operator's Yes (panel); so does every tier-3 command.
- The LLM can read the profile and remembered state, never change them (CLI only, as ls6t).

## What phnt remembers

Profile (`PHNT_HOME\profile.json`); NavCam -> SEM offsets per holder; scale/rotation and stage repeatability checks;
focus maps per holder position (short-lived); EDS detector history (temperature, resolution from fits); every
request under `PHNT_OUT\run_...` (studies, TIFFs with sidecars, `.msa`, maps, PNGs, results, PyPhenom's own log via
`Logging.LogToFile`).

## Testing

- `fake.py`: a pure-Python XL on any OS: a sample with particles of known size and composition on a substrate, a
  calibration grid, defocus vs WD, drift, charging, stage error with and without backlash correction, an operator who
  confirms or stops, and EDS spectra of known compositions (phnt's own simple model: `Spectroscopy.Simulate` is
  licensed too).
- The PPI simulator on the Windows PC (and Windows CI if PyPhenom can be installed there, which it probably cannot:
  then a manual `phnt bench --ppi` on the PC).
- Benchmarks with known answers: `image_basic`, `focus_curve`, `montage_stitch`, `backlash_revisit`,
  `particles_sizes`, `charging_detect`, `navcam_offset`, `operator_stop`, `door_open_stop`, `eds_point_lines`.
- TESTING.md with the maintainer at the XL (T0–Tn, questions Q1–Qn), `hardware_test` in test mode, as ls6t.

## Open questions for the instrument (seed of TESTING.md)

1. Q1 Which PPI features this license has. **Answered 2026-11-23: none** (all nine False).
   Q1b Does `AcquireSpectrum` work on the XL without the Spectroscopy feature? **Answered 2026-11-23: yes**
   (25743 counts in 1 s at 15 kV, while imaging). Still open for EDS: Q6 (spot mode and the units of the spot
   position), the spectrum's dimensions (offset, dispersion, bins), live vs acquisition time, dead time from
   `Spectrometer.GetStatus` (fast vs slow counts), and whether `EdsLiveMap` (licensed EdsMap) is refused.
   Q1c Which other non-instrument functions are license-free. **Answered 2026-11-23** on the XL (list above);
   `Application.UltraFocusAcquire` and `EdsLiveMap(phenom)` still to try.
2. Q2 The sign `SetSemHighTension` expects (negative, as `GetSemHighTension` reports?). Simulator first.
3. Q3 Does the exclusive-access message show on the Phenom's screen; does it lock out the operator's UI?
4. Q4 `Activate` from Standby: time to operational; ranges (HFW, spot) once operational.
5. Q5 Stage repeatability with BacklashOnly vs Auto (there-and-back, measured by image shift).
6. Q6 **Answered**: fractions of the field, +x right, +y down (above). Open: non-square fields (the live view),
   and `SpotPosition.Accuracy`'s meaning.
7. Q7 **Answered**: `EdsLiveMap(phenom)` raises "Missing license: EdsMap".
8. Q8 **Answered** (above). Open: the spot-size unit (A/√V per the docstring).
9. Q9 **Answered**: kelvin (234.7 K). Open: the "ready" threshold (record the temperature at every spectrum;
   flag a rise of more than a few K).
10. Q10 Do PPI acquisitions show in the Phenom UI's live view (operator visibility)?
11. Q11 Standby during long runs: does a request need `ResetStandbyTimer`?
12. Q12 What `GetSampleHolderMap(100)` returns for the manual-height holder (stub positions?).
13. Q13 Does `RequiresLogin` matter with a user logged in at the Phenom UI?
14. Q14 `Phenom.Simulate(acq)` on the simulator: which sizes, and does the next acquisition follow HFW and position?
15. Q15 `Application.ToWorld`: **answered** for the metadata (pixels -> stage m, row down = −Y). Open: does a
    `MoveTo` to a `ToWorld` point put that feature at the image centre (stage accuracy, rotation)?
16. Q16 Charge-reduction switching time and `isStable`; SED enabling time.
17. Q17 **Answered**: ~0.15–0.2 s per point on the asynchronous path, moving the spot 0.01–0.03 s.
18. Q18 **Answered**: gain right, axis ~12 eV low (above).
19. Q19 **Answered**: no call stops a spectrum early (above).
20. Q20 **Answered**: the spot preset has no measurable effect; not used.
21. Q21 **Answered**: `Spectrometer.ClearSpectrum()` before every start.
22. Q6b **Answered**: x and y are fractions of the field width.

EDS bring-up is complete for phnt's design (eds_tests.py, eds_tests2.py, eds_tests3.py and their folders go into
`docs/discovery/`). Left for TESTING.md at build time: the energy correction on a second known sample, spectra at
other kV and spot settings (count rate and dead time against spot size), and charging on an uncoated insulator.

Q22 **Answered** (2026-11-23): phnt reading `Spectrometer.GetStatus` every 0.5 s did not disturb the Phenom UI's
EDS: its spot spectrum ran and finished normally, no message in the UI. (One spectrum: watch for it in later runs.)

## State log

The dated log of what was done, found at the instrument and decided: [planning_log.md](planning_log.md) (add new
entries at its end).

## To do next

1. ~~The repo: `docs/discovery/`, this file, README~~ (2026-11-23).
2. EDS is case 1. Optionally, a quote from Thermo for Spectroscopy + EdsMap (quantification and maps).
3. ~~Phase 1~~ (2026.11.23.1): read-only adapter, fake XL, profile, study format,
   validation, estimates, CLI, MCP server. **At the XL: TESTING.md T0–T6** (install into Python 3.12, status in Standby and live, status while the
   Phenom UI acquires, discover and import the profile, the PPI simulator, the Claude app).
4. Phase 2: the request lifecycle (request folders, the detached runner, `run_studies` / `study_status` / `cancel` /
   `jobs`, the instrument lock with `GetExclusiveAccess`), the operator panel (STOP, Yes/No) and the watchdog
   (events), `image`, `navcam`, `move`, `focus` on tiers 1–2; the fake XL's images (a sample with particles and a
   grid, defocus vs WD, drift, stage error with and without backlash); `ppisim.py`; `render.py`, `get_image`,
   `get_file`; first benchmarks; test mode (`hardware_test`) and TESTING.md phase 2.
5. Phase 3: `montage`, `series`, `calibration`, `particles`.
6. Phase 4: `eds_point` (case 1: PyPhenom's line energies, phnt's peak fits), `eds_grid`; particles with EDS.
7. Phase 5: installer, `connect`, first release.
