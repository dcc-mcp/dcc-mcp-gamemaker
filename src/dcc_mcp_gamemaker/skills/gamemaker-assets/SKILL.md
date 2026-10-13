---
name: gamemaker-assets
description: >-
  Create, modify, and delete GameMaker resources and import sprite frames
  without the IDE. Use to bring art from Photoshop, GIMP, or Substance 3D into
  a GameMaker project as sprites, or to change resource properties in bulk.
  Load gamemaker-project first to learn the resource names you need.
license: MIT
compatibility: "Python 3.9+; Node.js 24+; gm-cli (@gamemaker/gm-cli) 2.4.1+; dcc-mcp-core 0.20.36+"
allowed-tools: "python"
metadata:
  dcc-mcp:
    dcc: gamemaker
    layer: domain
    version: "0.1.0"  # x-release-please-version
    tags: [gamemaker, assets, sprite, import, create, delete, dcc-mcp]
    search-hint: >-
      GameMaker create resource import sprite frame addframe delete assets
      Photoshop GIMP Substance pipeline
    tools: tools.yaml
---

# GameMaker Assets

Write to a GameMaker project through [`gm-cli`](https://github.com/YoYoGames/gm-cli).
This is the skill that closes the cross-DCC loop: art produced on the
Photoshop / GIMP / Substance 3D side lands here as GameMaker sprites.

## Every write is read back

Each mutating tool performs its write, then re-reads the project and returns
**that read-back** as the result — not a bare "ok". If a create did not land,
you see it in the returned listing instead of discovering it later. This mirrors
the write-after-read contract the other adapters in this organisation follow.

## Importing a sprite

1. Produce a PNG frame on the DCC side (Photoshop export, Substance render, …).
2. `gamemaker_resource_create` with `resource_type=sprite` and a `name`.
3. `gamemaker_sprite_add_frame` with that sprite name and the PNG path.

`position` accepts `FIRST`, `LAST`, or `INDEX n` and defaults to `LAST`. The
frame path is resolved before any call is made, so a typo is reported as a
missing file rather than as an opaque tool failure.

## Not a forwarding shell

GameMaker ships its own MCP server (`gm-cli resourcetool mcp`). This adapter is
deliberately **not** a wrapper around it: the value it adds is the dcc-mcp
contract — the asset-import path, a Python package installable from PyPI,
marketplace packaging, and gateway registration — not another route to the same
tools.

## Setting a property

`gamemaker_resource_set` takes an expression rooted at a resource name
(`spr_player.bbox_left`) and a value. Read the resource with
`gamemaker_resource_info` first to confirm the exact field name: the tool
rejects an unknown member rather than silently doing nothing.
