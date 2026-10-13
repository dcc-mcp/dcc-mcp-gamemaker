from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_list


@skill_entry
def main(resource_type: str = None, project: str = None) -> dict:
    result = gamemaker_resource_list(resource_type, project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resources listed.",
        prompt="Inspect a resource to read its properties.",
        resource_type=resource_type,
        resources=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
