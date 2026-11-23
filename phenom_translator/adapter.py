"""adapter.py — the only module that talks to the microscope.

Nothing else in phnt imports PyPhenom. The adapter offers a fixed set of verbs, each in a tier:

  0  read        always allowed: modes, health, door, holder, stage, ranges, settings, licenses, properties
  1  imaging     inside a request that holds the instrument: HFW, WD, focus, detectors, images, EDS spectra
  2  stage       inside a request, within the profile's limits: backlash-corrected moves, NavCam <-> SEM
  3  operator    never inside a study, each after the operator's Yes: load, unload, door, activate, standby

This version (phase 1) implements tier 0 only. PPI_ALLOWED lists every PyPhenom name the adapter may use (with the
tier that will use it); PPI_FORBIDDEN lists the names it must never use. tests/test_adapter.py reads this file's
source and fails on any PyPhenom name outside PPI_ALLOWED or inside PPI_FORBIDDEN.

Conventions (measured on the XL, 2026-11-23, see planning.md):
  - high tension: PyPhenom reports it negative (−15000 V); the adapter speaks positive kV;
  - lengths in the adapter's answers are in SI units with the unit in the key (x_m, hfw_m, wd_m);
  - enums are returned as their short names ("Standby", "LiveSem").
"""
from __future__ import annotations

from . import config

# PyPhenom names the adapter may use, by tier. Tier 0 ones are used now; the others are listed for the phases to come
# so that adding them is a reviewed change to this table, not a silent one.
PPI_ALLOWED = {
    # module level and types (no instrument access)
    "Phenom": 0, "__version__": 0, "HasLicense": 0, "Features": 0, "SampleHolderType": 0, "Name": 0,
    "Error": 0, "Position": 1, "Size": 1, "ScanParams": 1, "ScanParamsEx": 1, "DetectorMode": 1, "ScanMode": 1,
    "EdsTimeType": 1, "NavigationAlgorithm": 2, "ImagingDevice": 2, "OperationalMode": 0, "Save": 1,
    "Application": 1, "ToWorld": 1, "RoughFocus": 1, "Spectroscopy": 1, "WriteMsaFile": 1, "LineEnergy": 1,
    "EstimateIcr": 1, "Processing": 1, "GetShift": 1, "GetFocusCriteria": 1,
    # tier 0: reads
    "GetInstrumentMode": 0, "GetOperationalMode": 0, "GetSemDeviceMode": 0, "GetDoorStatus": 0,
    "GetSampleHolder": 0, "GetStageModeAndPosition": 0, "GetStageStroke": 0, "GetHFW": 0, "GetHFWRange": 0,
    "GetSemHighTension": 0, "GetSemHighTensionRange": 0, "GetSemSpotSize": 0, "GetSemSpotSizeRange": 0,
    "SemGetEmissionCurrent": 0, "GetSemWD": 0, "GetSemWDRange": 0, "SemHasSed": 0, "SemGetSedState": 0,
    "SemGetVacuumChargeReductionState": 0, "SemGetAllowedVacuumChargeReduction": 0,
    "GetExclusiveAccessStatus": 0, "Spectrometer": 0, "GetStatus": 0, "GetInstrumentHealth": 0,
    "GetActivatedFeatures": 0, "GetPropertyNames": 0, "GetPropertyDouble": 0, "GetPropertyInt": 0,
    "GetPropertyBool": 0, "GetPropertyString": 0, "GetSemViewingMode": 0, "SemGetBlankBeamState": 0,
    "IsAcquiringSpectrum": 0, "Connected": 0, "RequiresLogin": 0, "GetCurrentUser": 0,
    # tier 1: imaging and EDS (phase 2 and 4)
    "GetExclusiveAccess": 1, "ReleaseExclusiveAccess": 1, "SetHFW": 1, "SetSemWD": 1, "SemAutoFocus": 1,
    "SemAbortAutoFocus": 1, "SemAutoContrastBrightness": 1, "SemAutoStigmate": 1, "SemAbortAutoStigmate": 1,
    "SemAcquireImage": 1, "SemAcquireImageEx": 1, "BeginSemAcquisition": 1, "SemGetAcquisition": 1,
    "AbortAcquisition": 1, "SemGetAcquisitionTimeEstimate": 1, "NavCamAcquireImage": 1,
    "NavCamGetOverviewImage": 1, "SetSemViewingMode": 1, "SemBlankBeam": 1, "SemUnblankBeam": 1,
    "SetSemHighTension": 1, "SetSemSpotSize": 1, "SemSetEmissionCurrent": 1, "SemSetTargetVacuumChargeReduction": 1,
    "SemSetDetectorMixFactors": 1, "SemEnableSed": 1, "SemWaitForSedEnabled": 1, "SetSemBrightness": 1,
    "SetSemContrast": 1, "StartAcquireSpectrum": 1, "GetSpectrum": 1, "ClearSpectrum": 1, "ResetStandbyTimer": 1,
    # tier 2: stage
    "MoveTo": 2, "MoveBy": 2, "SelectImagingDevice": 2, "MoveToSem": 2, "MoveToNavCam": 2,
    # tier 3: operator only, never inside a study
    "Load": 3, "UnloadSample": 3, "OpenDoor": 3, "CloseDoor": 3, "Activate": 3, "Standby": 3,
}

