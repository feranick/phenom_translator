# phenom-translator (phnt)

SEM studies written as JSON -> a Thermo Scientific **Phenom XL** with EDS, through **PyPhenom** (the Phenom
Programming Interface) on the Windows PC connected to the microscope; checked results, a command line (`phnt`) and
an MCP server (`phnt-mcp`) that LLM apps (the Claude desktop app and others) run locally on that PC.

It is a translator in the sense of llm-translators (`docs/create_new_translators.md`): the LLM writes a study in the
user's terms; phnt validates it (every error says the fix), turns it into PyPhenom calls itself, checks every run and
says `reliable: false` with the reasons when a check fails. Like [labspec_translator (ls6t)](https://github.com/feranick/labspec_translator)
for the HORIBA Raman, and print3d_translator (p3dt) for OrcaSlicer, it lives outside llm-translators: it runs only on
the instrument PC, one request at a time, with no SLURM and no router. Design and state: [planning.md](planning.md);
the evidence behind every fact about the instrument: [docs/discovery](docs/discovery/README.md).

**Scope.** Imaging (BSD, SED), focus, stage moves, NavCam; montages, series, particles, calibration; EDS spectra at
spots or on grids with element identification. Out of scope: EDS quantification and EDS maps (Thermo licenses this XL
does not have), anything that changes the instrument's calibration, alignment, power, users or licenses.

## Status

| Phase | What | State |
|---|---|---|
| 1 | Read the instrument (read only), machine profile from discovery, study format, validation and estimates, CLI, MCP server, fake XL | **done** |
| 2 | `image`, `navcam`, `move`, `focus`; request folders and the runner, the instrument lock, the operator panel (STOP, Yes/No), the watchdog | next |
| 3 | `montage` (phnt's own stitching), `series`, `calibration`, `particles` | |
| 4 | `eds_point`, `eds_grid`, particles with EDS | |
| 5 | Windows installer, `phnt connect` for the LLM apps, first release | |

Phase 1 never moves the stage, switches the beam or acquires anything: the adapter uses only read-only PyPhenom
calls, and the tests check its source against the list of allowed and forbidden PyPhenom names.

## Install

PyPhenom is not on PyPI: it comes from Thermo Fisher with the PPI license and is a compiled module for one Python
version. On this XL's PC: PyPhenom 2.1.0, `C:\Program Files\Python312\DLLs\PyPhenom.pyd`, so phnt runs there on
**Python 3.12**. phnt finds it with a plain import, then `PHNT_PYPHENOM` (the folder holding the `.pyd`), then the
DLLs folder of the Python a venv was made from, then the usual Windows installs of that Python version.

On the instrument PC, in this repository:

```
py -3.12 -m pip install -e ".[mcp]"
py -3.12 -m phenom_translator.cli status            # "pyphenom": {"version": "2.1.0", ...}
py -3.12 -m phenom_translator.cli instrument status
```

On any other machine (development, CI), with the fake XL:

```
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[mcp,test]"
PHNT_MODE=fake phnt instrument status
pytest
```

The Windows installer and `phnt connect` come with phase 5. Until then, add the MCP server to the Claude desktop app
by hand (Settings > Developer > Edit config, `mcpServers`):
`"phnt": {"command": "C:\\Program Files\\Python312\\python.exe", "args": ["-m", "phenom_translator.mcp_server"]}`,
then restart the app.

## Use

| Command | What it does |
|---|---|
| `phnt status` | Versions, PyPhenom found or not, how it runs, the settings, the profile (JSON) |
| `phnt format` | The study format: kinds (with the phase that runs them), blocks, units, ranges, presets, limits |
| `phnt validate studies.json` | `{name: {ok, errors, warnings, estimate}}`; each error says the fix; `-` reads stdin; exit 1 if any fails |
| `phnt instrument status` | The instrument now, read only, with a summary (`can_image`, `eds_ready`) and warnings |
| `phnt instrument discover` | The same plus the instrument's properties, saved; writes `profile.proposed.json` |
| `phnt profile show / default / propose / import FILE / set KEY VALUE` | The machine profile; only a person imports or changes it |
| `phnt fake state / set KEY=JSON / reset` | The fake XL's state (`PHNT_MODE=fake`) |

## A study

```json
{"three_spots": {"kind": "eds_point", "sample": {"name": "C-Ni"},
                 "setup": {"kv": 15, "spot": "Map", "wd_mm": 6.3},
                 "eds": {"live_s": 2, "repeats": 2, "spots": [[0, 0], [0.2, -0.1], [-0.25, 0.15]],
                         "elements": ["C", "O", "Ni", "P"]}}}
```

Kinds: `image`, `navcam`, `move`, `focus`, `montage`, `series`, `calibration`, `particles`, `eds_point`, `eds_grid`
([examples/studies.json](examples/studies.json) has one of each; all validate). Blocks: `sample`, `setup` (kV and spot
as numbers or the Phenom's preset names, emission, charge reduction, detector, WD), `acquire`, `focus`, `points`,
`move`, `navcam`, `montage`, `series`, `calibration`, `particles`, `eds`, `eds_grid`; `expect` and `images` at the top.

Conventions: stage positions are offsets in µm from the home spot (where the operator left the stage), stage axes
(+y up); the scan centre and EDS spots are fractions of the field **width** in image axes (+x right, +y down);
kV positive. Units are in the key names (µm, mm, kV, s).

**Results** (from phase 2) follow the llm-translators contract: `ok`, `reliable`, `unreliable_because`, `warnings`,
`checks`, `expect` (`{quantity, value, got, tol, pass}`), the results under dotted keys, `images`, `files`, `seconds`,
`execution`. Every image keeps a JSON sidecar with the instrument's own metadata (pixel size, stage position, kV, WD,
spot, dwell, detector, pressure, holder, time); every spectrum an `.msa` file.

## The checker

Each run checks itself (from phase 2): settings read back after every change (PyPhenom clips values silently,
`OM_CLIPPED`); the stage within tolerance of its target; focus curves with an interior maximum; no saturated or
empty images; drift and charging between frames; EDS spectra whose real time matches the time asked (a running total
is refused), a cold detector, dead time within its cap, enough counts, the WD inside the EDX window; door, mode,
health or vacuum changes during the run. A failed check gives `reliable: false` with the reason, and the model is
told not to report those numbers. The reference for the tests is the fake XL, which answers with the values measured
on this instrument; benchmarks with known answers come with each phase.

### Assumptions about PyPhenom (and what catches each one if it is wrong)

| Assumption | Catches it |
|---|---|
| PyPhenom 2.1.0 for Python 3.12; `ppi.Phenom()` connects with the license installed on the PC | `phnt status` (`pyphenom`), TESTING T0–T1 |
| High tension is reported negative (−15000 V); the EDS metadata has it positive | `adapter.kv()`; the stub test; TESTING T2 against the Phenom UI |
| Enums print as `PyPhenom.<Enum>.<Name>` | `adapter.short()`; the stub test; TESTING T1 |
| `GetProperty<Type>` raises for the wrong type | `properties()` tries each; the stub test; TESTING T4 |
| Reads may be refused while the Phenom UI works (`OM_CONTEXT`) | status reports each failed read instead of failing; TESTING T3 |
| The EDS detector reads kelvin, ~234.7 K when ready | `eds_ready` below 245 K; TESTING T2 |
| The stage is accurate to ~35 µm point to point, better with backlash correction | every move uses `BacklashOnly`; the `stage_repeatability` calibration (phase 3) |
| The scan centre and EDS spots are fractions of the field width, +x right, +y down; no signal past the field's edge | measured (docs/discovery, rounds 1–2); validation limits; image registration in the `grid` calibration (phase 3) |
| `Application.ToWorld` ignores the scan centre | measured (round 2); phnt adds the offset and checks it on images (phase 2) |
| `StartAcquireSpectrum` adds to the previous spectrum unless `Spectrometer.ClearSpectrum()` comes first | measured (round 3); every spectrum's real time checked against the time asked (phase 4) |
| A spectrum cannot be stopped early | measured (round 2); `limits.eds_live_s_max` per spectrum; the watchdog's worst case is one spectrum |
| The energy axis comes with each spectrum (the map preset: 9.8616 eV/channel, −56.23 eV) and reads ~12 eV low | measured (round 1); the `eds_energy` calibration (phase 4) |
| The simulator enforces the PPI license, the XL does not for raw EDS | measured; a "Missing license" at run time turns the EDS kinds off with the reason (phase 4); TESTING T5 |

## How it works

| Module | What it does |
|---|---|
| `adapter.py` | The only module that imports PyPhenom: fixed verbs by tier (0 read, 1 imaging and EDS, 2 stage, 3 operator only), the tables of allowed and forbidden PyPhenom names, finding PyPhenom, the status summary and warnings |
| `fake.py` | phnt's own XL for any OS, answering with the values measured on 2026-11-23 |
| `profile.py` | The machine profile: defaults, the proposal from a discovery, import and set by a person |
| `format.py` | One schema per block and kind: validation and `study_format` from the same source |
| `plan.py` | Time estimates from the measured timings (study -> PyPhenom calls from phase 2) |
| `api.py`, `cli.py`, `mcp_server.py` | The functions, the command line, the MCP server |
| `config.py`, `store.py` | Settings; the small JSON files phnt keeps, written atomically |

## For LLM tools: the MCP server

`phnt-mcp` (stdio; `--http 8772` for HTTP). It answers the handshake at once and reads the instrument only when a
tool asks. Tools in phase 1: `study_format`, `validate_studies`, `instrument` (status, discover). From phase 2:
`run_studies` and `study_status` (`wait_s` up to 50 s; long runs come back pending with an ETA: polling costs tokens,
so past about 5 minutes the model tells the user when to come back), `cancel`, `jobs`, `get_file`, `get_image`,
`get_inputs`, `run_benchmarks`, `bench_status`.

## Settings

| Variable | Meaning | Default |
|---|---|---|
| `PHNT_MODE` | `phenom` (the XL), `ppisim` (PyPhenom's simulator, Windows), `fake` (phnt's own, any OS) | `phenom` |
| `PHNT_PYPHENOM` | the folder holding `PyPhenom.pyd`, when this Python does not import it by itself | unset |
| `PHNT_HOME` | profile, discovery, remembered state | `~/phnt` |
| `PHNT_OUT` | request folders; the simulators' records (`sim_*`) | `~/phnt_runs` |
| `PHNT_PROFILE` | the machine profile | `$PHNT_HOME/profile.json` |
| `PHNT_MAX_MINUTES` | ceiling for one study's estimate (below `limits.study_minutes_max`) | unset |

phnt has no setting for credentials: PyPhenom connects with the PPI license installed on the instrument PC, and phnt
never reads, stores or prints license details.

## Files

```
phenom_translator/   adapter.py, fake.py, profile.py, format.py, plan.py, api.py, cli.py, mcp_server.py, config.py,
                     store.py
tests/               pytest: the fake XL, and PhenomAdapter on a PyPhenom stand-in (tests/ppi_stub)
examples/            studies.json
docs/discovery/      the PyPhenom dumps, the probe, the EDS bring-up scripts and their results
planning.md          design and state; planning_log.md: the dated log; TESTING.md: tests at the XL
```

## Versions

`YYYY.MM.DD.N`, N counting the releases of that day, set only in `phenom_translator/__init__.py` (`phnt --version`);
what changed in each: [CHANGELOG.md](CHANGELOG.md).

| Version | Phase | Notes |
|---|---|---|
| 2026.11.23.1 | 1 | read-only adapter (with the PyPhenom finder), fake XL, profile, study format, validation and estimates in the llm-translators contract's shapes, CLI, MCP server |
