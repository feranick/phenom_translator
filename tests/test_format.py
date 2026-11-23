"""The study format: the examples validate; every rule refuses what it should and says the fix; the estimates
use the measured timings."""
import json
from pathlib import Path

import pytest

from phenom_translator import api, plan, profile
from phenom_translator import format as F

EXAMPLES = json.loads((Path(__file__).resolve().parents[1] / "examples" / "studies.json").read_text())


def v(study, **prof_over):
    p = profile.load()
    for k, val in prof_over.items():
        sec, key = k.split("__")
        p[sec][key] = val
    return F.validate_study("s", study, p)


def test_examples_are_valid():
    r = api.validate(EXAMPLES)
    bad = {n: s["errors"] for n, s in r.items() if not s["ok"]}
    assert set(r) == set(EXAMPLES) and not bad, bad
    assert api.all_ok(r)


def test_study_format_describes_every_kind_and_block():
    f = api.study_format()
    assert set(f["kinds"]) == set(F.KINDS) and set(f["blocks"]) == set(F.BLOCKS)
    assert f["blocks"]["setup"]["kv"]["range"] == [4.8, 20.5]
    assert "Analysis" in f["blocks"]["setup"]["kv"]["choices"]
    assert f["kinds"]["eds_point"]["runs_from_phase"] == 4 and f["status"]["phase"] == 1
    assert F.validate("x", profile.load())["_"]["ok"] is False


@pytest.mark.parametrize("study, needle", [
    ({"kind": "imaging"}, "use one of"),
    ({"kind": "image", "acquire": {"frames": 0}}, "acquire.frames is 0, below the minimum 1"),
    ({"kind": "image", "acquire": {"sise_px": [512, 512]}}, "unknown key acquire.sise_px"),
    ({"kind": "image", "colour": True}, "unknown key 'colour'"),
    ({"kind": "image", "setup": {"kv": 30}}, "setup.kv is 30 kV, above the maximum 20.5 kV"),
    ({"kind": "image", "setup": {"kv": 20}}, "above limits.kv_max = 15.0 kV"),
    ({"kind": "image", "setup": {"kv": 12}, "sample": {"sensitive": True}}, "limits.kv_max_sensitive"),
    ({"kind": "image", "setup": {"kv": "Fast"}}, "must be a number or a preset"),
    ({"kind": "image", "setup": {"spot": 5.8}}, "use a smaller spot"),
    ({"kind": "image", "setup": {"detector": "BSE"}}, "setup.detector must be one of"),
    ({"kind": "image", "acquire": {"hfw_um": 100, "pixel_um": 0.1}}, "not both"),
    ({"kind": "image", "points": [[0, 0], [20000, 0]]}, "beyond limits.max_move_mm"),
    ({"kind": "image", "points": [[0, 0, 0]]}, "points must be"),
    ({"kind": "image", "acquire": {"size_px": [960, 540], "scan_scale": 0.5, "scan_center": [0.25, 0.25]}},
     "|y| <= 0.141"),
    ({"kind": "move", "move": {"x_um": 15000}}, "beyond limits.max_move_mm"),
    ({"kind": "move", "move": {"to_home": True, "x_um": 5}}, "not both"),
    ({"kind": "montage", "montage": {"overlap": 0.1}}, "give tiles"),
    ({"kind": "montage", "acquire": {"hfw_um": 100}, "montage": {"tiles": [30, 30]}}, "montage_tiles_max"),
    ({"kind": "series", "series": {"interval_s": 5}}, "series.count is required"),
    ({"kind": "calibration", "calibration": {"target": "grid"}}, "pitch_um is required"),
    ({"kind": "calibration", "calibration": {"target": "eds_energy"}}, "elements is required"),
    ({"kind": "eds_point", "eds": {"live_s": 60}}, "eds.live_s is 60 s, above the maximum 10.0 s"),
    ({"kind": "eds_point", "eds": {"spots": [[0, 0.4]]}}, "outside the field"),
    ({"kind": "eds_point", "eds": {"elements": ["Ni", "Xx"]}}, "unknown element symbol(s): Xx"),
    ({"kind": "eds_point", "setup": {"wd_mm": 20}}, "outside the EDX-acceptable"),
    ({"kind": "eds_grid", "eds": {"live_s": 1}}, "eds_grid.grid [nx, ny] is required"),
    ({"kind": "eds_grid", "eds_grid": {"grid": [100, 100]}}, "exceed limits.eds_points_max"),
])
def test_rules_refuse_and_say_why(study, needle):
    r = v(study)
    assert not r["ok"]
    assert any(needle in e for e in r["errors"]), r["errors"]


