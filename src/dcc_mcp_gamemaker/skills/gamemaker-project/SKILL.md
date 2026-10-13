---
name: gamemaker-project
description: >-
  Inspect a GameMaker project without the IDE: confirm which project is loaded,
  list resources by type, and read any resource's properties through the
  official gm-cli resource tool. Use to answer "what is in this project" and to
  find the exact resource names a write tool needs.
license: MIT
compatibility: "Python 3.9+; Node.js 24+; gm-cli (@gamemaker/gm-cli) 2.4.1+; dcc-mcp-core 0.20.36+"
allowed-tools: "python"
metadata:
  dcc-mcp:
    dcc: gamemaker
    layer: domain
    version: "0.1.0"  # x-release-please-version
    tags: [gamemaker, project, resources, inspect, gml]
    search-hint: >-
      GameMaker project resources list inspect properties status yyp gm-cli
    tools: tools.yaml
---

# GameMaker Project

Read a GameMaker project through [`gm-cli`](https://github.com/YoYoGames/gm-cli),
the vendor's own command-line resource tool.

## Why the CLI and not the project files

A GameMaker project is a `.yyp` manifest plus a tree of `.yy` JSON files. That
format is private and changes between GameMaker releases, so this skill never
parses it. Every read goes through `gm-cli resourcetool eval`, which is the
supported automation surface — the same one the GameMaker IDE itself drives.

## What you can read

- **Which project is loaded** — `gamemaker_status` reports the resolved `.yyp`.
- **What resources exist** — `gamemaker_resource_list`, optionally filtered to
  one of the 17 resource types (`sprite`, `object`, `room`, `sound`, `tileset`,
  `script`, `shader`, `font`, `path`, `timeline`, `notes`, `includedfile`,
  `animcurve`, `audiogroup`, `texturegroup`, `particlesystem`, `shape`).
- **Any resource's properties** — `gamemaker_resource_info` takes an expression
  rooted at a resource name, so `spr_player`, `spr_player.frames`, and
  `spr_player.frames[0]` are all valid. This is the way to confirm a property
  name before setting it, and to confirm a write afterwards.

## Finding the project

The adapter resolves a project in this order:

1. the `project` argument, when a tool is called with one;
2. `DCC_MCP_GAMEMAKER_PROJECT`, when the server is configured with it;
3. the nearest `.yyp` in the working directory or any parent.

Run `dcc-mcp-gamemaker doctor --json` to see which one is in effect and why.
