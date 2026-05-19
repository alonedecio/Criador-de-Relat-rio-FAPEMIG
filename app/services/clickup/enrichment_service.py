from __future__ import annotations

from app.domain.clickup.enrichment_mapper import to_enriched_task
from app.domain.clickup.schemas import ClickUpTaskBase, ClickUpTaskEnriched
from app.services.clickup.task_comments_service import get_task_comments
from app.services.clickup.task_detail_service import get_task_detail


def enrich_task(base_task: ClickUpTaskBase) -> ClickUpTaskEnriched:
    task_detail = get_task_detail(base_task.id)
    comments = get_task_comments(base_task.id)
    return to_enriched_task(base_task=base_task, task_detail=task_detail, comments=comments)