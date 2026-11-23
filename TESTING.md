# Testing phnt at the Phenom XL

Tests on the instrument with the maintainer, phase by phase. Results go in the table at the end (date, version,
result, notes). The open questions (Q-numbers) are in [planning.md](planning.md); the bring-up answers so far are in
[docs/discovery](docs/discovery/README.md).

## Phase 1: read only (nothing moves, the beam is not touched)

**T0 Install.** On the instrument PC, in this repository: `py -3.12 -m pip install -e ".[mcp]"`.
Pass: `py -3.12 -m phenom_translator.cli --version` prints the version; `py -3.12 -m phenom_translator.cli status`
shows `"pyphenom": {"version": "2.1.0", "path": "C:\\Program Files\\Python312\\DLLs\\PyPhenom.pyd", ...}` and
`"PHNT_MODE": "phenom"`. Also in a venv made from that Python (`py -3.12 -m venv .venv`): `status` still finds
PyPhenom (`found_by` "import" or "folder"); if not, `set PHNT_PYPHENOM=C:\Program Files\Python312\DLLs` and note it.

**T1 Status, instrument in Standby.** `py -3.12 -m phenom_translator.cli instrument status` with the XL in Standby.
Pass: `ok` true, no `read_errors`; `summary.can_image` false; a warning names Standby; kV positive; holder
`XlManualHeight`; licenses all false.

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
| T1 | | | | |
| T2 | 2026-11-23 | 2026.11.23.1 | pass | live SEM, 15 kV, spot 5.1, WD 3.9 mm, HFW 620.75 µm; no read errors; `can_image`, `eds_ready` true. Found: vacuum not stable (target Off, 12.9 Pa) and SED NotAllowed without a warning; holder name `XL Manual Height` (fixed in .2) |
| T3 | | | | |
| T4 | 2026-11-23 | 2026.11.23.1 | partial | discover ok, properties identical to the probe; the proposal narrowed `ranges.hfw_um` to 755 µm (the max at WD 3.9 mm): fixed in .2; discover again with .2 before importing |
| T5 | | | | |
| T6 | | | | |
