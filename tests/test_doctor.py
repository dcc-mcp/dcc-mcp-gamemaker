"""Install SOP contract tests.

These run without GameMaker, Node, or a project: they pin the shape of the
report this adapter emits against the schema the resolved dcc-mcp-core
publishes, so a Core upgrade that moves the contract fails here rather than in
an agent session.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

from dcc_mcp_gamemaker.bridge import GamemakerBridge


def _published_schema_const():
    """The ``schema_version`` value the published Install SOP schema pins."""
    from dcc_mcp_core import install_sop_report_schema_version

    return install_sop_report_schema_version()


def test_report_schema_version_matches_the_published_schema_const():
    from dcc_mcp_gamemaker.install_contract import SCHEMA_VERSION

    assert SCHEMA_VERSION == _published_schema_const()


def test_adapter_does_not_reference_the_renamed_core_constant():
    """A001: ``INSTALL_SOP_SCHEMA_VERSION`` is the artifact revision, not the
    document's ``schema_version``, and was renamed in Core 0.20.40.

    Mirroring it here would make every doctor report fail validation the moment
    the resolved Core advances, because an artifact revision only ever adds
    optional members.
    """
    from dcc_mcp_gamemaker import install_contract

    assert not hasattr(install_contract, "INSTALL_SOP_SCHEMA_VERSION")
    assert not hasattr(install_contract, "INSTALL_SOP_SCHEMA_REVISION")


def test_public_doctor_reports_missing_node_as_structured_preflight(monkeypatch, capsys):
    from dcc_mcp_gamemaker import cli
    from dcc_mcp_gamemaker.__version__ import __version__

    monkeypatch.delenv("DCC_MCP_GAMEMAKER_PROJECT", raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr("dcc_mcp_gamemaker.bridge.GamemakerBridge.node_version", lambda self: None)

    code = cli.main(["doctor", "--json"])

    report = json.loads(capsys.readouterr().out)
    assert code == 10
    assert report["schema_version"] == _published_schema_const()
    assert report["status"] == "failed"
    assert report["dcc_type"] == "gamemaker"
    assert report["adapter_version"] == __version__
    assert report["error_code"] == "gamemaker_node_missing"
    assert report["verify"] == {
        "directly_usable": False,
        "failure_stage": "node",
        "failure_reason": "Node.js was not found on PATH",
    }


def test_public_doctor_reports_an_old_node_runtime(monkeypatch, capsys):
    from dcc_mcp_gamemaker import cli

    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.node_version", lambda self: "18.19.0"
    )
    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.resolve_command",
        lambda self: ["gm-cli"],
    )

    code = cli.main(["doctor", "--json"])

    report = json.loads(capsys.readouterr().out)
    assert code == 10
    assert report["error_code"] == "gamemaker_node_too_old"
    assert report["verify"]["failure_stage"] == "node"
    assert "24" in report["verify"]["failure_reason"]


def test_doctor_report_satisfies_the_published_schema(tmp_path, monkeypatch, capsys):
    """A014: validate a real report, not a hand-rolled copy of one."""
    from dcc_mcp_core import validate_install_sop_report

    from dcc_mcp_gamemaker import cli

    native_core = pytest.importorskip("dcc_mcp_core._core")
    if not callable(getattr(native_core, "_validate_install_sop_report_json", None)):
        pytest.skip("resolved dcc-mcp-core has no Install SOP validator ABI")

    project = tmp_path / "Fixture.yyp"
    project.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.node_version", lambda self: "24.11.1"
    )
    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.resolve_command",
        lambda self: ["gm-cli"],
    )
    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.eval",
        lambda self, command, timeout=None: "Project 'Fixture' loaded",
    )

    assert cli.main(["doctor", "--json", "--project", str(project)]) == 0
    validate_install_sop_report(json.loads(capsys.readouterr().out))


def test_cli_reports_version():
    # ``src`` is on the path via the editable install in CI, but a subprocess
    # started from a source checkout does not inherit pytest's ``pythonpath``
    # setting, so it is passed explicitly here.
    src = pathlib.Path(__file__).resolve().parent.parent / "src"
    env = dict(os.environ, PYTHONPATH=str(src))
    completed = subprocess.run(
        [sys.executable, "-m", "dcc_mcp_gamemaker.cli", "--version"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0


def test_failed_report_still_satisfies_the_published_schema(monkeypatch, capsys):
    """A failure report must validate too: agents parse both shapes."""
    from dcc_mcp_core import validate_install_sop_report

    from dcc_mcp_gamemaker import cli

    native_core = pytest.importorskip("dcc_mcp_core._core")
    if not callable(getattr(native_core, "_validate_install_sop_report_json", None)):
        pytest.skip("resolved dcc-mcp-core has no Install SOP validator ABI")

    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr("dcc_mcp_gamemaker.bridge.GamemakerBridge.node_version", lambda self: None)

    assert cli.main(["verify", "--json"]) == 10
    validate_install_sop_report(json.loads(capsys.readouterr().out))


# -- timeout actually governs the probe (P2b) ---------------------------------


def test_timeout_is_applied_to_the_runtime_probe(tmp_path, monkeypatch, capsys):
    """``--timeout`` must reach the probe, not only land in the report."""
    seen = {}

    def fake_eval(self, command, *, timeout=None):
        seen["timeout"] = timeout
        return "Project 'Fixture' loaded"

    project = tmp_path / "Fixture.yyp"
    project.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(GamemakerBridge, "node_version", lambda self: "24.11.1")
    monkeypatch.setattr(GamemakerBridge, "resolve_command", lambda self: ["gm-cli"])
    monkeypatch.setattr(GamemakerBridge, "eval", fake_eval)

    from dcc_mcp_gamemaker import cli

    assert cli.main(["doctor", "--json", "--project", str(project), "--timeout", "7"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert seen["timeout"] == 7.0
    assert report["checks"]["configuration"]["timeout"] == 7.0


def test_a_non_positive_timeout_is_rejected(monkeypatch, capsys):
    """A switch that silently does nothing is worse than one that errors."""
    from dcc_mcp_gamemaker import cli

    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(GamemakerBridge, "node_version", lambda self: None)

    assert cli.main(["doctor", "--json", "--timeout", "0"]) == 10
    report = json.loads(capsys.readouterr().out)
    assert report["verify"]["failure_stage"] == "configuration"
    assert "greater than 0" in report["verify"]["failure_reason"]