# Never: calibrations, alignment, power, users, licenses, firmware-side settings, beam writing.
PPI_FORBIDDEN = {
    "SetHFWCalibration", "SetImageDeviceCalibration", "SetNavCamRotationCalibration", "SetStageCenterCalibration",
    "SetStageCorrectionCalibration", "SetVFWCalibrationRatio", "SetSemSourceTilt", "SemAutoSourceTilt",
    "AutoSourceTilt", "SetSemStigmate", "PowerOff", "Reboot", "Hibernate", "SetInstrumentMode", "AddUser",
    "RemoveUser", "ChangePassword", "Login", "Logout", "ActivateFeature", "InstallLicense", "UninstallLicense",
    "GetLicenses", "GetLicenseExpiryDate", "ConfirmBakeout", "OverruleSafeStartupTime", "ResetSpectrometer",
    "SavePulseProcessorSettingsOnInstrument", "RegisterSampleHolder", "SampleHolderSetValue",
    "SampleHolderCallOperation", "SetSemScanDefinition", "SetSemScanLines", "Patterning", "SemDegauss",
    "CreateNewSourceStatistics", "SetStandbyTimeout", "ApplySettings", "SetDatabarFields", "SetDatabarLabel",
    "GenerateSysInfo", "MultiStageSetCenterCalib", "MultiStageSetSampleRadius", "Unload",
}

LICENSE_FEATURES = ("Spectroscopy", "Stitching", "ParticleMetric", "RoughnessReconstruction", "AsbestosDetection",
                    "LiveVideo", "FastSpectrum", "EdsMap", "ResolutionMeasurement")
HEALTH_FLAGS = ("DoorOpen", "ElectronicsOK", "ImageEngineOK", "NavCamOK", "OpticsOK", "SampleOK", "SourceOK",
                "StageOK", "SystemOK", "VacuumOK")


class AdapterError(RuntimeError):
    """The microscope cannot be reached, or refused something; the message says what to do."""


_PPI = {}  # the imported PyPhenom module and how it was found, once per process


def pyphenom_places() -> list:
    """Where PyPhenom.pyd is looked for, after PHNT_PYPHENOM and a plain import: the DLLs folder of the Python this
    venv was made from (PyPhenom 2.1.0 sits in C:\\Program Files\\Python312\\DLLs on the instrument PC), then the
    usual Windows installs of this Python version."""
    import os
    import sys
    from pathlib import Path
    xy = f"{sys.version_info.major}{sys.version_info.minor}"
    places = [Path(sys.base_prefix) / "DLLs"]
    if os.name == "nt":
        places += [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / f"Python{xy}" / "DLLs",
                   Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / f"Python{xy}" / "DLLs",
                   Path(f"C:\\Python{xy}") / "DLLs"]
    seen, out = set(), []
    for p in places:
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out