def test_warnings_do_not_refuse():
    r = v({"kind": "eds_point", "setup": {"wd_mm": 11.0}, "eds": {"live_s": 10, "repeats": 5}})
    assert r["ok"]
    w = " ".join(r["warnings"])
    assert "EDX-optimal" in w and "fine for trace elements" in w
    r = v({"kind": "eds_point"})
    assert r["ok"] and any("WD at run time" in x for x in r["warnings"])


def test_scan_center_on_wide_images_uses_the_width():
    ok = v({"kind": "image", "acquire": {"size_px": [960, 540], "scan_scale": 0.5, "scan_center": [0.25, 0.14]}})
    assert ok["ok"], ok["errors"]


def test_spots_allowed_to_the_edge_of_the_live_view():
    assert v({"kind": "eds_point", "eds": {"spots": [[0.5, 0.28], [-0.5, -0.28]]}})["ok"]


def test_disabled_eds_turns_the_kinds_off():
    p = profile.load()
    p["edx"]["enabled"] = False
    r = F.validate_study("s", {"kind": "eds_point"}, p)
    assert not r["ok"] and "not available" in r["errors"][0]
    assert F.study_format(p)["kinds"]["eds_grid"]["available"] is False


def test_study_minutes_cap(monkeypatch):
    monkeypatch.setenv("PHNT_MAX_MINUTES", "1")
    r = api.validate({"m": EXAMPLES["coarse_map"], "o": EXAMPLES["overview"]})
    assert not r["m"]["ok"] and "PHNT_MAX_MINUTES" in r["m"]["errors"][0]
    assert r["o"]["ok"]


def test_request_total_is_a_warning():
    assert api.profile_set("limits.request_minutes_max", "10")["ok"]
    r = api.validate({"a": EXAMPLES["coarse_map"], "b": EXAMPLES["coarse_map"]})
    assert api.all_ok(r)
    assert all(any("the request together" in w for w in x["warnings"]) for x in r.values())


def test_study_names_name_folders():
    r = api.validate({"bad name/..": {"kind": "focus"}})
    assert not r["bad name/.."]["ok"] and "use letters, digits" in r["bad name/.."]["errors"][0]


def test_study_format_stays_compact():
    import json
    assert len(json.dumps(api.study_format())) < 13000      # the template's 10-12 kB


def test_eds_grid_estimate_matches_the_measurement():
    # 0.5 s live per point measured at 0.66-0.70 s per point with the spot move (eds_tests2, Q17; eds_tests3)
    s = {"kind": "eds_grid", "eds": {"live_s": 0.5}, "eds_grid": {"grid": [32, 32]}}
    e = plan.estimate("eds_grid", s, profile.load())
    assert 0.66 * 1024 <= e["parts_s"]["spectra"] <= 0.72 * 1024
    assert "stage_mm_per_s" in e["assumed_timing"]


def test_image_estimate_matches_the_measurement():
    t = plan.image_s({"size_px": [512, 512], "frames": 2}, profile.load())
    assert 0.15 <= t <= 0.30          # 0.16-0.19 s measured


def test_montage_grid_from_area():
    nx, ny, ext = plan.montage_grid({"montage": {"area_um": [2000, 1500], "overlap": 0.15},
                                     "acquire": {"size_px": [1024, 1024], "hfw_um": 400}}, profile.load())
    assert (nx, ny) == (6, 5) and ext[0] >= 2000 and ext[1] >= 1500


def test_large_field_at_short_wd_is_warned_not_refused():
    r = v({"kind": "image", "setup": {"wd_mm": 4.0}, "acquire": {"hfw_um": 800}})
    assert r["ok"] and any("may not fit" in w and "about 760.4 µm at WD 4 mm (interpolated)" in w for w in r["warnings"])
    r = v({"kind": "image", "setup": {"wd_mm": 6.5}, "acquire": {"hfw_um": 800}})
    assert r["ok"] and not any("may not fit" in w for w in r["warnings"])


def test_largest_field_by_wd_from_the_three_points_measured():
    # 2026-11-23 on the XL: 726.0 µm at 3.3 mm, 755.3 at 3.9, 877.2 at 6.3
    p = profile.load()
    assert profile.hfw_max_um(p, 3.9) == (755.3, "measured")
    assert profile.hfw_max_um(p, 5.0) == (811.2, "interpolated")
    assert profile.hfw_max_um(p, 2.0) == (662.6, "extrapolated")
    assert profile.hfw_max_um(p, 3.3) == (726.0, "measured")
