# app/domain/clickup/selectors.py
import logging
from typing import Any, Dict, List

from app.domain.clickup.rules import parse_meta_name, parse_activity_name

logger = logging.getLogger(__name__)


def select_reportable_activities(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Retorna as tasks que devem entrar no enriched snapshot:
      - Tasks de Meta (sem parent, nome no padrão 'Meta N - ...')
      - Tasks de Atividade cujo parent é uma Meta reconhecida

    IMPORTANTE: as tasks de Meta devem estar no payload para que o mapper
    consiga identificar a hierarquia e vincular atividades às metas corretas.
    Antes só atividades eram incluídas, causando 0 metas/atividades no relatório.
    """
    metas_by_id: dict[str, dict] = {}
    selected: List[Dict[str, Any]] = []

    # --- Primeira passagem: identificar e incluir Metas ---
    for task in tasks:
        # Meta não tem parent (ou parent é nulo/vazio)
        parent = str(task.get("parent") or "").strip()
        if parent:
            continue

        parsed_meta = parse_meta_name(task.get("name"))
        if not parsed_meta:
            continue

        task_id = str(task["id"])
        metas_by_id[task_id] = {
            "task": task,
            "meta_numero": parsed_meta["meta_numero"],
            "meta_titulo": parsed_meta["meta_titulo"],
        }
        selected.append(task)  # inclui a Meta no snapshot

    logger.info("select_reportable_activities: %d metas identificadas", len(metas_by_id))

    # --- Segunda passagem: incluir Atividades cujo parent é uma Meta ---
    atividades_count = 0
    for task in tasks:
        parent_id = str(task.get("parent") or "").strip()
        if not parent_id or parent_id not in metas_by_id:
            continue

        parsed_activity = parse_activity_name(task.get("name"))
        if not parsed_activity:
            logger.debug(
                "select_reportable_activities: task '%s' (parent=%s) ignorada — "
                "nome não segue padrão 'N.N - Título'",
                task.get("name"), parent_id,
            )
            continue

        meta = metas_by_id[parent_id]
        if parsed_activity["meta_numero"] != meta["meta_numero"]:
            logger.debug(
                "select_reportable_activities: atividade '%s' ignorada — "
                "número de meta da atividade (%d) não bate com a meta pai (%d)",
                task.get("name"),
                parsed_activity["meta_numero"],
                meta["meta_numero"],
            )
            continue

        selected.append(task)
        atividades_count += 1

    logger.info(
        "select_reportable_activities: %d atividades selecionadas → total %d tasks no snapshot",
        atividades_count, len(selected),
    )
    return selected