def find_pyphenom():
    """(module or None, info). info is {version, path, found_by} when found, {error, searched} when not: the shape
    llm-translators reads for a backend. Importing PyPhenom does not connect to the microscope."""
    if "module" in _PPI:
        return _PPI["module"], _PPI["info"]
    import importlib
    import sys
    tried = []
    candidates = ([("PHNT_PYPHENOM", config.pyphenom_dir())] if config.pyphenom_dir() else []) + [("import", None)] \
        + [("folder", p) for p in pyphenom_places()]
    mod, info, last_error = None, None, None
    for how, folder in candidates:
        if folder is not None:
            tried.append(str(folder))
            if not (folder / "PyPhenom.pyd").exists() and not (folder / "PyPhenom.py").exists() \
                    and not any(folder.glob("PyPhenom*.pyd")):
                continue
            if str(folder) not in sys.path:
                sys.path.insert(0, str(folder))
        try:
            mod = importlib.import_module("PyPhenom")
        except ImportError as e:
            last_error = str(e)
            continue
        info = {"version": getattr(mod, "__version__", None), "path": getattr(mod, "__file__", None),
                "found_by": how}
        break
    if mod is None:
        info = {"error": "PyPhenom not found" + (f" ({last_error})" if last_error and "No module" not in last_error
                                                 else ""),
                "searched": ["PHNT_PYPHENOM", "this Python's imports"] + tried,
                "note": "PyPhenom exists only on the instrument PC (2.1.0 for Python 3.12); elsewhere use "
                        "PHNT_MODE=fake. A .pyd built for another Python version does not load."}
    _PPI.update(module=mod, info=info)
    return mod, info


def short(e) -> str:
    """An enum's short name: PyPhenom.InstrumentMode.Standby -> 'Standby'."""
    return str(e).split(".")[-1]


def kv(volts) -> float:
    """PyPhenom's high tension (negative volts) -> positive kV."""
    return round(abs(float(volts)) / 1000.0, 4)


class Adapter:
    """The verbs, independent of what answers them (the XL, PyPhenom's simulator, or phnt's fake)."""

    name = "adapter"

    # tier 0 primitives, implemented by each backend ---------------------------------------------------------
    def versions(self) -> dict: raise NotImplementedError
    def instrument_mode(self) -> str: raise NotImplementedError
    def operational_mode(self) -> str: raise NotImplementedError
    def sem_mode(self) -> str: raise NotImplementedError
    def door(self) -> str: raise NotImplementedError
    def holder(self) -> dict: raise NotImplementedError
    def stage(self) -> dict: raise NotImplementedError
    def stroke(self) -> dict: raise NotImplementedError
    def hfw(self) -> dict: raise NotImplementedError
    def high_tension(self) -> dict: raise NotImplementedError
    def spot(self) -> dict: raise NotImplementedError
    def emission(self) -> dict: raise NotImplementedError
    def wd(self) -> dict: raise NotImplementedError
    def sed(self) -> dict: raise NotImplementedError
    def charge_reduction(self) -> dict: raise NotImplementedError
    def exclusive(self) -> dict: raise NotImplementedError
    def viewing_mode(self) -> dict: raise NotImplementedError
    def beam_blank(self) -> str: raise NotImplementedError
    def spectrometer(self) -> dict: raise NotImplementedError
    def health(self) -> dict: raise NotImplementedError
    def licenses(self) -> dict: raise NotImplementedError
    def features(self) -> list: raise NotImplementedError
    def properties(self) -> dict: raise NotImplementedError

    # composed reads --------------------------------------------------------------------------------------------
    READS = ("versions", "instrument_mode", "operational_mode", "sem_mode", "door", "holder", "stage", "stroke",
             "hfw", "high_tension", "spot", "emission", "wd", "sed", "charge_reduction", "exclusive",
             "viewing_mode", "beam_blank", "spectrometer", "health", "licenses", "features")

    # what changes from second to second: read often by watches (and the phase-2 watchdog); a full status took
    # 0.39 s on the XL (2026-11-23), too long to poll fast
    QUICK = ("instrument_mode", "operational_mode", "door", "sed", "charge_reduction", "viewing_mode", "spectrometer")

    def status(self) -> dict:
        """Every tier-0 read; a read that fails is reported with its error instead of failing the whole status."""
        return self._reads(self.READS)

    def quick(self) -> dict:
        """The few reads that change from second to second (QUICK), with the same summary and warnings."""
        return self._reads(self.QUICK)

    def _reads(self, names) -> dict:
        out, errors = {"backend": self.name}, {}
        for r in names:
            try:
                out[r] = getattr(self, r)()
            except NotImplementedError:
                raise
            except Exception as e:  # noqa: BLE001 - one unreadable value must not hide the rest
                out[r] = None
                errors[r] = f"{type(e).__name__}: {e}"
        if errors:
            out["read_errors"] = errors
        out["summary"], out["warnings"] = summarise(out)
        return out

    def discover(self) -> dict:
        """status() plus the instrument's properties (presets, EDX geometry): what a profile proposal needs."""
        d = self.status()
        try:
            d["properties"] = self.properties()
        except Exception as e:  # noqa: BLE001
            d["properties"] = None
            d.setdefault("read_errors", {})["properties"] = f"{type(e).__name__}: {e}"
        return d


