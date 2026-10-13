from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_info


@skill_entry
def main(expression: str, project: str = None) -> dict:
    result = gamemaker_resource_info(expression, project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resource inspected.",
        prompt="Use the listed field names as set expressions.",
        expression=expression,
        members=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
