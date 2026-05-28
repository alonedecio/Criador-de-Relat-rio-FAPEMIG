import re
from collections import defaultdict

from app.domain.reporting.canonical_schemas import RelatorioCanonico, ResumoProjetoCanonico


PADRAO_META = re.compile(r"^Meta\s+(\d+)\s*-\s*(.+)$", re.IGNORECASE)
PADRAO_ATIVIDADE = re.compile(r"^(\d+)\.(\d+)\s*[-–—]\s*(.+)$")
PADRAO_NUMERO_ATIVIDADE = re.compile(r"^(\d+)\.(\d+)$")


def _normalize_str(value) -> str:
    return str(value or "").strip()


def _none_if_empty(value: str | None) -> str | None:
    value = _normalize_str(value)
    return value or None


def _extract_task_name(task: dict) -> str:
    return _normalize_str(task.get("name"))


def _extract_task_id(task: dict) -> str:
    return _normalize_str(task.get("id"))


def _extract_parent_id(task: dict) -> str | None:
    parent_id = _none_if_empty(task.get("parent"))
    if parent_id:
        return parent_id

    return _none_if_empty(task.get("toplevelparent"))


def _extract_status(task: dict) -> str | None:
    status = task.get("status")
    if isinstance(status, dict):
        return _none_if_empty(status.get("status"))
    return _none_if_empty(status)


def _extract_dates(task: dict) -> dict:
    return {
        "data_inicio": task.get("startdate") or task.get("start_date"),
        "data_fim": task.get("duedate") or task.get("due_date"),
        "data_fim_realizado": task.get("datedone") or task.get("date_closed"),
    }


def _extract_custom_fields(task: dict) -> dict:
    fields = {}
    raw_fields = task.get("customfields", []) or task.get("custom_fields", []) or []

    for item in raw_fields:
        name = _normalize_str(item.get("name"))
        value = item.get("value")
        if name:
            fields[name] = value

    return fields


def _extract_activity_parts(nome: str, custom_fields: dict) -> tuple[str | None, str | None, str, str]:
    nome = _normalize_str(nome)
    m = PADRAO_ATIVIDADE.match(nome)

    if m:
        numero = f"{m.group(1)}.{m.group(2)}"
        titulo = _normalize_str(m.group(3))
        return numero, numero, nome, titulo

    numero_custom = _none_if_empty(custom_fields.get("numero_atividade"))
    return numero_custom, numero_custom, nome, nome


def _meta_sort_key(meta: dict):
    nome = _normalize_str(meta.get("meta_nome"))
    m = PADRAO_META.match(nome)
    return int(m.group(1)) if m else 9999


def _atividade_sort_key(atividade: dict):
    numero = _normalize_str(
        atividade.get("numero_atividade_original") or atividade.get("numero_atividade")
    )
    m = PADRAO_NUMERO_ATIVIDADE.match(numero)

    if m:
        return (int(m.group(1)), int(m.group(2)))

    return (9999, 9999)


def to_report_base_from_clickup(payload: dict) -> RelatorioCanonico:
    tasks = payload.get("tasks", []) or []

    metas_por_id = {}
    atividades_por_meta_id = defaultdict(list)

    for task in tasks:
        nome = _extract_task_name(task)
        if not nome:
            continue

        if _extract_parent_id(task):
            continue

        m = PADRAO_META.match(nome)
        if not m:
            continue

        numero_meta = int(m.group(1))
        meta_id = _extract_task_id(task)

        if not meta_id:
            continue

        metas_por_id[meta_id] = {
            "item": str(numero_meta),
            "meta_id_original": meta_id,
            "meta_nome": nome,
            "percentual_meta": None,
            "atividades": [],
            "progresso": {
                "previsto_percentual_medio": None,
                "realizado_percentual_medio": None,
            },
        }

    for task in tasks:
        parent_id = _extract_parent_id(task)
        if not parent_id or parent_id not in metas_por_id:
            continue

        task_id = _extract_task_id(task)
        if not task_id:
            continue

        nome = _extract_task_name(task)
        custom_fields = _extract_custom_fields(task)

        (
            numero_atividade,
            numero_atividade_original,
            titulo_original,
            titulo,
        ) = _extract_activity_parts(nome, custom_fields)

        atividade = {
            "atividade_id": task_id,
            "numero_atividade": numero_atividade,
            "numero_atividade_original": numero_atividade_original,
            "titulo_original": titulo_original,
            "titulo": titulo,
            "indicador_fisico": custom_fields.get("indicador_fisico"),
            "status_clickup": _extract_status(task),
            "percentual_realizado": custom_fields.get("percentual_realizado"),
            "datas": _extract_dates(task),
            "progresso": {
                "atrasada": None,
                "situacao_prazo": None,
                "duracao_prevista_dias": None,
                "duracao_efetiva_dias": None,
                "mes_ano_inicio_previsto": None,
                "mes_ano_fim_previsto": None,
                "mes_ano_inicio_real": None,
                "mes_ano_fim_real": None,
                "previsto_percentual": None,
                "realizado_percentual": None,
            },
            "texto": {
                "desenvolvimento": "",
                "resultados": "",
                "justificativa": "",
            },
            "origem": {
                "source": "clickup_raw",
                "task_id": task_id,
                "parent_id": parent_id,
                "list_id": (task.get("list") or {}).get("id"),
                "custom_fields": custom_fields,
            },
        }

        atividades_por_meta_id[parent_id].append(atividade)

    metas_ordenadas = []
    for meta_id, meta in metas_por_id.items():
        atividades = sorted(atividades_por_meta_id.get(meta_id, []), key=_atividade_sort_key)

        if not atividades:
            continue

        if _normalize_str(meta.get("meta_nome")).startswith("Meta 0"):
            continue

        meta["atividades"] = atividades
        metas_ordenadas.append(meta)

    metas_ordenadas = sorted(metas_ordenadas, key=_meta_sort_key)

    return RelatorioCanonico(
        metadata={
            "source": "clickup_raw",
            "task_count": len(tasks),
        },
        resumo_projeto=ResumoProjetoCanonico(),
        metas=metas_ordenadas,
    )