def summarise(s: dict) -> tuple[dict, list]:
    """What a person (or an LLM) needs first: can it image now, and what is in the way."""
    warnings = []
    imode, omode = s.get("instrument_mode"), s.get("operational_mode")
    live_sem = omode in ("LiveSem", "AcquireSemImage")
    if imode and imode != "Operational":
        warnings.append(f"the instrument is in {imode}: it must be Operational to image (the operator wakes it in "
                        "the Phenom UI; about 30 s from Standby)")
    elif omode and not live_sem:
        warnings.append(f"operational mode {omode}: the sample is not under the SEM (load it and select the SEM in "
                        "the Phenom UI)")
    if s.get("door") == "Open":
        warnings.append("the sample door is open")
    ex = s.get("exclusive") or {}
    if ex.get("held"):
        warnings.append(f"another client holds exclusive access: {ex.get('message') or '(no message)'}")
    h = s.get("health") or {}
    bad = [k for k, v in h.items() if k.endswith("OK") and v is False]
    if bad:
        warnings.append("instrument health: " + ", ".join(bad) + " not OK")
    sp = s.get("spectrometer") or {}
    t = sp.get("temperature_k")
    if t is not None and t > 245:
        warnings.append(f"the EDS detector is at {t:.1f} K: not cold yet (234.7 K when ready on 2026-11-23)")
    if s.get("stage", {}) and (s.get("stage") or {}).get("mode") == "NotHomed":
        warnings.append("the stage is not homed")
    cr = s.get("charge_reduction") or {}
    if cr and cr.get("stable") is False:
        p = cr.get("pressure_pa")
        warnings.append(f"the vacuum is still changing (charge reduction target {cr.get('target')}, now "
                        + (f"~{p:.1f} Pa" if isinstance(p, (int, float)) else "pressure unknown")
                        + "): wait for it before high-resolution imaging, EDS or the SED")
    sed = s.get("sed") or {}
    if sed.get("present") and sed.get("state") == "NotAllowed":
        warnings.append("the SED is not allowed now (it needs high vacuum): BSD only until the vacuum settles")
    summary = {"can_image": bool(imode == "Operational" and live_sem and s.get("door") != "Open"),
               "vacuum_stable": cr.get("stable"), "pressure_pa": cr.get("pressure_pa"),
               "sed": sed.get("state") if sed.get("present") else "absent",
               "kv": (s.get("high_tension") or {}).get("kv"), "hfw_um": _um((s.get("hfw") or {}).get("hfw_m")),
               "wd_mm": _mm((s.get("wd") or {}).get("wd_m")),
               "stage_mm": [_mm((s.get("stage") or {}).get("x_m")), _mm((s.get("stage") or {}).get("y_m"))],
               "holder": (s.get("holder") or {}).get("type_name"),
               "eds_ready": bool(t is not None and t <= 245)}
    return summary, warnings


def _um(m):
    return None if m is None else round(m * 1e6, 3)


def _mm(m):
    return None if m is None else round(m * 1e3, 4)


