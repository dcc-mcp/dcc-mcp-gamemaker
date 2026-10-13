"""Standalone GameMaker doctor and verify orchestration.

Preflight is ordered so the cheap local checks run first: configuration, then
the resolved dcc-mcp-core, then the Node runtime, then ``gm-cli`` itself, and
only then a real project round-trip. A missing Node is reported as such instead
of surfacing as an opaque bundle syntax error from the CLI.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Optional

from .__version__ import __version__
from .bridge import MIN_NODE_MAJOR, BridgeError, GamemakerBridge
from .install_contract import (
    EXIT_OK,
    EXIT_PREFLIGHT,
    EXIT_VERIFY,
    SCHEMA_VERSION,
    runtime_core_version,
)

MIN_CORE_VERSION = "0.20.36"

_RELEASE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?")
_MAJOR = re.compile(r"^(\d+)")

ERROR_NODE_MISSING = "gamemaker_node_missing"
ERROR_NODE_TOO_OLD = "gamemaker_node_too_old"
ERROR_CLI_MISSING = "gamemaker_cli_missing"
ERROR_PROJECT_MISSING = "gamemaker_project_missing"


def _release_tuple(value: str) -> Optional[tuple[int, int, int]]:
    match = _RELEASE.match(value.strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def _major(value: str) -> Optional[int]:
    match = _MAJOR.match(value.strip())
    return int(match.group(1)) if match else None


def _command_step(
    identifier: str, description: str, command: list[str], why: str
) -> dict[str, Any]:
    return {"id": identifier, "description": description, "command": command, "why": why}


def _install_node_step() -> dict[str, Any]:
    if os.name == "nt" and _which("winget"):
        command = ["winget", "install", "--id", "OpenJS.NodeJS", "--exact"]
    elif sys.platform == "darwin" and _which("brew"):
        command = ["brew", "install", "node"]
    else:
        command = [sys.executable, "-m", "webbrowser", "https://nodejs.org/en/download"]
    return {
        "id": "install-node",
        "description": "Install Node.js %d or newer" % MIN_NODE_MAJOR,
        "command": command,
        "why": "gm-cli requires Node.js %d or newer to run" % MIN_NODE_MAJOR,
    }


def _install_cli_step() -> dict[str, Any]:
    return {
        "id": "install-gm-cli",
        "description": "Install the official GameMaker CLI",
        "command": ["npm", "install", "-g", "@gamemaker/gm-cli"],
        "why": "The adapter drives GameMaker through the official gm-cli resource tool",
    }


def _which(executable: str) -> Optional[str]:
    from shutil import which

    return which(executable)


def _report(
    verb: str,
    core_version: str,
    checks: dict[str, Any],
    steps: list[dict[str, Any]],
    exit_code: int,
    failure_stage: Optional[str] = None,
    failure_reason: Optional[str] = None,
    next_steps: Optional[list[dict[str, Any]]] = None,
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    directly_usable = exit_code == EXIT_OK
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if directly_usable else "failed",
        "error_code": error_code,
        "dcc_type": "gamemaker",
        "verb": verb,
        "adapter_version": __version__,
        "core_version": core_version,
        "checks": checks,
        "steps": steps,
        "next_steps": list(next_steps or ()),
        "receipt_path": None,
        "verify": {
            "directly_usable": directly_usable,
            "failure_stage": failure_stage,
            "failure_reason": failure_reason,
        },
        "_exit_code": exit_code,
    }


def _fail(
    verb: str,
    core_version: str,
    checks: dict[str, Any],
    steps: list[dict[str, Any]],
    exit_code: int,
    step_id: str,
    stage: str,
    reason: str,
    next_steps: list[dict[str, Any]],
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    steps.append({"id": step_id, "status": "failed", "message": reason})
    return _report(
        verb,
        core_version,
        checks,
        steps,
        exit_code,
        stage,
        reason,
        next_steps,
        error_code,
    )


def doctor_report(
    project: Optional[os.PathLike] = None,
    verb: str = "doctor",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Assemble an Install SOP report for the GameMaker adapter."""
    core_version = runtime_core_version()
    checks: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []

    # -- configuration -------------------------------------------------
    # A timeout that is only recorded is a lie to the orchestrator reading this
    # report, so validate it before anything else and then actually apply it to
    # the runtime probe below.
    if timeout <= 0:
        reason = "Probe timeout must be greater than 0 seconds, got %s" % timeout
        checks["configuration"] = {"success": False, "reason": reason, "timeout": timeout}
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "validate-configuration",
            "configuration",
            reason,
            [
                _command_step(
                    "review-configuration",
                    "Pass a positive --timeout in seconds",
                    ["dcc-mcp-gamemaker", verb, "--json", "--timeout", "30"],
                    reason,
                )
            ],
        )
    try:
        bridge = GamemakerBridge.from_env(str(project) if project is not None else None)
    except (OSError, ValueError) as exc:
        reason = "Invalid GameMaker adapter configuration: %s" % exc
        checks["configuration"] = {"success": False, "reason": str(exc)}
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "validate-configuration",
            "configuration",
            reason,
            [
                _command_step(
                    "review-configuration",
                    "Correct the GameMaker environment configuration",
                    ["dcc-mcp-gamemaker", verb, "--json"],
                    reason,
                )
            ],
        )
    steps.append({"id": "validate-configuration", "status": "ok"})
    checks["configuration"] = {
        "success": True,
        "project": str(bridge.project) if bridge.project is not None else None,
        "config": bridge.config,
        # The value the runtime probe below is actually run with.
        "timeout": timeout,
    }

    # -- core ----------------------------------------------------------
    core_release = _release_tuple(core_version)
    minimum_core = _release_tuple(MIN_CORE_VERSION)
    core_compatible = (
        core_release is not None and minimum_core is not None and core_release >= minimum_core
    )
    checks["core"] = {
        "success": core_compatible,
        "version": core_version,
        "minimum": MIN_CORE_VERSION,
    }
    if not core_compatible:
        reason = "dcc-mcp-core %s is unsupported; %s or newer is required" % (
            core_version,
            MIN_CORE_VERSION,
        )
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "validate-core",
            "core",
            reason,
            [
                _command_step(
                    "upgrade-core",
                    "Upgrade dcc-mcp-core",
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--upgrade",
                        "dcc-mcp-core>=%s" % MIN_CORE_VERSION,
                    ],
                    reason,
                )
            ],
        )
    steps.append({"id": "validate-core", "status": "ok"})

    # -- node ----------------------------------------------------------
    node_version = bridge.node_version()
    node_major = _major(node_version) if node_version else None
    node_ok = node_major is not None and node_major >= MIN_NODE_MAJOR
    checks["node"] = {
        "success": node_ok,
        "version": node_version,
        "minimum_major": MIN_NODE_MAJOR,
    }
    if node_version is None:
        reason = "Node.js was not found on PATH"
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "discover-node",
            "node",
            reason,
            [_install_node_step()],
            ERROR_NODE_MISSING,
        )
    if not node_ok:
        reason = "Node.js %s is unsupported; %d or newer is required" % (
            node_version,
            MIN_NODE_MAJOR,
        )
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "discover-node",
            "node",
            reason,
            [_install_node_step()],
            ERROR_NODE_TOO_OLD,
        )
    steps.append({"id": "discover-node", "status": "ok"})

    # -- gm-cli --------------------------------------------------------
    try:
        command = bridge.resolve_command()
    except BridgeError as exc:
        reason = str(exc)
        checks["gm_cli"] = {"success": False, "reason": reason}
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "discover-gm-cli",
            "gm_cli",
            reason,
            [_install_node_step(), _install_cli_step()],
            ERROR_CLI_MISSING,
        )
    steps.append({"id": "discover-gm-cli", "status": "ok"})
    checks["gm_cli"] = {
        "success": True,
        "command": command,
        "via_npx": command[0].endswith("npx") or command[0].endswith("npx.cmd"),
    }

    # -- project -------------------------------------------------------
    resolved = bridge.find_project()
    checks["project"] = {
        "success": resolved is not None and resolved.is_file(),
        "path": str(resolved) if resolved is not None else None,
    }
    if not checks["project"]["success"]:
        reason = "No GameMaker project (.yyp) was found"
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_PREFLIGHT,
            "discover-project",
            "project",
            reason,
            [
                _command_step(
                    "select-project",
                    "Set DCC_MCP_GAMEMAKER_PROJECT to a .yyp file, or run from a project directory",
                    ["dcc-mcp-gamemaker", verb, "--json", "--project", "<path to .yyp>"],
                    reason,
                )
            ],
            ERROR_PROJECT_MISSING,
        )
    steps.append({"id": "discover-project", "status": "ok"})

    # -- runtime round-trip --------------------------------------------
    try:
        status = bridge.eval("status", timeout=timeout)
    except (BridgeError, OSError, ValueError) as exc:
        reason = "GameMaker runtime verification failed: %s" % exc
        checks["runtime"] = {"success": False, "reason": str(exc)}
        return _fail(
            verb,
            core_version,
            checks,
            steps,
            EXIT_VERIFY,
            "verify-runtime",
            "runtime",
            reason,
            [
                _command_step(
                    "retry-verify",
                    "Retry standalone runtime verification",
                    [
                        "dcc-mcp-gamemaker",
                        verb,
                        "--json",
                        "--project",
                        str(resolved),
                    ],
                    reason,
                )
            ],
        )
    checks["runtime"] = {"success": True, "status": status}
    steps.append({"id": "verify-runtime", "status": "ok"})
    return _report(verb, core_version, checks, steps, EXIT_OK)
