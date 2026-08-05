from __future__ import annotations

from agent_console.agents.main_agent import run_task_sync
from agent_console.scenarios import MVP_SCENARIO_NAME, build_mvp_task


def main() -> None:
    print(f"Running scenario: {MVP_SCENARIO_NAME}")
    print(run_task_sync(build_mvp_task()))


if __name__ == "__main__":
    main()