class PhenomAdapter(Adapter):
    """The XL (or PyPhenom's simulator) through PyPhenom. Connects with the PPI license installed on this PC."""

    name = "phenom"

    def __init__(self, simulator: bool = False):
        ppi, info = find_pyphenom()
        if ppi is None:
            raise AdapterError(
                "PyPhenom is not importable here: it exists only on the instrument PC (PyPhenom 2.1.0 for Python "
                "3.12, C:\\Program Files\\Python312\\DLLs\\PyPhenom.pyd); with another Python or a venv, set "
                "PHNT_PYPHENOM to that folder. Elsewhere use PHNT_MODE=fake. Searched: "
                + ", ".join(info.get("searched", [])))
        self.ppi = ppi
        self.name = "ppisim" if simulator else "phenom"
        try:
            self._p = ppi.Phenom("Simulator", "", "") if simulator else ppi.Phenom()
        except Exception as e:  # noqa: BLE001
            raise AdapterError(f"could not connect to the Phenom: {e} (is the Phenom on and on this PC's network, "
                               "and the PPI license installed?)") from e

    def versions(self):
        return {"pyphenom": getattr(self.ppi, "__version__", None)}

    def instrument_mode(self):
        return short(self._p.GetInstrumentMode())

    def operational_mode(self):
        return short(self._p.GetOperationalMode())

    def sem_mode(self):
        return short(self._p.GetSemDeviceMode())

    def door(self):
        return short(self._p.GetDoorStatus())

    def holder(self):
        h = self._p.GetSampleHolder()
        t = int(h.holderType)
        try:
            name = self.ppi.SampleHolderType.Name(t)
        except Exception:  # noqa: BLE001
            name = None
        return {"id": str(h.holderID), "type": t, "type_name": name, "status": short(h.status)}

    def stage(self):
        s = self._p.GetStageModeAndPosition()
        return {"mode": short(s.mode), "x_m": s.position.x, "y_m": s.position.y}

    def stroke(self):
        s = self._p.GetStageStroke()
        return {"x_m": [s.SemX.begin, s.SemX.end], "y_m": [s.SemY.begin, s.SemY.end],
                "navcam_x_m": [s.NavCamX.begin, s.NavCamX.end], "navcam_y_m": [s.NavCamY.begin, s.NavCamY.end]}

    def hfw(self):
        r = self._p.GetHFWRange()
        return {"hfw_m": self._p.GetHFW(), "range_m": [r.begin, r.end]}

    def high_tension(self):
        r = self._p.GetSemHighTensionRange()
        lo, hi = sorted((kv(r.begin), kv(r.end)))
        return {"kv": kv(self._p.GetSemHighTension()), "range_kv": [lo, hi]}

    def spot(self):
        r = self._p.GetSemSpotSizeRange()
        return {"value": self._p.GetSemSpotSize(), "range": [r.begin, r.end]}

    def emission(self):
        return {"current_a": self._p.SemGetEmissionCurrent()}

    def wd(self):
        r = self._p.GetSemWDRange()
        return {"wd_m": self._p.GetSemWD(), "range_m": [r.begin, r.end]}

    def sed(self):
        present = bool(self._p.SemHasSed())
        return {"present": present, "state": short(self._p.SemGetSedState()) if present else None}

    def charge_reduction(self):
        s = self._p.SemGetVacuumChargeReductionState()
        return {"target": short(s.target), "stable": bool(s.isStable), "pressure_pa": s.pressureEstimate,
                "allowed": [short(v) for v in self._p.SemGetAllowedVacuumChargeReduction()]}

    def exclusive(self):
        s = self._p.GetExclusiveAccessStatus()
        return {"held": bool(s.isExclusive), "message": s.message}

    def viewing_mode(self):
        v = self._p.GetSemViewingMode()
        sp = v.scanParams
        return {"scan_mode": short(v.scanMode), "size_px": [sp.size.width, sp.size.height],
                "center": [sp.center.x, sp.center.y], "scale": sp.scale, "frames": sp.nFrames,
                "detector": short(sp.detector)}

    def beam_blank(self):
        return short(self._p.SemGetBlankBeamState())

    def spectrometer(self):
        s = self._p.Spectrometer.GetStatus()
        return {"temperature_k": round(s.detectorTemperature, 2), "acquiring": bool(self._p.IsAcquiringSpectrum())}

    def health(self):
        h = self._p.GetInstrumentHealth()
        return {k: bool(getattr(h, k)) for k in HEALTH_FLAGS if hasattr(h, k)}

    def licenses(self):
        return {f: bool(self.ppi.HasLicense(getattr(self.ppi.Features, f))) for f in LICENSE_FEATURES
                if hasattr(self.ppi.Features, f)}

    def features(self):
        return list(self._p.GetActivatedFeatures())

    def properties(self):
        out = {}
        for n in self._p.GetPropertyNames():
            for getter in (self._p.GetPropertyDouble, self._p.GetPropertyInt, self._p.GetPropertyBool,
                           self._p.GetPropertyString):
                try:
                    out[n] = getter(n)
                    break
                except Exception:  # noqa: BLE001 - the wrong type for this property: try the next getter
                    pass
            else:
                out[n] = None
        return out


def get(mode: str | None = None) -> Adapter:
    """The adapter for PHNT_MODE (or the mode given)."""
    m = mode or config.mode()
    if m == "fake":
        from .fake import FakeAdapter
        return FakeAdapter()
    return PhenomAdapter(simulator=(m == "ppisim"))
