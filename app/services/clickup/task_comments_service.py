from __future__ import annotations

from typing import Any

import requests

from app.core.config import CLICKUP_API_BASE, CLICKUP_API_TOKEN


def _headers() -> dict[str, str]:
    return {
        "Authorization": CLICKUP_API_TOKEN,
        "Content-Type": "application/json",
    }


def get_task_comments(
    task_id: str,
    max_pages: int = 5,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    all_comments: list[dict[str, Any]] = []
    page = 0

    while page < max_pages:
        url = f"{CLICKUP_API_BASE}/task/{task_id}/comment"
        params = {"page": page}

        response = requests.get(url, headers=_headers(), params=params, timeout=timeout)

        if response.status_code == 404:
            break

        response.raise_for_status()
        data = response.json()
        comments = data.get("comments", [])

        if not comments:
            break

        all_comments.extend(comments)

        if len(comments) < 25:
            break

        page += 1

    return all_comments