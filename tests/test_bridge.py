"""Host-free bridge tests.

These cover the argument assembly and output cleaning that can be checked
without a real GameMaker project. Anything needing the toolchain is marked
``gamemaker`` and skipped by default.
"""

from __future__ import annotations

import subprocess

import pytest

from dcc_mcp_gamemaker.bridge import (
    MIN_NODE_MAJOR,
    RESOURCE_TYPES,
    BridgeError,
    GamemakerBridge,
)


def test_min_node_major_matches_the_vendor_engine_requirement():
    assert MIN_NODE_MAJOR == 24


def test_resource_types_match_the_vendor_tool():
    assert len(RESOURCE_TYPES) == 17
    assert "sprite" in RESOURCE_TYPES
    assert "tileset" in RESOURCE_TYPES


def test_resolve_command_prefers_an_explicit_path():
    bridge = GamemakerBridge(gm_cli="/opt/gm-cli")
    assert bridge.resolve_command() == ["/opt/gm-cli"]


def test_resolve_command_raises_when_nothing_is_available(monkeypatch):
    monkeypatch.setattr("dcc_mcp_gamemaker.bridge.shutil.which", lambda _name: None)
    bridge = GamemakerBridge()
    with pytest.raises(BridgeError, match="Neither 'gm-cli' nor 'npx'"):
        bridge.resolve_command()


def test_clean_strips_banners_progress_and_terminators():
    raw = "\n".join(
        [
            "ResourceTool@2026.0.22",
            "----------------------",
            "Core Resources : Info - loading",
            "ProjectFileWatcher:StopWatching:",
            "Saving..........Success",
            " spr_player ",
            "",
            "ResourceTool Successful",
        ]
    )
    assert GamemakerBridge._clean(raw) == "spr_player"


def test_failure_reason_surfaces_the_first_meaningful_line():
    raw = "\n".join(
        [
            "ResourceTool@2026.0.22",
            "----------------------",
            "Room1.height: Member 'height' not found on Room1",
            "ResourceTool Failed",
        ]
    )
    reason = GamemakerBridge._failure_reason(raw, 1)
    assert reason == "Room1.height: Member 'height' not found on Room1"


def test_eval_rejects_an_empty_command():
    with pytest.raises(BridgeError, match="command is required"):
        GamemakerBridge(project=None).eval("   ")


def test_unknown_resource_type_is_rejected_before_a_round_trip():
    bridge = GamemakerBridge(project=None)
    with pytest.raises(BridgeError, match="Unknown resource type"):
        bridge.resource_list("sprites")


def test_subprocess_uses_no_window_flag_on_windows(monkeypatch):
    """The org-wide Windows convention: never flash a console per call."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="ResourceTool Successful")

    monkeypatch.setattr("dcc_mcp_gamemaker.bridge.subprocess.run", fake_run)
    GamemakerBridge(project=None).eval("status")
    assert "creationflags" in captured
    assert captured["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["shell"] is False


def test_missing_frame_image_is_reported_before_a_round_trip(tmp_path):
    bridge = GamemakerBridge(project=None)
    with pytest.raises(BridgeError, match="Frame image not found"):
        bridge.sprite_add_frame("spr_player", tmp_path / "absent.png")


def test_from_env_reads_the_documented_variables(monkeypatch):
    monkeypatch.setenv("DCC_MCP_GAMEMAKER_PROJECT", "/tmp/Game.yyp")
    monkeypatch.setenv("DCC_MCP_GAMEMAKER_CONFIG", "Default")
    monkeypatch.setenv("DCC_MCP_GAMEMAKER_NODE", "/usr/bin/node")
    monkeypatch.setenv("DCC_MCP_GAMEMAKER_TIMEOUT", "45")
    bridge = GamemakerBridge.from_env()
    assert str(bridge.project).endswith("Game.yyp")
    assert bridge.config == "Default"
    assert bridge.node == "/usr/bin/node"
    assert bridge.timeout == 45.0


def test_from_env_rejects_a_non_numeric_timeout(monkeypatch):
    monkeypatch.setenv("DCC_MCP_GAMEMAKER_TIMEOUT", "soon")
    with pytest.raises(ValueError, match="must be a number of seconds"):
        GamemakerBridge.from_env()


def test_doctor_reports_a_missing_project(tmp_path, monkeypatch):
    from dcc_mcp_gamemaker.doctor import doctor_report

    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.node_version", lambda self: "24.11.1"
    )
    monkeypatch.setattr(
        "dcc_mcp_gamemaker.bridge.GamemakerBridge.resolve_command",
        lambda self: ["gm-cli"],
    )
    report = doctor_report(tmp_path)
    assert report["_exit_code"] == 10
    assert report["error_code"] == "gamemaker_project_missing"


@pytest.mark.gamemaker
def test_live_round_trip_against_a_real_project():
    """Requires Node %d+, gm-cli, and DCC_MCP_GAMEMAKER_PROJECT." % MIN_NODE_MAJOR"""
    import os

    project = os.environ.get("DCC_MCP_GAMEMAKER_PROJECT")
    if not project:
        pytest.skip("DCC_MCP_GAMEMAKER_PROJECT is not set")
    bridge = GamemakerBridge(project=project)
    assert bridge.status()
    assert "sprite" in bridge.resource_types()
    created = bridge.resource_create("sprite", name="spr_mcp_smoke")
    assert "spr_mcp_smoke" in created
    assert "spr_mcp_smoke" not in bridge.resource_delete("spr_mcp_smoke", "sprite")
