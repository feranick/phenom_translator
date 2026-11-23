"""mcp_server.py — MCP server: lets LLM-based tools read a Thermo Scientific Phenom XL and prepare SEM studies.

Tools (all JSON), phase 1:
  study_format      the study format, this instrument's choices and limits, phnt's state. Read it first.
  validate_studies  static checks of {name: study} with time estimates (fix every error)
  instrument        status: the instrument now (read only); discover: the same plus a profile proposal

Run:  phnt-mcp            (stdio, what the Claude app starts)
      phnt-mcp --http 8772 [--host 127.0.0.1]
Needs the MCP Python SDK: pip install "mcp>=1.2".
"""
from __future__ import annotations

import argparse
import functools
import inspect

from . import api

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
    _V2 = True
except ImportError:  # 1.x
    from mcp.server.fastmcp import FastMCP as _Server
    from mcp.server.fastmcp.exceptions import ToolError
    _V2 = False

INSTRUCTIONS = """phenom-translator (phnt) prepares and (from phase 2) runs SEM studies on a Thermo Scientific Phenom XL
with EDS, through PyPhenom on the instrument PC. This is phase 1: it reads the instrument (read only) and validates
and estimates studies; it does not move the stage, switch the beam or acquire anything yet. Say so if asked to.
Only these tools reach the instrument. Never use scripts, shell commands or PyPhenom directly: they bypass phnt's
limits and the operator. If no tool does it, say so; do not look for a way.
Workflow: study_format once (kinds, blocks, units, this instrument's ranges, presets and limits, licenses);
instrument status for the instrument now (summary.can_image, warnings); write {name: study}; validate_studies and
fix every error (each says the fix); report the estimate.
Kinds: image, navcam, move, focus (phase 2); montage, series, calibration, particles (phase 3); eds_point, eds_grid
(phase 4). EDS on this XL: raw spectra, peaks and element identification; no quantification and no EDS maps (Thermo
licenses it does not have): say so rather than promising compositions.
Conventions: stage offsets in µm from the home spot; scan_center and EDS spots as fractions of the field width
(+x right, +y down); kV positive; presets by name (setup.kv "Analysis", setup.spot "Map").
Limits come from the profile a person reviewed; the LLM cannot change them: give the person the command
(phnt profile set KEY VALUE) when a limit is in the way. Units: µm, mm, kV, s."""

server = _Server("phenom-translator", instructions=INSTRUCTIONS)


def _errors_said(fn):
    """A tool's failure with its text (SDK 2.x otherwise answers 'Error executing tool X' only)."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"{fn.__name__} failed: {type(exc).__name__}: {exc}"[:2000]) from exc
    assert not inspect.iscoroutinefunction(fn)
    return wrapper


_tool = server.tool


def _tool_said(*a, **k):
    deco = _tool(*a, **k)
    return lambda fn: deco(_errors_said(fn))


server.tool = _tool_said


@server.tool()
def study_format() -> dict:
    """The study format (kinds with the phase that runs them, blocks with types, units, ranges and defaults,
    conventions, an example), this instrument's ranges, presets, limits and licenses from its profile, and phnt's
    status (version, phase, mode, whether the profile is reviewed)."""
    return api.study_format()


@server.tool()
def validate_studies(studies: dict) -> dict:
    """Static checks of {name: study}: {name: {ok, kind, errors (each says the fix), warnings, estimate (minutes,
    parts, which timings are still assumed), runs_from_phase}}."""
    return api.validate(studies)


@server.tool()
def instrument(action: str = "status") -> dict:
    """status: the instrument now, read only: instrument and operational mode, door, sample holder, stage position
    and stroke, kV, spot, emission, WD, HFW, SED, vacuum / charge reduction, exclusive access, EDS detector
    temperature, health, PPI licenses; with a summary (can_image, eds_ready) and warnings. discover: the same plus
    the instrument's properties (presets, EDX geometry), saved, and a profile proposal for a person to review
    (it does not change the profile in use)."""
    return api.instrument(action)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--http", type=int, help="serve MCP over streamable HTTP on this port (default: stdio)")
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    if a.http is None:
        server.run()
    elif _V2:
        server.run(transport="streamable-http", host=a.host, port=a.http)
    else:
        server.settings.host, server.settings.port = a.host, a.http
        server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
