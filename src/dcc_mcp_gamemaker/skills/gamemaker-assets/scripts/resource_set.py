from dcc_mcp_core.skill import run_main, skill_entry, skill_success

from dcc_mcp_gamemaker.skill_tools import gamemaker_resource_set


@skill_entry
def main(expression: str, value: str, project: str = None) -> dict:
    result = gamemaker_resource_set(expression, value, project)
    if not result["success"]:
        return result
    return skill_success(
        "GameMaker resource property set.",
        prompt="The returned members are the post-write readback.",
        verified=True,
        postcondition={"method": "resource_info_readback"},
        expression=expression,
        value=value,
        members=result["result"],
    )


if __name__ == "__main__":
    run_main(main)
