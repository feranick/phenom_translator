"""The command line and the MCP server, as a person and an LLM app start them."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from phenom_translator import __version__, cli

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, stdin=None):
    p = subprocess.run([sys.executable, "-m", "phenom_translator.cli", *args], capture_output=True, text=True,
                       input=stdin, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
    return p.returncode, (json.loads(p.stdout) if p.stdout.strip().startswith(("{", "[")) else p.stdout), p.stderr


def test_version_and_status():
    rc, out, _ = run_cli("--version")
    assert rc == 0 and __version__ in out
    rc, out, _ = run_cli("status")
    assert rc == 0 and out["translator"] == __version__ and out["phase"] == 1
    assert out["settings"]["PHNT_MODE"] == "fake" and out["executor"]["kind"] == "local"


def test_validate_from_stdin_and_exit_code():
    rc, out, _ = run_cli("validate", "-", stdin=json.dumps({"a": {"kind": "image"}}))
    assert rc == 0 and out["a"]["ok"]
    rc, out, _ = run_cli("validate", "-", stdin=json.dumps({"a": {"kind": "image"}, "b": {"kind": "nope"}}))
    assert rc == 1 and out["a"]["ok"] and not out["b"]["ok"]


def test_instrument_and_fake_state():
    rc, out, _ = run_cli("fake", "set", 'door="Open"')
    assert rc == 0 and out["state"]["door"] == "Open"
    rc, out, _ = run_cli("instrument", "status")
    assert rc == 0 and out["summary"]["can_image"] is False
    rc, out, _ = run_cli("fake", "reset")
    assert out["state"]["door"] == "Closed"


def test_profile_commands(tmp_path):
    assert cli.main(["instrument", "discover"]) == 0
    assert cli.main(["profile", "propose"]) == 0
    assert cli.main(["profile", "set", "limits.max_move_mm", "5"]) == 0
    assert cli.main(["profile", "import"]) == 1


def test_mcp_server_over_stdio():
    mcp = pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "phenom_translator.mcp_server"],
                                       env={**os.environ, "PYTHONPATH": str(ROOT)}, cwd=str(ROOT))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                init = await s.initialize()
                tools = sorted(t.name for t in (await s.list_tools()).tools)
                st = await s.call_tool("instrument", {"action": "status"})
                vs = await s.call_tool("validate_studies", {"studies": {"a": {"kind": "focus"}}})
                return init, tools, st, vs
    init, tools, st, vs = asyncio.run(go())
    assert "phase 1" in (init.instructions or "")
    assert tools == ["instrument", "study_format", "validate_studies"]
    assert '"can_image": true' in st.content[0].text.replace(" ", "").replace('"can_image":true', '"can_image": true')
    assert json.loads(vs.content[0].text)["a"]["ok"] is True
