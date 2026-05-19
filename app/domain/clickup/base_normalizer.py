from __future__ import annotations

from typing import Any

from app.domain.clickup.schemas import ClickUpTaskBase


def _extract_status(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("status")
    return value


def _extract_priority(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("priority")
    return value


def normalize_clickup_task(task: dict[str, Any]) -> ClickUpTaskBase:
    return ClickUpTaskBase(
        id=str(task.get("id", "")).strip(),
        name=(task.get("name") or "").strip(),
        parent=task.get("parent"),
        toplevelparent=task.get("toplevelparent"),
        status=_extract_status(task.get("status")),
        status_raw=task.get("status"),
        priority=_extract_priority(task.get("priority")),
        startdate=task.get("startdate"),
        duedate=task.get("duedate"),
        datedone=task.get("datedone"),
        dateclosed=task.get("dateclosed"),
        datecreated=task.get("datecreated"),
        dateupdated=task.get("dateupdated"),
        archived=bool(task.get("archived", False)),
        list=task.get("list") or {},
        folder=task.get("folder") or {},
        space=task.get("space") or {},
        url=task.get("url"),
        customfields=task.get("custom_fields") or task.get("customfields") or [],
        textcontent=task.get("text_content") or task.get("textcontent") or "",
        description=task.get("description") or "",
        assignees=task.get("assignees") or [],
    )


def normalize_clickup_tasks(tasks: list[dict[str, Any]]) -> list[ClickUpTaskBase]:
    out: list[ClickUpTaskBase] = []

    for task in tasks:
        normalized = normalize_clickup_task(task)
        if normalized.id:
            out.append(normalized)

    return out