from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_sprite_delete_frame


@skill_entry
def main(sprite: str, index: int, project: str = None) -> dict:
    result = gamemaker_sprite_delete_frame(sprite, index, project)
    if not result["success"]:
        return result
    return skill_success(
        "Sprite frame deleted.",
        prompt="The returned frame list is the post-delete state.",
        verified=True,
        postcondition={"method": "sprite_frames_readback"},
        sprite=sprite,
        index=index,
        frames=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
