"""MCP-exposed GameMaker operations.

Each tool is a thin wrapper over a ``GamemakerBridge`` call. Mutating tools read
the project state back and return the read-back result rather than a bare
acknowledgement, so a caller can confirm the write landed without a second call.
"""

from __future__ import annotations

from typing import Any, Optional

from .bridge import RESOURCE_TYPES, BridgeError, GamemakerBridge

__all__ = [
    "RESOURCE_TYPES",
    "gamemaker_resource_create",
    "gamemaker_resource_delete",
    "gamemaker_resource_info",
    "gamemaker_resource_list",
    "gamemaker_resource_set",
    "gamemaker_resource_types",
    "gamemaker_sprite_add_frame",
    "gamemaker_sprite_delete_frame",
    "gamemaker_status",
]


def _bridge(project: Optional[str] = None) -> GamemakerBridge:
    return GamemakerBridge.from_env(project)


def _result(payload: Any) -> dict[str, Any]:
    return {"success": True, "result": payload}


def _error(exc: Exception) -> dict[str, Any]:
    return {"success": False, "error": str(exc)}


def gamemaker_status(project: Optional[str] = None) -> dict[str, Any]:
    """Report the loaded GameMaker project."""
    try:
        return _result(_bridge(project).status())
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_types(project: Optional[str] = None) -> dict[str, Any]:
    """List the resource types the project tool understands."""
    try:
        return _result(_bridge(project).resource_types())
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_list(
    resource_type: Optional[str] = None, project: Optional[str] = None
) -> dict[str, Any]:
    """List project resources, optionally filtered to one type."""
    try:
        return _result(_bridge(project).resource_list(resource_type))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_info(expression: str, project: Optional[str] = None) -> dict[str, Any]:
    """Show the members of a resource expression such as ``spr_hero``."""
    try:
        return _result(_bridge(project).resource_info(expression))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_set(
    expression: str, value: str, project: Optional[str] = None
) -> dict[str, Any]:
    """Set a resource property and read it back."""
    try:
        return _result(_bridge(project).resource_set(expression, value))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_create(
    resource_type: str,
    name: Optional[str] = None,
    parent: Optional[str] = None,
    folder: Optional[str] = None,
    project: Optional[str] = None,
) -> dict[str, Any]:
    """Create a resource and read the project back to confirm it exists."""
    try:
        return _result(_bridge(project).resource_create(resource_type, name, parent, folder))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_resource_delete(
    name: str,
    resource_type: Optional[str] = None,
    parent: Optional[str] = None,
    project: Optional[str] = None,
) -> dict[str, Any]:
    """Delete a resource and read the project back to confirm it is gone."""
    try:
        return _result(_bridge(project).resource_delete(name, resource_type, parent))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_sprite_add_frame(
    sprite: str,
    frame_path: str,
    position: Optional[str] = None,
    project: Optional[str] = None,
) -> dict[str, Any]:
    """Add a PNG frame to a sprite and read the frame list back."""
    try:
        return _result(_bridge(project).sprite_add_frame(sprite, frame_path, position))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)


def gamemaker_sprite_delete_frame(
    sprite: str, index: int, project: Optional[str] = None
) -> dict[str, Any]:
    """Delete one frame by index and read the frame list back."""
    try:
        return _result(_bridge(project).sprite_delete_frame(sprite, index))
    except (BridgeError, OSError, ValueError) as exc:
        return _error(exc)
