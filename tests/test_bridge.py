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


# -- argument quoting (P1) ----------------------------------------------------
#
# These feed genuinely space-bearing values and paths, because the bug they
# guard against only manifests on input containing a space. Asserting the shape
# of the argv on a no-space input would have passed against the broken code.


def _captured_eval(monkeypatch, bridge, call, index=0):
    """Run a bridge call with the subprocess stubbed, returning one argv.

    Returns the *first* eval by default: mutating helpers fire a write and then
    a read-back, and it is the write whose quoting is under test.
    """
    captured = {}

    def fake_run(argv, **kwargs):
        captured.setdefault("commands", []).append(list(argv)[-1])
        return subprocess.CompletedProcess(argv, 0, stdout="ResourceTool Successful")

    monkeypatch.setattr("dcc_mcp_gamemaker.bridge.subprocess.run", fake_run)
    call(bridge)
    return captured["commands"][index]


def _split_command(command):
    """Port of the resource tool's ``splitCommand()``: split on spaces, with a
    double quote acting as a grouping toggle. There is no escape syntax."""
    tokens, current, in_quotes = [], [], False
    for char in command:
        if char == '"':
            in_quotes = not in_quotes
        elif char == " " and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Hello World", 'value="Hello World"'),
        ("C:\\Users\\First Last\\frame.png", 'value="C:\\Users\\First Last\\frame.png"'),
        ("no-spaces", 'value="no-spaces"'),
        ("  padded  ", 'value="  padded  "'),
    ],
)
def test_quote_value_wraps_the_whole_token(value, expected):
    assert GamemakerBridge.quote_value("value", value) == expected


def test_quote_value_refuses_a_double_quote_rather_than_misparsing():
    """The tool has no escape syntax, so such a value cannot be expressed."""
    with pytest.raises(BridgeError, match="cannot contain a double quote"):
        GamemakerBridge.quote_value("value", 'say "hi"')


def test_resource_set_survives_a_value_containing_spaces(monkeypatch):
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(
        monkeypatch, bridge, lambda b: b.resource_set("spr_player.name", "Player Idle")
    )
    assert 'value="Player Idle"' in command
    assert _split_command(command) == [
        "resource",
        "set",
        "expr=spr_player.name",
        "value=Player Idle",
    ]


def test_resource_create_survives_a_folder_containing_spaces(monkeypatch):
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(
        monkeypatch,
        bridge,
        lambda b: b.resource_create("sprite", name="spr hero", folder="Sprites/Player Idle"),
    )
    assert _split_command(command) == [
        "resource",
        "create",
        "type=sprite",
        "name=spr hero",
        "folder=Sprites/Player Idle",
    ]


def test_resource_delete_survives_a_name_containing_spaces(monkeypatch):
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(monkeypatch, bridge, lambda b: b.resource_delete("spr hero", "sprite"))
    assert _split_command(command) == [
        "resource",
        "delete",
        "name=spr hero",
        "type=sprite",
    ]


def test_sprite_add_frame_survives_a_windows_path_containing_spaces(monkeypatch, tmp_path):
    """The primary cross-DCC import path, and the one the bug broke worst."""
    frame = tmp_path / "frame 01.png"
    frame.write_bytes(b"png")
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(monkeypatch, bridge, lambda b: b.sprite_add_frame("spr_p", frame))
    # One single path token, not torn at the space.
    assert 'path="%s"' % frame in command
    assert _split_command(command) == [
        "sprite",
        "addframe",
        "name=spr_p",
        "path=%s" % frame,
    ]


def test_sprite_add_frame_survives_a_space_bearing_position(monkeypatch, tmp_path):
    """``INDEX 2`` is a documented value in the skill's own front matter."""
    frame = tmp_path / "f.png"
    frame.write_bytes(b"png")
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(
        monkeypatch, bridge, lambda b: b.sprite_add_frame("spr_p", frame, "INDEX 2")
    )
    assert _split_command(command) == [
        "sprite",
        "addframe",
        "name=spr_p",
        "path=%s" % frame,
        "frame=INDEX 2",
    ]


def test_sprite_delete_frame_survives_a_sprite_name_containing_spaces(monkeypatch):
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(monkeypatch, bridge, lambda b: b.sprite_delete_frame("spr hero", 2))
    assert _split_command(command) == [
        "sprite",
        "deleteframe",
        "name=spr hero",
        "index=2",
    ]


def test_resource_info_survives_an_expression_containing_spaces(monkeypatch):
    bridge = GamemakerBridge(project=None)
    command = _captured_eval(monkeypatch, bridge, lambda b: b.resource_info("spr hero"))
    assert _split_command(command) == ["resource", "info", "expr=spr hero"]


# -- project discovery (P2a) --------------------------------------------------


def test_find_project_walks_up_from_a_subdirectory(tmp_path):
    """Working from a project subdirectory is a real usage pattern."""
    project = tmp_path / "My Game.yyp"
    project.write_text("{}", encoding="utf-8")
    nested = tmp_path / "sprites" / "hero"
    nested.mkdir(parents=True)
    bridge = GamemakerBridge(cwd=nested)
    assert bridge.find_project() == project


def test_find_project_stops_at_the_filesystem_root(tmp_path):
    """A directory with no ``.yyp`` anywhere above it yields nothing."""
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    bridge = GamemakerBridge(cwd=deep)
    found = bridge.find_project()
    assert found is None or not str(found).startswith(str(tmp_path))


def test_find_project_prefers_the_nearest_yyp_when_walking_up(tmp_path):
    outer = tmp_path / "Outer.yyp"
    outer.write_text("{}", encoding="utf-8")
    inner = tmp_path / "inner"
    inner.mkdir()
    nearest = inner / "Inner.yyp"
    nearest.write_text("{}", encoding="utf-8")
    child = inner / "sprites"
    child.mkdir()
    bridge = GamemakerBridge(cwd=child)
    assert bridge.find_project() == nearest


def test_find_project_accepts_a_directory_containing_a_yyp(tmp_path):
    project = tmp_path / "Game.yyp"
    project.write_text("{}", encoding="utf-8")
    assert GamemakerBridge(project=tmp_path).find_project() == project


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
