# Testing phnt at the Phenom XL

Tests on the instrument with the maintainer, phase by phase. Results go in the table at the end (date, version,
result, notes). The open questions (Q-numbers) are in [planning.md](planning.md); the bring-up answers so far are in
[docs/discovery](docs/discovery/README.md).

## Phase 1: read only (nothing moves, the beam is not touched)

**All of T1–T5 in one command** (from 2026.11.23.3), on the instrument PC in the repository folder:

```
python -m phenom_translator.cli report --watch 180 --out "$env:USERPROFILE\Desktop\phnt_report.txt"
```

During the 3 minutes, in the Phenom UI: take an image (T3), take an EDS spectrum (T3), then put the instrument in
Standby and wake it again (T1). The report lists each change with its time and any read that failed, in which mode.
Send `phnt_report.txt` (and `phnt_report.json` if asked). Changes are printed as they happen, with a line every
30 s when nothing changes. From 2026.11.23.5 the watch reads every 0.5 s (only what changes quickly; a full status
every 30 s), so a short acquisition is not missed between reads; leave about 10 s between the steps. (PowerShell ISE shows anything a program writes to stderr as a red NativeCommandError:
pip's warnings look like failures there; phnt writes nothing to stderr from 2026.11.23.4.)

**T0 Install.** On the instrument PC, in this repository: `py -3.12 -m pip install -e ".[mcp]"`.
Pass: `py -3.12 -m phenom_translator.cli --version` prints the version; `py -3.12 -m phenom_translator.cli status`
shows `"pyphenom": {"version": "2.1.0", "path": "C:\\Program Files\\Python312\\DLLs\\PyPhenom.pyd", ...}` and
`"PHNT_MODE": "phenom"`. Also in a venv made from that Python (`py -3.12 -m venv .venv`): `status` still finds
PyPhenom (`found_by` "import" or "folder"); if not, `set PHNT_PYPHENOM=C:\Program Files\Python312\DLLs` and note it.

**T1 Status, instrument in Standby.** `py -3.12 -m phenom_translator.cli instrument status` with the XL in Standby.
Pass: `ok` true, no `read_errors`; `summary.can_image` false; a warning names Standby; kV positive; holder
`XL Manual Height`; licenses all false.

**T2 Status, live SEM imaging.** The same while imaging a sample in the Phenom UI.
Pass: `summary.can_image` true, `eds_ready` true (detector ~234.7 K), `warnings` empty; kV, spot, WD and HFW as the
Phenom UI shows them; the viewing mode 960×540, 4 frames.

**T3 Status with the Phenom UI busy.** During an image acquisition, and during an EDS acquisition started in the
Phenom UI. Pass: no `read_errors`, or reads that fail say why (OM_CONTEXT, busy) without failing the whole status;
`spectrometer.acquiring` true during the EDS acquisition. (Answers: can phnt read while the UI works?)

**T4 Discover and profile.** `py -3.12 -m phenom_translator.cli instrument discover`, then read
`%USERPROFILE%\phnt\profile.proposed.json` with the maintainer: ranges, presets, EDX windows, licenses as the
discovery files show; limits as wanted (`limits.kv_max`, `spot_max`, `max_move_mm`, `eds_live_s_max`, …). Then
`py -3.12 -m phenom_translator.cli profile import %USERPROFILE%\phnt\profile.proposed.json --who NAME`.
Pass: `reviewed` true; `phnt format` shows the profile's values.

**T5 PyPhenom's simulator.** `set PHNT_MODE=ppisim` then `instrument status`. Pass: a status with `backend`
`ppisim`; note which reads the simulator refuses (licenses) for the record.

**T6 The MCP server in the Claude desktop app.** Add `phnt` to the app's configuration (README), restart it, ask
"what is the state of the Phenom?" and "validate a 32×18 EDS grid at 0.5 s per point". Pass: the app calls
`instrument` and `validate_studies` and reports `can_image`, the warnings and an estimate of about 7 minutes.

## Results

| Test | Date | Version | Result | Notes |
|---|---|---|---|---|
| T0 | 2026-11-23 | 2026.11.23.1 | pass | Python 3.12.2, PyPhenom 2.1.0 found by plain import (`C:\Program Files\Python312\DLLs`), mcp 2.3.0; installed from the GitHub zip; run as `python`. Venv not tried |
| T1 | 2026-11-23 | 2026.11.23.3 | not observed | no Standby during the watch: rerun with .5 |
| T2 | 2026-11-23 | 2026.11.23.1 | pass | live SEM, 15 kV, spot 5.1, WD 3.9 mm, HFW 620.75 µm; no read errors; `can_image`, `eds_ready` true. Found: vacuum not stable (target Off, 12.9 Pa) and SED NotAllowed without a warning; holder name `XL Manual Height` (fixed in .2) |
| T3 | 2026-11-23 | 2026.11.23.3 | not observed | watch of 180 s, 90 full reads every 2 s, 0.39 s mean / 0.92 s max, no read errors; the mode stayed `LiveSem` and EDS never read acquiring (nothing done in the UI, or missed between reads): rerun with .5 |
| T2 | 2026-11-23 | 2026.11.23.3 | pass | in the report: watch during a pump-down, 18.8 → 0.1 Pa in ~36 s, stable at ~50 s; SED `NotAllowed` → `Disabled` between 2.5 and 1.8 Pa; WD 3.3 mm, largest field 726.0 µm |
| T3 | 2026-11-23 | 2026.11.23.5 | pass | quick reads 0.17 s mean / 0.99 s max, full 0.40 s; two images (`AcquireSemImage` 53.6 s, then 0.5 s), an EDS spot spectrum (scan `Spot`, ~7 s): every read went on, except `Spectrometer.GetStatus`, refused while the UI's EDS held the detector (15 reads: `Access denied … is another application using it?`; a state from .6). A sample exchange: `Unloading` 33 s, `Loadpos` door open ~8 s, `SelectingNavCam` 3 s, `LiveNavCam`, `SelectingSem` > 40 s (0.65 Pa); the HFW range is refused outside NavCam/SEM (a state from .6). Largest field 1003.2 µm at WD 8.7 mm |
| T1 | 2026-11-23 | 2026.11.23.5 | not observed | no Standby in this watch (a sample exchange instead) |
| T4 | 2026-11-23 | 2026.11.23.2 | discover pass | rerun with .2: no warnings, no changes in the proposal, vacuum stable 0.1 Pa, SED Disabled. Import after reviewing the limits |
| T4 | 2026-11-23 | 2026.11.23.1 | partial | discover ok, properties identical to the probe; the proposal narrowed `ranges.hfw_um` to 755 µm (the max at WD 3.9 mm): fixed in .2; discover again with .2 before importing |
| T5 | 2026-11-23 | 2026.11.23.3 | pass | the simulator connects; it reports holder `XL1 Motorized Height`, 42 Pa, 5.3 kV, `can_image` false; it refuses the spectrometer (`Missing license: Spectroscopy`) and the features (`500 resolve: No such host is known`) |
| T6 | | | | |
