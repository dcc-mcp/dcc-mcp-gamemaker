from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_sprite_add_frame


@skill_entry
def main(sprite: str, frame_path: str, position: str = None, project: str = None) -> dict:
    result = gamemaker_sprite_add_frame(sprite, frame_path, position, project)
    if not result["success"]:
        return result
    return skill_success(
        "Sprite frame added.",
        prompt="The returned frame list is the post-import state.",
        verified=True,
        postcondition={"method": "sprite_frames_readback"},
        sprite=sprite,
        frame_path=frame_path,
        frames=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
