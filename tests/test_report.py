"""phnt report: one call for a test session at the instrument, written to a text file and a JSON file."""
import json
import time

from phenom_translator import adapter, api, cli, fake


def test_report_writes_text_and_json(tmp_path):
    out = tmp_path / "Desktop" / "phnt_report.txt"
    r = api.report(out=str(out))
    assert r["ok"] and r["files"] == {"text": str(out), "json": str(out.with_suffix(".json"))}
    text = out.read_text()
    assert text.startswith("phnt ") and "NOW: Operational/LiveSem" in text and "LIMITS: kv_max 15.0" in text
    full = json.loads(out.with_suffix(".json").read_text())
    assert full["instrument"]["ok"] and full["instrument"]["read_s"] >= 0 and "properties" in full["instrument"]
    assert "ppisim" not in full                    # only with PHNT_MODE=phenom


def test_watch_lists_changes_and_read_errors_while_the_ui_works(monkeypatch, tmp_path):
    # the Phenom UI starts an image acquisition after the first read; meanwhile one read is refused (as OM_CONTEXT
    # might be): the watch records the change, the error with the mode it happened in, and the change back
    class Busy(fake.FakeAdapter):
        def spectrometer(self):
            if self.s["operational_mode"] == "AcquireSemImage":
                raise RuntimeError("OM_CONTEXT: Command currently rejected; Phenom busy")
            return super().spectrometer()
    monkeypatch.setattr(adapter, "get", lambda mode=None: Busy())
    calls, real_sleep = [], time.sleep

    def ui(s):
        calls.append(s)
        if len(calls) == 1:
            fake.set_state(operational_mode="AcquireSemImage")
        elif len(calls) == 3:
            fake.set_state(operational_mode="LiveSem")
        real_sleep(0.01)
    monkeypatch.setattr(api.time, "sleep", ui)
    r = api.report(watch_s=0.6, every_s=0.2, out=str(tmp_path / "r.txt"))
    w = json.loads((tmp_path / "r.json").read_text())["watch"]
    modes = [c["operational_mode"] for c in w["changes"]]
    assert modes[:3] == ["LiveSem", "AcquireSemImage", "LiveSem"]
    assert w["read_s"]["full"]["n"] >= 1 and w["read_s"]["quick"]["n"] >= 1
    assert len(w["trace"]["rows"]) == w["samples"]
    assert w["read_errors"]["spectrometer during AcquireSemImage"]["count"] >= 1
    assert "READ ERRORS" in r["text"] and "spectrometer during AcquireSemImage" in r["text"]


def test_cli_report_prints_progress_and_the_text_on_stdout_only(tmp_path, capsys):
    fake.set_state(door="Open")
    assert cli.main(["report", "--watch", "0.5", "--every", "0.2", "--out", str(tmp_path / "x.txt")]) == 0
    got = capsys.readouterr()
    assert got.err == ""                               # PowerShell ISE turns stderr into red errors
    assert got.out.startswith("phnt report: reading the instrument... then watching for 0.5 s")
    assert "+   0.0 s  Operational/LiveSem" in got.out   # the change, printed while watching
    assert got.out.rstrip().endswith((tmp_path / "x.txt").read_text().strip())


def test_report_without_pyphenom_says_so(monkeypatch, tmp_path):
    monkeypatch.setenv("PHNT_MODE", "phenom")
    monkeypatch.setenv("PHNT_PYPHENOM", str(tmp_path))
    r = api.report(watch_s=1, out=str(tmp_path / "r.txt"))
    assert r["ok"] and "INSTRUMENT: PyPhenom is not importable here" in r["text"]


def test_pressure_alone_is_not_a_change_and_quick_and_full_reads_compare(monkeypatch, tmp_path):
    # the first watch on the XL logged a 'change' at every read while the chamber pumped down (18.8 -> 0.1 Pa)
    pressures = iter([18.8, 13.3, 6.8, 1.8, 0.1] + [0.1] * 400)

    real_cr = fake.FakeAdapter.charge_reduction

    def cr(self):
        d = real_cr(self)
        p = next(pressures)
        d.update(pressure_pa=p, stable=p < 0.2)
        return d
    monkeypatch.setattr(fake.FakeAdapter, "charge_reduction", cr)
    api.report(watch_s=2.0, every_s=0.1, out=str(tmp_path / "r.txt"))
    w = json.loads((tmp_path / "r.json").read_text())["watch"]
    assert [c["vacuum_stable"] for c in w["changes"]] == [False, True]      # two lines, not one per read
    assert w["changes"][0]["pressure_pa"] == 13.3 or w["changes"][0]["pressure_pa"] == 18.8
    assert [r[1] for r in w["trace"]["rows"][:3]] != [None, None, None]
