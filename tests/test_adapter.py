"""The adapter: tier-0 reads on the fake XL, the summary and warnings, and the static check that adapter.py uses
only the PyPhenom names it is allowed to."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

from phenom_translator import adapter, fake

SRC = Path(adapter.__file__).read_text(encoding="utf-8")


def test_status_on_fake_matches_the_discovery():
    s = adapter.get().status()
    assert s["backend"] == "fake" and "read_errors" not in s
    assert s["high_tension"] == {"kv": 15.0, "range_kv": [4.8, 20.5]}       # positive kV
    assert s["holder"]["type_name"] == "XL Manual Height"
    assert s["stroke"]["x_m"] == [-0.05, 0.05]
    assert s["licenses"]["Spectroscopy"] is False and s["licenses"]["EdsMap"] is False
    assert s["summary"]["can_image"] is True and s["summary"]["eds_ready"] is True
    assert s["summary"]["hfw_um"] == pytest.approx(877.216, abs=1e-3)
    assert s["warnings"] == []


def test_standby_door_and_warm_detector_are_warned():
    fake.set_state(instrument_mode="Standby", operational_mode="Unavailable", door="Open",
                   spectrometer={"temperature_k": 290.0})
    s = adapter.get().status()
    assert s["summary"]["can_image"] is False and s["summary"]["eds_ready"] is False
    text = " ".join(s["warnings"])
    assert "Standby" in text and "door is open" in text and "not cold" in text


def test_a_failing_read_does_not_hide_the_rest():
    class Broken(fake.FakeAdapter):
        def door(self):
            raise RuntimeError("OM_COMM_ERROR")
    s = Broken().status()
    assert s["read_errors"] == {"door": "RuntimeError: OM_COMM_ERROR"}
    assert s["high_tension"]["kv"] == 15.0


def test_discover_adds_properties():
    d = adapter.get().discover()
    assert d["properties"]["EDX.WdOptimalLowerBound"] == 0.0045


def test_kv_and_short_names():
    assert adapter.kv(-15000.0) == 15.0
    assert adapter.short("PyPhenom.InstrumentMode.Standby") == "Standby"


STUB = Path(__file__).resolve().parent / "ppi_stub"


@pytest.fixture
def stub(monkeypatch):
    """PyPhenom's stand-in, found through PHNT_PYPHENOM as on a PC where the .pyd is not on the path."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("PHNT_PYPHENOM", str(STUB))
    monkeypatch.setenv("PHNT_MODE", "phenom")
    mod, info = adapter.find_pyphenom()
    mod.CALLS.clear()
    mod.CONNECT_ARGS.clear()
    return mod


def test_phenom_mode_without_pyphenom_says_what_to_do(monkeypatch, tmp_path):
    monkeypatch.setenv("PHNT_PYPHENOM", str(tmp_path))          # an empty folder
    if importlib.util.find_spec("PyPhenom") is not None:
        pytest.skip("PyPhenom is installed here")
    mod, info = adapter.find_pyphenom()
    assert mod is None and "error" in info and str(tmp_path) in info["searched"]
    adapter._PPI.clear()
    with pytest.raises(adapter.AdapterError, match="PHNT_MODE=fake"):
        adapter.get("phenom")


def test_pyphenom_found_through_the_setting(stub):
    mod, info = adapter.find_pyphenom()
    assert info == {"version": "2.1.0-stub", "path": str(STUB / "PyPhenom.py"), "found_by": "PHNT_PYPHENOM"}


def test_phenom_adapter_reads_like_the_fake(stub):
    real, ref = adapter.get().status(), fake.FakeAdapter().status()
    assert real["backend"] == "phenom" and stub.CONNECT_ARGS == [()]      # ppi.Phenom() with the installed license
    assert "read_errors" not in real, real.get("read_errors")
    for k in ("instrument_mode", "operational_mode", "sem_mode", "door", "holder", "stage", "stroke", "hfw",
              "high_tension", "spot", "wd", "sed", "charge_reduction", "exclusive", "viewing_mode", "beam_blank",
              "licenses", "features", "summary", "warnings"):
        assert real[k] == ref[k], k
    assert real["spectrometer"] == {"temperature_k": 234.7, "acquiring": False}
    assert real["health"] == ref["health"]


def test_phenom_adapter_properties_try_each_type(stub):
    p = adapter.get().properties()
    assert p["HighTension.Analysis"] == -15000.0 and p["EDX.Detector.Window"] == "C2"
    assert p["Features.CustomSpotSizeAllowed"] is True and p["MultiStage.Count"] == 0


def test_ppisim_connects_to_the_simulator(stub, monkeypatch):
    monkeypatch.setenv("PHNT_MODE", "ppisim")
    assert adapter.get().name == "ppisim" and stub.CONNECT_ARGS == [("Simulator", "", "")]


def test_the_stub_calls_are_tier0(stub):
    adapter.get().discover()
    called = {c.split(".")[-1] for c in stub.CALLS}
    assert called and all(adapter.PPI_ALLOWED.get(c) == 0 for c in called), called


def _pyphenom_names():
    """Every attribute reached through PyPhenom objects in adapter.py's code (not its tables or docstrings)."""
    code = SRC.split("class PhenomAdapter", 1)[1]
    names = set(re.findall(r"\b(?:ppi|_p|Spectrometer|SampleHolderType|Features)\.([A-Za-z_]\w*)", code))
    return names


def test_adapter_uses_only_allowed_pyphenom_names():
    names = _pyphenom_names()
    assert names, "the scan found no PyPhenom calls: the regular expression is wrong"
    assert not names - set(adapter.PPI_ALLOWED), f"not in PPI_ALLOWED: {sorted(names - set(adapter.PPI_ALLOWED))}"
    assert not names & adapter.PPI_FORBIDDEN, f"forbidden: {sorted(names & adapter.PPI_FORBIDDEN)}"


def test_phase1_adapter_uses_tier0_only():
    tiers = {n: adapter.PPI_ALLOWED[n] for n in _pyphenom_names()}
    assert all(t == 0 for t in tiers.values()), {n: t for n, t in tiers.items() if t}


def test_allowed_and_forbidden_do_not_overlap():
    assert not set(adapter.PPI_ALLOWED) & adapter.PPI_FORBIDDEN


def test_fake_implements_every_read():
    a = fake.FakeAdapter()
    for r in adapter.Adapter.READS + ("properties",):
        getattr(a, r)()


def test_vacuum_settling_and_sed_not_allowed_are_warned():
    # the XL on 2026-11-23 16:08: target Off, 12.9 Pa, not stable; SED NotAllowed; imaging with the BSD went on
    fake.set_state(charge_reduction={"stable": False, "pressure_pa": 12.891667648928037},
                   sed={"present": True, "state": "NotAllowed"})
    s = adapter.get().status()
    assert s["summary"]["can_image"] is True
    assert s["summary"]["vacuum_stable"] is False and s["summary"]["sed"] == "NotAllowed"
    text = " ".join(s["warnings"])
    assert "vacuum is still changing" in text and "~12.9 Pa" in text and "SED is not allowed" in text
