from __future__ import annotations

from rq import Worker

from agent_console.backend.task_queue import get_redis_connection, get_task_queue


def main() -> None:
    connection = get_redis_connection()
    Worker([get_task_queue()], connection=connection).work()


if __name__ == "__main__":
    main()
