"""fake.py — phnt's own pure-Python Phenom XL, for any OS and CI (PHNT_MODE=fake).

It answers the adapter's verbs with what the real XL answered on 2026-11-23 (docs/discovery): live SEM imaging at
15 kV, spot 5.1 (Map), WD 6.3 mm, HFW 877 µm, the manual-height holder, the ±50 mm stage, the EDS detector cold, no
PPI add-on license. Tests and practice runs change that state through `fake_state.json` (store: sim_fake_state.json
in PHNT_OUT), e.g. {"instrument_mode": "Standby"} or {"door": "Open"}.

Phase 1 covers the tier-0 reads; images, spectra and the stage arrive with phases 2–4 (a sample with particles of
known size and composition, a calibration grid, defocus, drift, charging, stage error with and without backlash
correction, an operator who confirms or stops).
"""
from __future__ import annotations

import copy

from . import store
from .adapter import Adapter, LICENSE_FEATURES

STATE_FILE = "fake_state.json"

DEFAULT_STATE = {
    "pyphenom": "fake (as PyPhenom 2.1.0)",
    "instrument_mode": "Operational",
    "operational_mode": "LiveSem",
    "sem_mode": "Imaging",
    "door": "Closed",
    "holder": {"id": "0183a2111d0000d3", "type": 100, "type_name": "XlManualHeight", "status": "Present"},
    "stage": {"mode": "Rest", "x_m": 6.02434271662765e-05, "y_m": 0.003988864624543326},
    "stroke": {"x_m": [-0.05, 0.05], "y_m": [-0.05, 0.05], "navcam_x_m": [-0.05, 0.05],
               "navcam_y_m": [-0.05, 0.05]},
    "hfw_m": 0.000877216182013485, "hfw_range_m": [2.4714285714285713e-06, 0.000877216182013485],
    "high_tension_v": -15000.0, "high_tension_range_v": [-20500.0, -4800.0],
    "spot": 5.1, "spot_range": [0.0, 5.8],
    "emission_a": 4.03e-05,
    "wd_m": 0.0063, "wd_range_m": [0.001, 0.06],
    "sed": {"present": True, "state": "Enabled"},
    "charge_reduction": {"target": "Off", "stable": True, "pressure_pa": 0.1, "allowed": ["Off", "Low", "High"]},
    "exclusive": {"held": False, "message": ""},
    "viewing_mode": {"scan_mode": "Imaging", "size_px": [960, 540], "center": [0.0, 0.0], "scale": 1.0,
                     "frames": 4, "detector": "All"},
    "beam_blank": "Unblanked",
    "spectrometer": {"temperature_k": 234.7, "acquiring": False},
    "health": {"DoorOpen": False, "ElectronicsOK": True, "ImageEngineOK": True, "NavCamOK": True, "OpticsOK": True,
               "SampleOK": True, "SourceOK": True, "StageOK": True, "SystemOK": True, "VacuumOK": True},
    "licenses": {f: False for f in LICENSE_FEATURES},
    "features": ["XL 100 x 100 mm stage"],
    "properties": {
        "HighTension.AllMaterials": -5300.0, "HighTension.HighResolution": -10000.0, "HighTension.Analysis": -15000.0,
        "SpotPosition.Accuracy": 0.005, "MultiStage.MaximumSampleRadius": 0.035,
        "TransitionTime.OffToOperational": 52200.0, "TransitionTime.StandbyToOperational": 30.0,
        "BSD.NominalMountingAngle": 1.5708, "EDX.TakeOffAngle": 28.5, "EDX.WdOptimalLowerBound": 0.0045,
        "EDX.WdOptimalUpperBound": 0.01, "EDX.WdAcceptableLowerBound": 0.003, "EDX.WdAcceptableUpperBound": 0.012,
        "EDX.DppConnectionType": "usb", "EDX.Detector.Manufacturer": "Ametek", "EDX.Detector.Type": "Dp5",
        "EDX.Detector.SoftwareInterfaceVersion": "Fw6", "EDX.Detector.SurfaceArea": 2.5e-05,
        "EDX.Detector.Attributes": "Surface25", "EDX.Detector.Window": "C2", "SamplePressure.High": 60.0,
        "SamplePressure.Medium": 10.0, "SamplePressure.Low": 0.1, "Features.CustomSpotSizeAllowed": True,
        "Features.CustomHighTensionAllowed": True, "EmissionCurrent.Nominal": 4.03e-05, "EmissionCurrent.Low": 2e-05,
        "SpotSize.Low": 2.1, "SpotSize.Image": 3.3, "SpotSize.Point": 4.3, "SpotSize.Map": 5.1},
}


def state() -> dict:
    """The default XL with the overrides in fake_state.json applied (one level deep for dict values)."""
    s = copy.deepcopy(DEFAULT_STATE)
    for k, v in store.read(STATE_FILE).items():
        if isinstance(v, dict) and isinstance(s.get(k), dict):
            s[k].update(v)
        else:
            s[k] = v
    return s


def set_state(**overrides) -> dict:
    cur = store.read(STATE_FILE)
    cur.update(overrides)
    return store.write(STATE_FILE, cur)


def reset_state() -> dict:
    return store.write(STATE_FILE, {})


class FakeAdapter(Adapter):
    name = "fake"

    def __init__(self):
        self.s = state()

    def versions(self):
        return {"pyphenom": self.s["pyphenom"]}

    def instrument_mode(self):
        return self.s["instrument_mode"]

    def operational_mode(self):
        return self.s["operational_mode"]

    def sem_mode(self):
        return self.s["sem_mode"]

    def door(self):
        return self.s["door"]

    def holder(self):
        return dict(self.s["holder"])

    def stage(self):
        return dict(self.s["stage"])

    def stroke(self):
        return copy.deepcopy(self.s["stroke"])

    def hfw(self):
        return {"hfw_m": self.s["hfw_m"], "range_m": list(self.s["hfw_range_m"])}

    def high_tension(self):
        lo, hi = sorted(abs(v) / 1000.0 for v in self.s["high_tension_range_v"])
        return {"kv": abs(self.s["high_tension_v"]) / 1000.0, "range_kv": [lo, hi]}

    def spot(self):
        return {"value": self.s["spot"], "range": list(self.s["spot_range"])}

    def emission(self):
        return {"current_a": self.s["emission_a"]}

    def wd(self):
        return {"wd_m": self.s["wd_m"], "range_m": list(self.s["wd_range_m"])}

    def sed(self):
        return dict(self.s["sed"])

    def charge_reduction(self):
        return copy.deepcopy(self.s["charge_reduction"])

    def exclusive(self):
        return dict(self.s["exclusive"])

    def viewing_mode(self):
        return copy.deepcopy(self.s["viewing_mode"])

    def beam_blank(self):
        return self.s["beam_blank"]

    def spectrometer(self):
        return dict(self.s["spectrometer"])

    def health(self):
        return dict(self.s["health"])

    def licenses(self):
        return dict(self.s["licenses"])

    def features(self):
        return list(self.s["features"])

    def properties(self):
        return dict(self.s["properties"])
