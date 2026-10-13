# AGENTS.md — dcc-mcp-gamemaker

> Navigation map for AI agents, not a reference manual. Detailed API lives in
> `README.md`; install and lifecycle in `install.md`. **This file is the only
> agent contract file at the repository root** — `CLAUDE.md` / `GEMINI.md` /
> `COPILOT.md` / `CODEBUDDY.md` / `CURSOR.md` and `.cursorrules` are deliberately
> absent; agents looking for a vendor-named entry point should read this file.

## Build & test

There is no `justfile` or `vx.toml` in this repo — use the commands CI runs:

```bash
python -m pip install -e ".[test]"          # editable install with the test extra
python -m pytest -m "not gamemaker"         # host-free suite (default local run)
python -m pytest tests/test_doctor.py -q    # Install SOP contract smoke
python -m ruff check src tests              # lint
python -m ruff format --check src tests     # format check
python -m build                             # wheel + sdist
python -m twine check dist/*                # distribution metadata check
```

Use the `dev` extra (`python -m pip install -e ".[dev]"`) when running the lint,
build, and distribution gates — CI uses `test` for the pytest matrix and `dev`
for lint plus packaging.

- **Python:** `>=3.9`. The CI matrix covers 3.9 and 3.12.
- **Core pin:** `dcc-mcp-core>=0.20.36,<1.0.0`. Do not widen or lower this
  without running `tests/test_doctor.py`.

### Real-host lanes (gated, not run by default)

Tests that need a real GameMaker project are behind the `gamemaker` marker and
are skipped unless `DCC_MCP_GAMEMAKER_PROJECT` is set:

```bash
export DCC_MCP_GAMEMAKER_PROJECT=/path/to/Game/Game.yyp
python -m pytest -m gamemaker -v
```

These also require **Node.js 24 or newer** and `gm-cli` on PATH.

## Repo layout

| Path | Role |
|---|---|
| `src/dcc_mcp_gamemaker/bridge.py` | `gm-cli` invocation, argument assembly, output cleaning |
| `src/dcc_mcp_gamemaker/server.py` | `GamemakerMcpServer` — `DccServerBase` subclass |
| `src/dcc_mcp_gamemaker/doctor.py` | Install SOP preflight report assembly |
| `src/dcc_mcp_gamemaker/cli.py` | `dcc-mcp-gamemaker` console script |
| `src/dcc_mcp_gamemaker/skill_tools.py` | Tool functions the skill scripts call |
| `src/dcc_mcp_gamemaker/install_contract.py` | Exit codes and the report `schema_version` |
| `src/dcc_mcp_gamemaker/skills/` | Shipped skills; shipped as wheel artifacts |
| `tests/` | pytest suite; host-free by default |
| `install.md` | Install, verify, upgrade, uninstall |

## Invariants

These are the constraints this adapter was built under. Do not break them.

- **Never parse `.yyp` / `.yy`.** That format is private and moves between
  GameMaker releases. Every project operation goes through
  `gm-cli resourcetool eval`, the vendor's supported automation surface.
- **Windows subprocesses use `CREATE_NO_WINDOW`.** Every launch passes
  `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)`; the `getattr`
  fallback is what keeps POSIX working. `shell=False` with a list argv — no
  shell quoting rules, no injection surface.
- **Node 24 is a floor.** `gm-cli` declares `engines.node >= 24`. Detect and
  report an old runtime; do not let it fail as an opaque bundle syntax error.
- **Not a forwarding shell.** GameMaker ships `gm-cli resourcetool mcp`. This
  adapter's value is the dcc-mcp contract — asset import, a PyPI package,
  marketplace packaging, gateway registration — not another route to the
  vendor's own tools.
- **Writes read back.** Every mutating tool returns the post-write read of the
  project, not a bare acknowledgement.

## Install SOP contract

`install_contract.py` mirrors the report's `schema_version` from the resolved
Core via `install_sop_report_schema_version()`. Do not mirror Core's
`INSTALL_SOP_SCHEMA_REVISION` (or its former name
`INSTALL_SOP_SCHEMA_VERSION`): that is the schema *artifact* revision, which
moves independently of the document contract and would make every report fail
validation the moment Core advances. `tests/test_doctor.py` enforces this.

## Release

- release-please drives versioning from Conventional Commits on `main`.
- `chore:` / `ci:` / `style:` / `refactor:` / `test:` / `build:` are
  `hidden: true`; `docs:` is a visible `Documentation` section. If every commit
  in a batch is hidden, release-please skips the batch entirely — no release PR
  and no version bump.
- Version strings are also written to both skill `SKILL.md` front-matter blocks
  via `release-please-config.json` `extra-files`.

## Agent control path

AI agent runtimes reach this adapter through the shared gateway and the
`dcc-mcp` skill, not by importing the package directly:

```bash
dcc-mcp-cli search --query "<task>" --dcc-type gamemaker
dcc-mcp-cli describe <tool-slug>
dcc-mcp-cli call <tool-slug> --json '{"key":"value"}'
```
