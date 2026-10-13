from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_status


@skill_entry
def main(project: str = None) -> dict:
    result = gamemaker_status(project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker project resolved.",
        prompt="List resources to explore the project.",
        project_status=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
