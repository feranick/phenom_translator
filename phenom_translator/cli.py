"""cli.py — the command line. Every command prints JSON; '-' reads the studies from stdin.

  phnt --version
  phnt status                        versions, settings, PyPhenom here or not, the profile
  phnt format                        the study format (kinds, blocks, conventions, example, profile)
  phnt validate studies.json         static checks and time estimates
  phnt instrument status             the instrument now, read only (modes, door, holder, stage, kV, spot, WD,
                                     HFW, SED, vacuum, EDS detector, licenses) with a summary and warnings
  phnt instrument discover           the same plus the instrument's properties, saved; a profile proposal
  phnt profile show | default        the profile in use; write the default one (unreviewed)
  phnt profile propose [DISCOVERY]   profile.proposed.json from the newest (or the given) discovery
  phnt profile import FILE [--who NAME]
                                     the edited proposal, checked and marked reviewed (a person only)
  phnt profile set KEY VALUE         one value (JSON), e.g. limits.kv_max 20
  phnt report [--watch S] [--every S] [--no-ppisim] [--out FILE]
                                     everything for a test session in two files (a short text to paste, and the
                                     full JSON next to it): versions, the instrument now and the time a status read
                                     takes, the profile and its proposal, PyPhenom's simulator; --watch S reads the
                                     status every --every S (2) for S seconds while someone uses the Phenom UI and
                                     lists every change and read error (read only). Prints the text.
  phnt fake state | set KEY=JSON ... | reset
                                     the fake XL's state (PHNT_MODE=fake), for practice and tests

PHNT_MODE: phenom (the XL, default), ppisim (PyPhenom's simulator), fake (phnt's own, any OS).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, api, config


def _studies(arg: str):
    text = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    return json.loads(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="phnt", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"phnt {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("format")
    v = sub.add_parser("validate")
    v.add_argument("file")
    i = sub.add_parser("instrument")
    i.add_argument("action", choices=["status", "discover"])
    p = sub.add_parser("profile")
    p.add_argument("action", choices=["show", "default", "propose", "import", "set"])
    p.add_argument("args", nargs="*")
    p.add_argument("--who", default="")
    r = sub.add_parser("report")
    r.add_argument("--watch", type=float, default=0.0, metavar="S")
    r.add_argument("--every", type=float, default=2.0, metavar="S")
    r.add_argument("--no-ppisim", action="store_true")
    r.add_argument("--out", default=None, metavar="FILE")
    f = sub.add_parser("fake")
    f.add_argument("action", choices=["state", "set", "reset"])
    f.add_argument("pairs", nargs="*")
    a = ap.parse_args(argv)

    if a.cmd == "status":
        out = api.tool_status()
    elif a.cmd == "format":
        out = api.study_format()
    elif a.cmd == "validate":
        out = api.validate(_studies(a.file))
        print(api.dumps(out))
        return 0 if api.all_ok(out) else 1
    elif a.cmd == "instrument":
        out = api.instrument(a.action)
    elif a.cmd == "report":
        if a.watch > 0:
            print(f"watching for {a.watch:g} s (status every {a.every:g} s): use the Phenom UI now", file=sys.stderr)
        out = api.report(a.watch, a.every, not a.no_ppisim, a.out)
        print(out["text"])
        return 0
    elif a.cmd == "profile":
        out = _profile(a)
    else:
        out = _fake(a)
    print(api.dumps(out))
    return 0 if (not isinstance(out, dict) or out.get("ok", True)) else 1


def _profile(a) -> dict:
    if a.action == "show":
        return api.profile_show()
    if a.action == "default":
        return api.profile_default()
    if a.action == "propose":
        return api.profile_propose(a.args[0] if a.args else None)
    if a.action == "import":
        if len(a.args) != 1:
            return {"ok": False, "error": "usage: phnt profile import FILE [--who NAME]"}
        return api.profile_import(a.args[0], a.who)
    if len(a.args) != 2:
        return {"ok": False, "error": "usage: phnt profile set KEY VALUE (VALUE as JSON)"}
    return api.profile_set(a.args[0], a.args[1])


def _fake(a) -> dict:
    if config.mode() != "fake":
        return {"ok": False, "error": "the fake XL is used with PHNT_MODE=fake"}
    from . import fake
    if a.action == "reset":
        fake.reset_state()
    elif a.action == "set":
        over = {}
        for pair in a.pairs:
            k, _, v = pair.partition("=")
            try:
                over[k] = json.loads(v)
            except ValueError:
                over[k] = v
        fake.set_state(**over)
    return {"ok": True, "state": fake.state()}


if __name__ == "__main__":
    sys.exit(main())
