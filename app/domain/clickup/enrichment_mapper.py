from __future__ import annotations

from typing import Any

from app.domain.clickup.schemas import (
    ClickUpChecklistItemSummary,
    ClickUpChecklistSummary,
    ClickUpCommentSummary,
    ClickUpTaskBase,
    ClickUpTaskEnriched,
)


def summarize_comments(comments: list[dict[str, Any]]) -> list[ClickUpCommentSummary]:
    out: list[ClickUpCommentSummary] = []

    for comment in comments or []:
        user = comment.get("user") or {}

        out.append(
            ClickUpCommentSummary(
                comment_id=comment.get("id"),
                date=comment.get("date"),
                user=user.get("username"),
                email=user.get("email"),
                comment_text=comment.get("comment_text")
                or comment.get("comment")
                or comment.get("text"),
            )
        )

    return out


def extract_checklists_summary(
    checklists: list[dict[str, Any]],
) -> list[ClickUpChecklistSummary]:
    out: list[ClickUpChecklistSummary] = []

    for checklist in checklists or []:
        itens: list[ClickUpChecklistItemSummary] = []

        for item in checklist.get("items", []) or []:
            raw_name = (item.get("name") or item.get("text") or "").strip()
            resolved = item.get("resolved") is True or "✅" in raw_name

            itens.append(
                ClickUpChecklistItemSummary(
                    name=raw_name,
                    concluido=resolved,
                    marcador="✅" if resolved else "",
                )
            )

        out.append(
            ClickUpChecklistSummary(
                checklist_name=checklist.get("name") or "",
                itens=itens,
                total=len(itens),
                concluidos=sum(1 for i in itens if i.concluido),
            )
        )

    return out


def to_enriched_task(
    base_task: ClickUpTaskBase,
    task_detail: dict[str, Any],
    comments: list[dict[str, Any]],
) -> ClickUpTaskEnriched:
    comment_summaries = summarize_comments(comments)
    checklists = task_detail.get("checklists") or []
    checklist_summaries = extract_checklists_summary(checklists)

    return ClickUpTaskEnriched(
        task_id=base_task.id,
        base=base_task,
        description=task_detail.get("description") or base_task.description or "",
        textcontent=task_detail.get("text_content")
        or task_detail.get("textcontent")
        or base_task.textcontent
        or "",
        assignees=task_detail.get("assignees") or base_task.assignees or [],
        watchers=task_detail.get("watchers") or [],
        attachments=task_detail.get("attachments") or [],
        tags=task_detail.get("tags") or [],
        customfields=task_detail.get("custom_fields")
        or task_detail.get("customfields")
        or base_task.customfields
        or [],
        dependencies=task_detail.get("dependencies") or [],
        linkedtasks=task_detail.get("linked_tasks")
        or task_detail.get("linkedtasks")
        or [],
        checklists=checklists,
        checklists_summary=checklist_summaries,
        comments=comment_summaries,
        comments_count=len(comment_summaries),
        raw_detail_keys=list(task_detail.keys()),
    )