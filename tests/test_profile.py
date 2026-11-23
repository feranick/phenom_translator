"""The machine profile: defaults, the proposal from a discovery, import (reviewed) and set."""
import json

from phenom_translator import api, config, fake, profile


def test_default_profile_is_unreviewed_and_passes_its_checks():
    p = profile.load()
    assert p["reviewed"] is False and profile.check(p) == []
    assert p["presets"]["kv"]["Analysis"] == 15.0 and p["edx"]["wd_acceptable_mm"] == [3.0, 12.0]


def test_discover_writes_a_proposal_and_leaves_the_profile_alone():
    fake.set_state(high_tension_range_v=[-20000.0, -5000.0], properties={"SpotSize.Map": 5.0})
    r = api.instrument("discover")
    assert r["ok"] and r["proposal"].endswith("profile.proposed.json")
    prop = json.loads(open(r["proposal"]).read())
    assert prop["ranges"]["kv"] == [5.0, 20.0] and prop["presets"]["spot"]["Map"] == 5.0
    assert prop["reviewed"] is False
    assert r["changes"]["ranges.kv"] == {"was": [4.8, 20.5], "proposed": [5.0, 20.0]}
    assert not config.profile_path().exists()          # the profile in use is untouched


def test_import_marks_reviewed_and_refuses_bad_limits(tmp_path):
    api.instrument("discover")
    prop = json.loads(profile.proposed_path().read_text())
    prop["limits"]["kv_max"] = 99
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(prop))
    r = profile.import_file(bad)
    assert not r["ok"] and any("kv_max" in e for e in r["errors"])
    r = profile.import_file(profile.proposed_path(), who="NF")
    assert r["ok"] and profile.load()["reviewed"] is True and profile.load()["reviewed_by"] == "NF"


def test_set_value_checks_and_keeps_new_defaults():
    assert api.profile_set("limits.kv_max", "20")["ok"]
    assert profile.load()["limits"]["kv_max"] == 20
    r = api.profile_set("limits.kv_max_sensitive", "25")
    assert not r["ok"]
    assert api.profile_set("nosuch.key", "1")["ok"] is False
    assert profile.load()["timing"]["eds_overhead_s"] == 0.07      # a key not in the saved file: its default


def test_profile_default_writes_once():
    assert api.profile_default()["ok"]
    assert not api.profile_default()["ok"]
