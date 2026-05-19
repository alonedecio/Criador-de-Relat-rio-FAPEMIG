# app/domain/clickup/selectors.py
from typing import Any, Dict, List

from app.domain.clickup.rules import parse_meta_name, parse_activity_name

def select_reportable_activities(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metas_by_id: dict[str, dict] = {}

    for task in tasks:
        if task.get("parent"):
            continue

        parsed_meta = parse_meta_name(task.get("name"))
        if not parsed_meta:
            continue

        metas_by_id[str(task["id"])] = {
            "task": task,
            "meta_numero": parsed_meta["meta_numero"],
            "meta_titulo": parsed_meta["meta_titulo"],
        }

    selected: List[Dict[str, Any]] = []

    for task in tasks:
        parent_id = str(task.get("parent") or "").strip()
        if not parent_id or parent_id not in metas_by_id:
            continue

        parsed_activity = parse_activity_name(task.get("name"))
        if not parsed_activity:
            continue

        meta = metas_by_id[parent_id]

        if parsed_activity["meta_numero"] != meta["meta_numero"]:
            continue

        selected.append(task)

    return selected