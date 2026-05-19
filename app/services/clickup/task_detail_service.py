# app/services/clickup/task_detail_service.py
from __future__ import annotations

from typing import Any

import requests

from app.core.config import CLICKUP_API_BASE, CLICKUP_API_TOKEN


def _headers() -> dict[str, str]:
    return {
        "Authorization": CLICKUP_API_TOKEN,
        "Content-Type": "application/json",
    }


def get_task_detail(task_id: str, timeout: int = 30) -> dict[str, Any]:
    url = f"{CLICKUP_API_BASE}/task/{task_id}"
    params = {"include_markdown_description": "true"}

    response = requests.get(url, headers=_headers(), params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()