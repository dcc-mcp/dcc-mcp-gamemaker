from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_delete


@skill_entry
def main(name: str, resource_type: str = None, parent: str = None, project: str = None) -> dict:
    result = gamemaker_resource_delete(name, resource_type, parent, project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resource deleted.",
        prompt="The returned listing is the post-delete project state.",
        verified=True,
        postcondition={"method": "resource_list_readback"},
        deleted=name,
        listing=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
