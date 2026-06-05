# app/application/use_cases/build_clickup_enriched_snapshot.py
import json
from pathlib import Path

from app.domain.clickup.schemas import ClickUpTaskBase
from app.domain.clickup.selectors import select_reportable_activities
from app.services.clickup.enrichment_service import enrich_task
from app.services.loaders.clickup_base_snapshot_loader import load_clickup_base_snapshot

BASE_PATH = Path("data/staged/clickup_base_snapshot.json")
OUT_PATH = Path("data/staged/clickup_enriched_snapshot.json")


def build_clickup_enriched_snapshot(
    input_path: Path = BASE_PATH,
    output_path: Path = OUT_PATH,
) -> Path:
    payload = load_clickup_base_snapshot(input_path)
    raw_tasks = payload.get("tasks", [])

    selected_tasks = select_reportable_activities(raw_tasks)

    enriched_tasks = []
    processed_ids: set[str] = set()

    # Carrega snapshot existente para retomar de onde parou (resume mode)
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            existing = json.load(f)
        enriched_tasks = existing.get("tasks", [])

        # CORRIGIDO: o modelo ClickUpTaskEnriched serializa como 'task_id', nao 'id'.
        # Antes usava t.get("id") que sempre retornava None, deixando processed_ids
        # vazio e reprocessando todas as tasks, acumulando duplicatas.
        processed_ids = {
            str(t.get("task_id") or t.get("id") or "")
            for t in enriched_tasks
            if isinstance(t, dict) and (t.get("task_id") or t.get("id"))
        }

    for raw_task in selected_tasks:
        task_id = str(raw_task.get("id") or "")

        if not task_id or task_id in processed_ids:
            continue

        base_task = ClickUpTaskBase(**raw_task)
        enriched = enrich_task(base_task)

        if hasattr(enriched, "model_dump"):
            enriched_dict = enriched.model_dump()
        elif hasattr(enriched, "dict"):
            enriched_dict = enriched.dict()
        else:
            enriched_dict = enriched

        enriched_tasks.append(enriched_dict)
        processed_ids.add(task_id)

    # CORRIGIDO: grava uma unica vez ao final, fora do loop.
    # Antes gravava a cada task, causando I/O desnecessario.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "source": "clickup_enriched_snapshot",
                    "base_task_count": len(raw_tasks),
                    "selected_task_count": len(selected_tasks),
                    "enriched_task_count": len(enriched_tasks),
                },
                "tasks": enriched_tasks,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output_path
