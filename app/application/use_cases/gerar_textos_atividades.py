"""
Use Case: Gerar Textos das Atividades

Orquestra todo o pipeline de ponta a ponta:

    1. Carrega o PDF do Termo de Outorga
       → extrai ContextoProjeto (objetivo geral, metas, vocabulário)

    2. Carrega o relatório canônico com progresso (JSON)

    3. Para cada atividade do relatório:
       → busca a task enriquecida do ClickUp pelo atividadeId
       → monta o ContextoAtividade (builder existente)

    4. Executa AIService.processar_relatorio()
       → writer → validator → retry → merger

    5. Salva o relatório final com textos em output/

Arquitetura LLM:
    Recebe llm_client já instanciado pelo pipeline_completo.py
    (openai.OpenAI com base_url Gemini — padrão Ed Donner).
    Nenhuma dependência de LiteLLM neste módulo.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_codigo(atividade: dict) -> str:
    return (
        atividade.get("numero_atividade_original")
        or atividade.get("numero_atividade")
        or atividade.get("numeroAtividadeOriginal")
        or atividade.get("numeroAtividade")
        or atividade.get("codigo")
        or ""
    )


def _get_ativ_id(atividade: dict) -> str:
    return (
        atividade.get("atividade_id")
        or atividade.get("atividadeId")
        or ""
    )


def _get_titulo(atividade: dict, codigo: str) -> str:
    return (
        atividade.get("titulo")
        or atividade.get("titulo_original")
        or atividade.get("tituloOriginal")
        or f"Atividade {codigo}"
    )


def _get_progresso(atividade: dict):
    return (
        atividade.get("progresso")
        or atividade.get("progressoCalculado")
    )


def _iter_atividades(relatorio: dict):
    """
    Itera sobre todas as atividades do relatório canônico tolerando
    tanto a estrutura 'metas' (Pydantic snake_case) quanto 'itens' (legado).
    """
    for meta in relatorio.get("metas", []):
        yield from meta.get("atividades", [])
    for item in relatorio.get("itens", []):
        yield from item.get("atividades", [])


def executar(
    termo_pdf_path: Path,
    relatorio_progresso_path: Path,
    clickup_snapshot_path: Path,
    output_path: Path,
    llm_client,
    model: str = "gemini-2.5-flash",
    max_tentativas: int = 3,
    atividades_filtro: Optional[list[str]] = None,
) -> dict:
    """
    Ponto de entrada do use case.

    Args:
        termo_pdf_path:           Path para data/input/termo_projeto.pdf
        relatorio_progresso_path: Path para o JSON com progresso calculado
        clickup_snapshot_path:    Path para o JSON enriquecido do ClickUp
        output_path:              Path para salvar o relatório final
        llm_client:               openai.OpenAI (Gemini via base_url ou OpenAI nativo)
        model:                    Modelo LLM — sem prefixo de provider
        max_tentativas:           Máximo de tentativas por atividade
        atividades_filtro:        Se fornecido, processa só estas atividades
                                  (ex: ["2.1", "4.1"] para teste parcial)

    Returns:
        Dicionário do relatório final com textos e auditoria.
    """
    # ── 1. Carrega e extrai o Termo de Outorga ──────────────────────────
    from app.domain.projects.pdf_reader import ler_pdf_projeto
    from app.domain.projects.termo_outorga import extrair_contexto_projeto

    logger.info("Carregando Termo de Outorga: %s", termo_pdf_path)
    pdf_indexado = ler_pdf_projeto(termo_pdf_path)
    ctx_projeto = extrair_contexto_projeto(pdf_indexado)
    logger.info(
        "ContextoProjeto extraído: '%s' | %d metas | %d obj. específicos",
        ctx_projeto.titulo_projeto[:60],
        len(ctx_projeto.metas_pactuadas),
        len(ctx_projeto.objetivos_especificos),
    )

    # ── 2. Carrega o relatório canônico com progresso ───────────────────
    logger.info("Carregando relatório de progresso: %s", relatorio_progresso_path)
    with open(relatorio_progresso_path, "r", encoding="utf-8") as f:
        relatorio = json.load(f)

    # ── 3. Carrega snapshot enriquecido do ClickUp ──────────────────────
    logger.info("Carregando snapshot ClickUp enriquecido: %s", clickup_snapshot_path)
    with open(clickup_snapshot_path, "r", encoding="utf-8") as f:
        snapshot_raw = json.load(f)

    from app.domain.clickup.models import ClickUpTaskEnriched
    tasks_index: dict[str, ClickUpTaskEnriched] = {}

    raw_list = snapshot_raw if isinstance(snapshot_raw, list) else snapshot_raw.get("tasks", [])
    for item in raw_list:
        try:
            task = ClickUpTaskEnriched(**item)
            tasks_index[task.task_id] = task
        except Exception as e:
            logger.debug("Ignorando task malformada no snapshot: %s", e)

    logger.info("Snapshot ClickUp: %d tasks indexadas.", len(tasks_index))

    # ── 4. Monta contextos das atividades ──────────────────────────────
    from app.domain.context.builders import montar_contexto
    from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico

    contextos = []
    codigos_encontrados: list[str] = []

    for atividade in _iter_atividades(relatorio):
        codigo  = _get_codigo(atividade)
        ativ_id = _get_ativ_id(atividade)
        titulo  = _get_titulo(atividade, codigo)

        if atividades_filtro and codigo not in atividades_filtro:
            continue

        codigos_encontrados.append(codigo)
        task = tasks_index.get(ativ_id)

        prog_raw = _get_progresso(atividade)
        progresso: Optional[ProgressoAtividadeCanonico] = None
        if prog_raw and isinstance(prog_raw, dict):
            try:
                progresso = ProgressoAtividadeCanonico(**prog_raw)
            except Exception:
                pass

        ctx = montar_contexto(
            codigo=codigo,
            titulo=titulo,
            task=task,
            pdf_atv=None,
            progresso=progresso,
        )
        contextos.append(ctx)

    logger.info("%d contextos de atividade montados.", len(contextos))
    if codigos_encontrados:
        logger.info("Códigos processados: %s", codigos_encontrados)

    if not contextos:
        todos = [_get_codigo(atv) for atv in _iter_atividades(relatorio)]
        logger.warning(
            "Nenhum contexto montado.\n"
            "  Filtro solicitado : %s\n"
            "  Códigos no relatório: %s",
            atividades_filtro,
            sorted(set(todos))[:20],
        )

    # ── 5. Executa pipeline de agentes ───────────────────────────────
    from app.domain.ai.service import AIService

    service = AIService(
        llm_client=llm_client,
        ctx_projeto=ctx_projeto,
        model=model,
        max_tentativas=max_tentativas,
    )
    relatorio_final = service.processar_relatorio(relatorio, contextos)

    # ── 6. Salva resultado ──────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(relatorio_final, f, ensure_ascii=False, indent=2)

    logger.info("Relatório final salvo em: %s", output_path)
    return relatorio_final
