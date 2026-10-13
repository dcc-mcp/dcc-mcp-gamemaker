from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_types


@skill_entry
def main(project: str = None) -> dict:
    result = gamemaker_resource_types(project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resource types listed.",
        prompt="Pass one of these types to the listing tool to filter resources.",
        resource_types=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
