# dcc-mcp-gamemaker

Drive a [GameMaker](https://gamemaker.io/en) project from an AI agent without
opening the IDE: inspect resources, author them, and import sprites produced
anywhere else in the pipeline.

Everything goes through [`gm-cli`](https://github.com/YoYoGames/gm-cli), the
command-line tool YoYoGames publishes and maintains. The `.yyp` / `.yy` project
format is private and shifts between GameMaker releases, so this adapter never
parses it — it sends a command to the official resource tool and reads back
what that tool prints.

## Part of the DCC-MCP host matrix

This adapter joins the same contract as the Godot, Blender, Houdini, and Unreal
adapters: one Python package, one gateway registration, one skill catalog. The
ecosystem index and the full host matrix live in
[dcc-mcp-core](https://github.com/dcc-mcp/dcc-mcp-core).

## Capabilities

| Area | What you can do |
|---|---|
| Inspect | Confirm which project is loaded; list resources across all 17 resource types; read any resource's properties |
| Author | Create and delete resources; set a resource property by expression |
| Import | Add and remove sprite frames from a PNG — the path art takes from Photoshop, GIMP, or Substance 3D into GameMaker |

Every mutating call performs its write and then **re-reads the project**,
returning the read-back rather than a bare success. A create that did not land
shows up in the returned listing, not in a later surprise.

## What this is not

GameMaker ships its own MCP server: `gm-cli resourcetool mcp`. This adapter is
deliberately **not** a forwarding shell around it. The official server already
exposes the vendor's tool surface; re-exposing it adds a hop and nothing else.

The value here is the dcc-mcp contract, which is a different thing:

- **the asset-import path** — a frame produced on the Photoshop/GIMP/Substance
  3D side lands as a GameMaker sprite through one call;
- **a Python package** installable from PyPI and importable on its own;
- **marketplace installability** — packaged like every other adapter;
- **gateway integration** — registers through the `dcc_mcp.adapters` entry
  point so the shared gateway discovers it like any other host.

If you only want the vendor's own tools, use `gm-cli resourcetool mcp`
directly. Reach for this adapter when you want GameMaker to behave like the
rest of the DCC-MCP host matrix.

## Requirements

- **Python** 3.9 or newer
- **Node.js 24 or newer** — `gm-cli` declares `engines.node >= 24`
- **gm-cli** — `npm install -g @gamemaker/gm-cli` (2.4.1 or newer), or let the
  adapter fetch it on demand via `npx`
- **dcc-mcp-core** 0.20.36 or newer

No paid GameMaker seat is required: `gm-cli` runs with a guest licence.

## Install

```bash
python -m pip install dcc-mcp-gamemaker
```

Then confirm the toolchain resolves:

```bash
dcc-mcp-gamemaker doctor --json
```

See [`install.md`](install.md) for the full lifecycle, the environment
variables, and what each failure code means.

## Pointing at a project

The adapter resolves a project in this order:

1. the `project` argument on a tool call;
2. `DCC_MCP_GAMEMAKER_PROJECT`;
3. the nearest `.yyp` in the working directory or any parent.

```bash
export DCC_MCP_GAMEMAKER_PROJECT=/path/to/Game/Game.yyp
```

## Agent workflow

Agents reach this adapter through the shared gateway and the `dcc-mcp` skill,
not by importing the package directly:

```bash
dcc-mcp-cli search --query "list sprites" --dcc-type gamemaker
dcc-mcp-cli describe <tool-slug>
dcc-mcp-cli call <tool-slug> --json '{"key":"value"}'
```

## Development

```bash
python -m pip install -e ".[test]"          # editable install with the test extra
python -m pytest -m "not gamemaker"         # host-free suite (the default local run)
python -m pytest tests/test_doctor.py -q    # Install SOP contract smoke
python -m ruff check src tests              # lint
python -m ruff format --check src tests     # format check
python -m build                             # wheel + sdist
python -m twine check dist/*                # distribution metadata check
```

Tests needing a real project are behind the `gamemaker` marker and are skipped
by default. Set `DCC_MCP_GAMEMAKER_PROJECT` to run them.

## License

MIT — see [LICENSE](LICENSE).
