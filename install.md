# GameMaker Standalone Install SOP v1

Install the GameMaker adapter without touching the GameMaker IDE. This adapter
never modifies the host application; it drives the official `gm-cli` tool.

The canonical copy of this document is
<https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-gamemaker/main/install.md>.

## Requirements

| Component | Requirement | Why |
|---|---|---|
| Python | 3.9 or newer | The adapter package itself |
| Node.js | **24 or newer** | `gm-cli` declares `engines.node >= 24`; older runtimes fail inside the bundle with an opaque syntax error |
| gm-cli | 2.4.1 or newer | The supported automation surface |
| dcc-mcp-core | 0.20.36 or newer | Server, gateway, and Install SOP contract |
| GameMaker | Not required | `gm-cli` runs with a guest licence; no paid seat needed |

### Node is the one that catches people out

`gm-cli` is a Node program, and Node 24 is a hard floor, not a preference. If
Node is missing or too old, `dcc-mcp-gamemaker doctor` reports it directly —
`gamemaker_node_missing` or `gamemaker_node_too_old` — instead of letting a
bundle syntax error surface later. Install Node **before** the adapter:

```bash
# Windows
winget install --id OpenJS.NodeJS --exact

# macOS
brew install node

# Linux — use your distribution's NodeSource or nvm setup; the version in most
# default repositories is older than 24.
```

Verify:

```bash
node --version   # must print v24 or newer
```

## Agent quick path

```bash
python -m pip install dcc-mcp-gamemaker
npm install -g @gamemaker/gm-cli

export DCC_MCP_GAMEMAKER_PROJECT=/path/to/Game/Game.yyp
dcc-mcp-gamemaker doctor --json
```

An exit code of `0` with `"status": "ok"` means the adapter is directly usable.

## Manual path

1. Install Node.js 24 or newer (see above).
2. Install the vendor CLI:
   ```bash
   npm install -g @gamemaker/gm-cli
   ```
   A global install is recommended. Without one the adapter falls back to
   `npx --yes @gamemaker/gm-cli`, which works but is slower and needs network
   access on every call.
3. Install the adapter:
   ```bash
   python -m pip install dcc-mcp-gamemaker
   ```
4. Point it at a project and verify:
   ```bash
   dcc-mcp-gamemaker doctor --json --project /path/to/Game/Game.yyp
   ```

## Configuration

| Variable | Purpose |
|---|---|
| `DCC_MCP_GAMEMAKER_PROJECT` | Path to a `.yyp` file, or a directory containing one |
| `DCC_MCP_GAMEMAKER_CLI` | Explicit path to a `gm-cli` executable, skipping PATH lookup and the `npx` fallback |
| `DCC_MCP_GAMEMAKER_NODE` | Explicit path to a `node` executable |
| `DCC_MCP_GAMEMAKER_CONFIG` | GameMaker project config to use (default `Default`) |
| `DCC_MCP_GAMEMAKER_TIMEOUT` | Per-call timeout in seconds (default `300`, maximum `3600`) |

If `DCC_MCP_GAMEMAKER_PROJECT` is unset, the adapter looks for the nearest
`.yyp` in the working directory or any parent, so running from a project
subdirectory such as `sprites/` still resolves the project.

## Verify

```bash
dcc-mcp-gamemaker verify --json
```

### What "verified" means here

Verification is a real round-trip, not a file-existence check. The adapter
launches `gm-cli`, loads the project through the official resource tool, and
reads the loaded-project status back. Only a successful round-trip reports
`"directly_usable": true`.

### Failure codes

| Code | Stage | Meaning |
|---|---|---|
| `gamemaker_node_missing` | `node` | Node.js was not found on PATH |
| `gamemaker_node_too_old` | `node` | Node.js is older than 24 |
| `gamemaker_cli_missing` | `gm_cli` | Neither `gm-cli` nor `npx` could be resolved |
| `gamemaker_project_missing` | `project` | No `.yyp` could be resolved |

Preflight runs cheapest-first: configuration, then core, then Node, then
`gm-cli`, and only then a project round-trip.

## Upgrade

```bash
python -m pip install --upgrade dcc-mcp-gamemaker
npm install -g @gamemaker/gm-cli
dcc-mcp-gamemaker verify --json
```

## Uninstall

```bash
python -m pip uninstall dcc-mcp-gamemaker
npm uninstall -g @gamemaker/gm-cli   # only if nothing else needs it
```

## Troubleshooting

**`gamemaker_node_too_old` after installing Node.** A pre-existing older Node is
still first on PATH. Check `node --version` and, on Windows, whether a stale
entry precedes the new install. `DCC_MCP_GAMEMAKER_NODE` pins an exact
executable if you need to bypass PATH entirely.

**Every call is slow.** The adapter is falling back to `npx`, which resolves the
package before each run. Install globally (`npm install -g @gamemaker/gm-cli`)
or set `DCC_MCP_GAMEMAKER_CLI` to the executable.

**`gm-cli exited with code N` with no message.** Usually a project the IDE has
open with unsaved changes, or a `.yyp` written by a newer GameMaker than the
toolchain supports. Close the IDE and retry.

**A window flashes on Windows.** It should not: every `gm-cli` launch passes
`CREATE_NO_WINDOW`. If one still appears, the call is not going through
`GamemakerBridge`.
