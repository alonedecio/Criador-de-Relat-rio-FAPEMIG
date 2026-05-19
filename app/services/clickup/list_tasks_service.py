from __future__ import annotations

from typing import Any

import requests

from app.core.config import CLICKUP_API_BASE, CLICKUP_API_TOKEN, CLICKUP_LIST_ID


def _headers() -> dict[str, str]:
    return {
        "Authorization": CLICKUP_API_TOKEN,
        "Content-Type": "application/json",
    }


def fetch_all_tasks_from_list(
    list_id: str | None = None,
    include_subtasks: bool = True,
    include_closed: bool = True,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    target_list_id = list_id or CLICKUP_LIST_ID
    tasks: list[dict[str, Any]] = []
    page = 0

    while True:
        params = {
            "page": page,
            "subtasks": "true" if include_subtasks else "false",
            "include_closed": "true" if include_closed else "false",
        }

        url = f"{CLICKUP_API_BASE}/list/{target_list_id}/task"
        response = requests.get(url, headers=_headers(), params=params, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        batch = data.get("tasks", [])

        if not batch:
            break

        tasks.extend(batch)
        page += 1

    return tasks