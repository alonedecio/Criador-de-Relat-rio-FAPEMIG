from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import STAGED_DIR
from app.domain.clickup.base_normalizer import normalize_clickup_tasks
from app.services.clickup.list_tasks_service import fetch_all_tasks_from_list
from app.services.exporters.clickup_base_snapshot_exporter import (
    export_clickup_base_snapshot,
)

DEFAULT_OUTPUT = STAGED_DIR / "clickup_base_snapshot.json"


def build_clickup_base_snapshot(output_path: Optional[Path] = None) -> Path:
    raw_tasks = fetch_all_tasks_from_list()
    normalized_tasks = [task.model_dump() for task in normalize_clickup_tasks(raw_tasks)]

    payload = {
        "metadata": {
            "source": "clickup_api",
            "snapshot_type": "base",
            "task_count": len(normalized_tasks),
        },
        "tasks": normalized_tasks,
    }

    final_output_path = output_path or DEFAULT_OUTPUT
    return export_clickup_base_snapshot(payload, final_output_path)