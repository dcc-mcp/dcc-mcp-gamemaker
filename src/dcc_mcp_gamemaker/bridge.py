"""Bridge to the official GameMaker ``gm-cli`` resource tool.

Every project operation goes through ``gm-cli resourcetool eval``, the vendor's
supported automation surface. The ``.yyp`` / ``.yy`` project format is private
and changes between GameMaker releases, so this module never parses it; it only
ever sends a command string and reads the printed result back.

The child process is spawned with ``CREATE_NO_WINDOW`` so a headless agent host
never gets a console window flashed per call, which is the organisation-wide
convention for Windows subprocess launches.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence

__all__ = [
    "BridgeError",
    "GamemakerBridge",
    "MIN_NODE_MAJOR",
    "RESOURCE_TYPES",
]

# ``gm-cli`` 2.4.1 declares ``engines.node >= 24``. Older Node runtimes are
# rejected up front with an actionable message rather than failing later with an
# opaque syntax error from the bundled bundle.
MIN_NODE_MAJOR = 24

# The 17 resource types ``resourcetool eval "resource types"`` reports. Used to
# reject a typo'd type locally instead of paying a ~1.5s host round-trip.
RESOURCE_TYPES = (
    "animcurve",
    "audiogroup",
    "font",
    "includedfile",
    "notes",
    "object",
    "particlesystem",
    "path",
    "room",
    "script",
    "shader",
    "shape",
    "sound",
    "sprite",
    "texturegroup",
    "tileset",
    "timeline",
)

# Printed by the resource tool on every invocation; stripped from output.
_BANNER = re.compile(r"^ResourceTool@\S+$")
_RULE = re.compile(r"^-{3,}$")
_NOISE = (
    "Core Resources :",
    "ProjectFileWatcher:",
    "Saving",
    "GMSC serialisation",
    "npm exec failed",
    "Command failed",
)

# The tool's own success/failure terminators.
_OK = "ResourceTool Successful"
_FAILED = "ResourceTool Failed"

_DEFAULT_TIMEOUT = 300.0
_MAX_TIMEOUT = 3600.0


class BridgeError(RuntimeError):
    """A ``gm-cli`` invocation failed or reported a command-level error."""


class GamemakerBridge:
    """Runs ``gm-cli resourcetool eval`` against a GameMaker project."""

    def __init__(
        self,
        project: Optional[os.PathLike] = None,
        *,
        gm_cli: Optional[str] = None,
        node: Optional[str] = None,
        config: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
        cwd: Optional[os.PathLike] = None,
        env: Optional[dict] = None,
    ) -> None:
        self.project = Path(project).resolve() if project is not None else None
        self.gm_cli = gm_cli
        self.node = node
        self.config = config
        self.timeout = min(float(timeout), _MAX_TIMEOUT)
        self.cwd = Path(cwd) if cwd is not None else None
        self.env = env

    @classmethod
    def from_env(cls, project: Optional[str] = None) -> "GamemakerBridge":
        """Build a bridge from ``DCC_MCP_GAMEMAKER_*`` environment variables.

        Keeping construction in one place means ``doctor`` validates exactly the
        same configuration the server later runs with.
        """
        env_project = os.environ.get("DCC_MCP_GAMEMAKER_PROJECT")
        raw_project = project if project is not None else env_project
        raw_timeout = os.environ.get("DCC_MCP_GAMEMAKER_TIMEOUT", "")
        timeout = _DEFAULT_TIMEOUT
        if raw_timeout.strip():
            try:
                timeout = float(raw_timeout)
            except ValueError as exc:
                raise ValueError(
                    "DCC_MCP_GAMEMAKER_TIMEOUT must be a number of seconds, got %r" % raw_timeout
                ) from exc
        return cls(
            raw_project.strip() if raw_project and raw_project.strip() else None,
            gm_cli=os.environ.get("DCC_MCP_GAMEMAKER_CLI") or None,
            node=os.environ.get("DCC_MCP_GAMEMAKER_NODE") or None,
            config=os.environ.get("DCC_MCP_GAMEMAKER_CONFIG") or None,
            timeout=timeout,
        )

    # -- discovery -----------------------------------------------------

    def node_version(self) -> Optional[str]:
        """Return the resolved Node version string, or ``None`` if unavailable."""
        executable = self.node or shutil.which("node")
        if not executable:
            return None
        try:
            completed = self._run([executable, "--version"], timeout=30.0)
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.strip().lstrip("v")

    def resolve_command(self) -> list[str]:
        """Return the argv prefix that invokes ``gm-cli``.

        Prefers an explicit ``gm-cli`` path, then a locally installed binary,
        and falls back to ``npx`` so the tool can be fetched on demand. The
        fallback is what makes a bare ``pip install`` workable, but it is slower
        and needs network access, so ``install.md`` recommends a pinned install.
        """
        if self.gm_cli:
            return [self.gm_cli]
        on_path = shutil.which("gm-cli")
        if on_path:
            return [on_path]
        npx = shutil.which("npx")
        if npx:
            return [npx, "--yes", "@gamemaker/gm-cli"]
        raise BridgeError(
            "Neither 'gm-cli' nor 'npx' was found on PATH. Install Node.js "
            "%d or newer, then install the CLI with "
            "'npm install -g @gamemaker/gm-cli'." % MIN_NODE_MAJOR
        )

    def find_project(self) -> Optional[Path]:
        """Resolve the ``.yyp`` to operate on.

        An explicit project wins. Otherwise the nearest ``.yyp`` in ``cwd`` or
        its parents is used, which is what makes the tools work when the server
        is launched from inside a project directory.
        """
        if self.project is not None:
            candidate = Path(self.project)
            if candidate.is_dir():
                return self._yyp_upward(candidate)
            if candidate.is_file():
                return candidate
            return None
        start = (self.cwd or Path.cwd()).resolve()
        return self._yyp_upward(start)

    @classmethod
    def _yyp_upward(cls, directory: Path) -> Optional[Path]:
        """Return the nearest ``.yyp`` in *directory* or any of its parents.

        Walking up is what makes the tools usable from a subdirectory of a
        project — ``sprites/`` or ``objects/`` — which is the normal place to be
        when working on one asset. The upstream tool only looks at ``cwd``, so
        this is a deliberate superset of its behaviour, not a copy of it.
        """
        current = directory.resolve()
        while True:
            found = cls._yyp_in(current)
            if found is not None:
                return found
            parent = current.parent
            if parent == current:
                return None
            current = parent

    @staticmethod
    def _yyp_in(directory: Path) -> Optional[Path]:
        matches = sorted(directory.glob("*.yyp"))
        if matches:
            return matches[0]
        return None

    @staticmethod
    def quote_value(key: str, value: str) -> str:
        """Build one ``key=value`` token using the resource tool's own syntax.

        The tool splits a command on spaces and treats a double quote as a
        grouping toggle, so an unquoted value containing a space is silently
        torn into several tokens: ``value=Hello World`` arrives as
        ``value=Hello`` plus a stray ``World``. That is not a corner case here —
        Windows paths routinely contain spaces (``C:\\Users\\First Last\\...``,
        ``Program Files``), and the sprite import path is exactly the one that
        carries a filesystem path.

        The whole ``key=value`` token is wrapped, not just the value, because
        the tool parses the ``=`` itself.

        The tool offers no way to escape a double quote, so a value containing
        one cannot be expressed at all. Refuse it loudly rather than emitting a
        command that would be parsed as something else.
        """
        text = str(value)
        if '"' in text:
            raise BridgeError(
                "%s cannot contain a double quote: the resource tool has no "
                "escape syntax for one, so the value cannot be represented" % key
            )
        return '%s="%s"' % (key, text)

    # -- invocation ----------------------------------------------------

    def eval(self, command: str, *, timeout: Optional[float] = None) -> str:
        """Run one resource-tool command and return its cleaned output.

        Raises ``BridgeError`` when the tool cannot be spawned, exits non-zero,
        times out, or prints ``ResourceTool Failed``.
        """
        stripped = command.strip()
        if not stripped:
            raise BridgeError("A resource-tool command is required")
        argv = self.resolve_command() + ["resourcetool", "eval", stripped]
        project = self.find_project()
        if project is not None:
            argv.append(str(project))
        if self.config:
            argv.extend(["--config", self.config])
        completed = self._run(argv, timeout=self.timeout if timeout is None else timeout)
        output = completed.stdout
        if _FAILED in output or completed.returncode != 0:
            raise BridgeError(self._failure_reason(output, completed.returncode))
        return self._clean(output)

    def _run(self, argv: Sequence[str], timeout: float) -> "subprocess.CompletedProcess[str]":
        # ``CREATE_NO_WINDOW`` only exists on Windows; ``getattr`` keeps POSIX
        # working. ``shell=False`` with a list argv means no quoting rules and
        # no shell injection surface.
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "timeout": timeout,
            "shell": False,
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }
        if self.cwd is not None:
            kwargs["cwd"] = str(self.cwd)
        if self.env is not None:
            kwargs["env"] = self.env
        try:
            return subprocess.run(  # noqa: S603 - fixed argv, no shell
                list(argv),
                universal_newlines=True,
                errors="replace",
                **kwargs,
            )
        except subprocess.TimeoutExpired as exc:
            raise BridgeError("gm-cli did not finish within %.0f seconds" % timeout) from exc
        except OSError as exc:
            raise BridgeError("Failed to launch %s: %s" % (argv[0], exc)) from exc

    @staticmethod
    def _clean(output: str) -> str:
        lines = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or _BANNER.match(stripped) or _RULE.match(stripped):
                continue
            if any(stripped.startswith(prefix) for prefix in _NOISE):
                continue
            if stripped in (_OK, _FAILED):
                continue
            lines.append(line.rstrip())
        # Drop the trailing separator the tool prints before its terminator.
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines).strip()

    @staticmethod
    def _failure_reason(output: str, returncode: int) -> str:
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or _BANNER.match(stripped) or _RULE.match(stripped):
                continue
            if any(stripped.startswith(prefix) for prefix in _NOISE):
                continue
            if stripped in (_OK, _FAILED):
                continue
            if "npm exec failed" in stripped or "Command failed" in stripped:
                continue
            return stripped
        if returncode != 0:
            return "gm-cli exited with code %d" % returncode
        return "gm-cli reported a command failure without a message"

    # -- typed operations ----------------------------------------------

    def status(self) -> str:
        """Return the loaded-project status line."""
        return self.eval("status")

    def version(self) -> str:
        """Return the resource-tool version banner."""
        return self.eval("version")

    def resource_types(self) -> list[str]:
        """List the resource types the project tool understands."""
        output = self.eval("resource types")
        return [line.strip() for line in output.splitlines() if line.strip().isalpha()]

    def resource_list(self, resource_type: Optional[str] = None) -> str:
        """List project resources, optionally filtered to one type."""
        if resource_type:
            if resource_type not in RESOURCE_TYPES:
                raise BridgeError(
                    "Unknown resource type %r; expected one of: %s"
                    % (resource_type, ", ".join(RESOURCE_TYPES))
                )
            return self.eval("resource list type=%s" % resource_type)
        return self.eval("resource list")

    def resource_info(self, expression: str) -> str:
        """Show the members of a resource expression such as ``spr_hero``."""
        if not expression.strip():
            raise BridgeError("A resource expression is required")
        return self.eval("resource info %s" % self.quote_value("expr", expression.strip()))

    def resource_set(self, expression: str, value: str) -> str:
        """Set a resource property, then read it back to confirm the write."""
        if not expression.strip():
            raise BridgeError("A resource expression is required")
        self.eval(
            "resource set %s %s"
            % (self.quote_value("expr", expression.strip()), self.quote_value("value", value))
        )
        return self.resource_info(expression)

    def resource_create(
        self,
        resource_type: str,
        name: Optional[str] = None,
        parent: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> str:
        """Create a resource and read the project back to confirm it exists."""
        if resource_type not in RESOURCE_TYPES:
            raise BridgeError(
                "Unknown resource type %r; expected one of: %s"
                % (resource_type, ", ".join(RESOURCE_TYPES))
            )
        parts = ["resource create type=%s" % resource_type]
        if name:
            parts.append(self.quote_value("name", name))
        if parent:
            parts.append(self.quote_value("parent", parent))
        if folder:
            parts.append(self.quote_value("folder", folder))
        self.eval(" ".join(parts))
        return self.resource_list(resource_type)

    def resource_delete(
        self,
        name: str,
        resource_type: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> str:
        """Delete a resource and read the project back to confirm it is gone."""
        if not name.strip():
            raise BridgeError("A resource name is required")
        parts = ["resource delete", self.quote_value("name", name.strip())]
        if resource_type:
            parts.append("type=%s" % resource_type)
        if parent:
            parts.append(self.quote_value("parent", parent))
        self.eval(" ".join(parts))
        return self.resource_list(resource_type)

    def sprite_add_frame(
        self,
        sprite: str,
        frame_path: os.PathLike,
        position: Optional[str] = None,
    ) -> str:
        """Add a PNG frame to a sprite and read the frame list back."""
        if not sprite.strip():
            raise BridgeError("A sprite name is required")
        path = Path(frame_path)
        if not path.is_file():
            raise BridgeError("Frame image not found: %s" % path)
        parts = [
            "sprite addframe",
            self.quote_value("name", sprite.strip()),
            self.quote_value("path", str(path)),
        ]
        if position:
            parts.append(self.quote_value("frame", position))
        self.eval(" ".join(parts))
        return self.resource_info("%s.frames" % sprite.strip())

    def sprite_delete_frame(self, sprite: str, index: int) -> str:
        """Delete one frame by index and read the frame list back."""
        if not sprite.strip():
            raise BridgeError("A sprite name is required")
        self.eval(
            "sprite deleteframe %s index=%d"
            % (self.quote_value("name", sprite.strip()), int(index))
        )
        return self.resource_info("%s.frames" % sprite.strip())
