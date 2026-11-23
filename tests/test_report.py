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
    assert w["read_errors"]["spectrometer during AcquireSemImage"]["count"] >= 1
    assert "READ ERRORS" in r["text"] and "spectrometer during AcquireSemImage" in r["text"]


def test_cli_report_prints_the_text(tmp_path, capsys):
    assert cli.main(["report", "--out", str(tmp_path / "x.txt")]) == 0
    printed = capsys.readouterr().out
    assert printed.strip() == (tmp_path / "x.txt").read_text().strip()


def test_report_without_pyphenom_says_so(monkeypatch, tmp_path):
    monkeypatch.setenv("PHNT_MODE", "phenom")
    monkeypatch.setenv("PHNT_PYPHENOM", str(tmp_path))
    r = api.report(watch_s=1, out=str(tmp_path / "r.txt"))
    assert r["ok"] and "INSTRUMENT: PyPhenom is not importable here" in r["text"]
