from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_create


@skill_entry
def main(
    resource_type: str,
    name: str = None,
    parent: str = None,
    folder: str = None,
    project: str = None,
) -> dict:
    result = gamemaker_resource_create(resource_type, name, parent, folder, project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resource created.",
        prompt="Add sprite frames next if this is a sprite.",
        verified=True,
        postcondition={"method": "resource_list_readback"},
        resource_type=resource_type,
        listing=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
