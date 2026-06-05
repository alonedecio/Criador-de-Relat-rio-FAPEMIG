"""
Use Case: Gerar Textos das Atividades

Orquestra todo o pipeline de ponta a ponta:

    1. Carrega o PDF do Termo de Outorga
       → extrai ContextoProjeto (objetivo geral, metas, vocabulário)

    2. Carrega o relatório canônico com progresso (JSON)

    3. Para cada atividade do relatório:
       → busca a task enriquecida do ClickUp pelo task_id (atividade_id) OU pelo código da atividade
       → título da atividade: usa task.base.name (ClickUp) quando task encontrada
       → monta o ContextoAtividade (builder existente)

    4. Executa AIService.processar_relatorio()
       → writer → validator → retry → merger

    5. Salva o relatório final com textos em output/

Indexação do snapshot:
    Duplo índice para lookup robusto:
      - idx_by_id:     task_id (ClickUp ID) → ClickUpTaskEnriched
      - idx_by_codigo: código da atividade (ex: '2.1') → ClickUpTaskEnriched
                       Resolve o campo 'codigo' do snapshot se disponível.

Estruturas de JSON suportadas em _iter_atividades:
    1. Canônica (Pydantic snake_case):
         { "metas": [ { "atividades": [...] } ] }
    2. Legado notebooks (relatorio_com_progresso_clickup_api.json):
         { "relatorio": { "secoes_fixas": {
             "3_tabela_resumo_execucao_cronograma_fisico": {
                 "itens_meta_atividade": [ { "atividades": [...] } ]
             }
         } } }
    3. Alternativa legado simples:
         { "itens": [ { "atividades": [...] } ] }

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


def _get_titulo_canonical(atividade: dict, codigo: str) -> str:
    """Título canônico do relatório — usado apenas como fallback."""
    return (
        atividade.get("titulo")
        or atividade.get("titulo_original")
        or atividade.get("tituloOriginal")
        or f"Atividade {codigo}"
    )


def _get_progresso(atividade: dict):
    """
    Lê o bloco de progresso da atividade tolerando as três chaves possíveis:
      - 'progresso_calculado'  → gerado pelo script legado dos notebooks
      - 'progresso'            → estrutura canônica nova
      - 'progressoCalculado'   → variante camelCase
    """
    return (
        atividade.get("progresso_calculado")
        or atividade.get("progresso")
        or atividade.get("progressoCalculado")
    )


def _iter_atividades(relatorio: dict):
    """
    Itera sobre todas as atividades do relatório tolerando 3 estruturas:

    1. Canônica nova (Pydantic snake_case):
         relatorio["metas"][*]["atividades"]

    2. Legado notebooks (relatorio_com_progresso_clickup_api.json):
         relatorio["relatorio"]["secoes_fixas"]
                  ["3_tabela_resumo_execucao_cronograma_fisico"]
                  ["itens_meta_atividade"][*]["atividades"]

    3. Alternativa legado simples:
         relatorio["itens"][*]["atividades"]
    """
    encontrou = False

    # ── Estrutura 1: canônica ────────────────────────────────────────────
    for meta in relatorio.get("metas", []):
        for atv in meta.get("atividades", []):
            encontrou = True
            yield atv

    # ── Estrutura 2: legado notebooks ────────────────────────────────────
    relatorio_inner = relatorio.get("relatorio", {})
    secoes = relatorio_inner.get("secoes_fixas", {})
    tabela = secoes.get("3_tabela_resumo_execucao_cronograma_fisico", {})
    for meta in tabela.get("itens_meta_atividade", []):
        for atv in meta.get("atividades", []):
            encontrou = True
            yield atv

    # ── Estrutura 3: alternativa legado simples ──────────────────────────
    for item in relatorio.get("itens", []):
        for atv in item.get("atividades", []):
            encontrou = True
            yield atv

    if not encontrou:
        chaves = list(relatorio.keys())
        logger.warning(
            "_iter_atividades: nenhuma atividade encontrada. "
            "Chaves raiz do JSON: %s",
            chaves,
        )


def _build_snapshot_indexes(
    snapshot_raw: dict | list,
) -> tuple[dict, dict]:
    """
    Constrói dois índices a partir do snapshot enriquecido:

      idx_by_id:     task_id (ClickUp ID)        → ClickUpTaskEnriched
      idx_by_codigo: código da atividade (N.N)   → ClickUpTaskEnriched

    Suporta tanto envelope {"tasks": [...]} quanto lista direta.
    Usa ClickUpEnrichedSnapshot para deserialização robusta.
    """
    from app.domain.clickup.models import ClickUpEnrichedSnapshot, ClickUpTaskEnriched

    # Tenta deserializar via envelope tipado
    try:
        if isinstance(snapshot_raw, dict) and "tasks" in snapshot_raw:
            envelope = ClickUpEnrichedSnapshot(**snapshot_raw)
            tasks = envelope.tasks
        elif isinstance(snapshot_raw, list):
            # lista direta de tasks enriquecidas
            tasks = []
            for item in snapshot_raw:
                try:
                    tasks.append(ClickUpTaskEnriched(**item))
                except Exception as e:
                    logger.debug("Task malformada ignorada no snapshot: %s", e)
        else:
            tasks = []
            logger.warning("Formato de snapshot não reconhecido: %s", type(snapshot_raw))
    except Exception as e:
        logger.error("Falha ao deserializar snapshot via ClickUpEnrichedSnapshot: %s", e)
        tasks = []

    idx_by_id:     dict = {}
    idx_by_codigo: dict = {}

    for task in tasks:
        # Índice primário: task_id
        if task.task_id:
            idx_by_id[task.task_id] = task

        # Índice secundário: campo 'codigo' explícito no snapshot (se existir)
        codigo_snapshot = getattr(task, "codigo", None)
        if codigo_snapshot:
            idx_by_codigo[str(codigo_snapshot)] = task

    logger.info(
        "Snapshot indexado: %d tasks por task_id, %d por código.",
        len(idx_by_id), len(idx_by_codigo),
    )
    return idx_by_id, idx_by_codigo


def _buscar_task(ativ_id: str, codigo: str, idx_by_id: dict, idx_by_codigo: dict):
    """
    Busca a task enriquecida com duplo índice:
      1. task_id (ClickUp ID) via idx_by_id
      2. codigo da atividade via idx_by_codigo
    """
    return (
        idx_by_id.get(ativ_id)
        or idx_by_codigo.get(codigo)
    )


def executar(
    termo_pdf_path: Path,
    relatorio_progresso_path: Path,
    clickup_snapshot_path: Path,
    output_path: Path,
    llm_client,
    model: str = "gemini-2.5-flash-lite",
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

    # ── Diagnóstico da estrutura do JSON ────────────────────────────────
    todos_codigos = [_get_codigo(atv) for atv in _iter_atividades(relatorio)]
    logger.info(
        "Relatório carregado: %d atividades encontradas (chaves raiz: %s)",
        len(todos_codigos),
        list(relatorio.keys()),
    )

    # ── 3. Carrega e indexa snapshot enriquecido do ClickUp ─────────────
    logger.info("Carregando snapshot ClickUp enriquecido: %s", clickup_snapshot_path)
    with open(clickup_snapshot_path, "r", encoding="utf-8") as f:
        snapshot_raw = json.load(f)

    idx_by_id, idx_by_codigo = _build_snapshot_indexes(snapshot_raw)
    logger.info(
        "Snapshot ClickUp: %d tasks no índice por task_id.",
        len(idx_by_id),
    )

    # ── 4. Monta contextos das atividades ──────────────────────────────
    from app.domain.context.builders import montar_contexto
    from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico

    contextos = []
    codigos_encontrados: list[str] = []
    codigos_sem_task:    list[str] = []

    for atividade in _iter_atividades(relatorio):
        codigo  = _get_codigo(atividade)
        ativ_id = _get_ativ_id(atividade)

        if atividades_filtro and codigo not in atividades_filtro:
            continue

        codigos_encontrados.append(codigo)

        # Busca com duplo índice: task_id primeiro, código como fallback
        task = _buscar_task(
            ativ_id=ativ_id,
            codigo=codigo,
            idx_by_id=idx_by_id,
            idx_by_codigo=idx_by_codigo,
        )

        if task is None:
            codigos_sem_task.append(codigo)
            logger.warning(
                "Atividade %s (task_id=%r): não encontrada no snapshot enriquecido. "
                "Contexto será montado sem dados do ClickUp.",
                codigo, ativ_id or "—",
            )

        # Título: usa base.name do ClickUp quando task encontrada
        # Isso garante que o título exibido no relatório é o título original do ClickUp
        if task is not None:
            titulo = task.base.name
        else:
            titulo = _get_titulo_canonical(atividade, codigo)

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

    logger.info(
        "%d contextos montados (filtro=%s). %d/%d com task ClickUp.",
        len(contextos),
        atividades_filtro or "nenhum",
        len(contextos) - len(codigos_sem_task),
        len(contextos),
    )
    if codigos_sem_task:
        logger.warning(
            "%d atividade(s) sem task no snapshot (sem contexto ClickUp): %s",
            len(codigos_sem_task), codigos_sem_task,
        )
    if codigos_encontrados:
        logger.info("Códigos processados: %s", codigos_encontrados)

    if not contextos:
        logger.warning(
            "Nenhum contexto montado.\n"
            "  Filtro solicitado  : %s\n"
            "  Todos os códigos   : %s",
            atividades_filtro,
            sorted(set(todos_codigos))[:20],
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
