"""
Merger — aplica os textos gerados pelos agentes no relatório canônico.

Recebe:
    relatorio:  dict   — estrutura do relatorio_final_com_progresso.json
                         Suporta tanto 'metas' (Pydantic snake_case) quanto
                         'itens' (formato legado).
    resultados: list[ResultadoAtividade] — saída do pipeline de agentes

Devolve:
    relatorio_com_textos: dict — relatório com os campos de texto preenchidos
                                  + trilha de auditoria embutida

O merger não altera nenhum campo de progresso, datas ou metas;
ele apenas injeta os três campos textuais e a auditoria.

Lookup de atividade:
    Tenta por atividade_id (task_id do ClickUp) primeiro.
    Se não encontrar, tenta pelo código da atividade (ex: '2.1').
    Isso garante que atividades sem task_id também recebam os textos.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from app.domain.ai.schemas import ResultadoAtividade

logger = logging.getLogger(__name__)


def _index_resultados(
    resultados: list[ResultadoAtividade],
) -> tuple[dict[str, ResultadoAtividade], dict[str, ResultadoAtividade]]:
    """
    Constrói dois índices para lookup robusto:
        idx_id:     por atividade_id (task_id do ClickUp)
        idx_codigo: pelo código da atividade (ex: '2.1')
    """
    idx_id: dict[str, ResultadoAtividade] = {}
    idx_codigo: dict[str, ResultadoAtividade] = {}
    for r in resultados:
        if r.atividade_id:
            idx_id[r.atividade_id] = r
        # auditoria.atividade_id pode ser o código quando task_id está vazio
        if r.auditoria.atividade_id:
            idx_id[r.auditoria.atividade_id] = r
        # código sempre disponível como fallback
        codigo = getattr(r, "meta_codigo", None)
        # o código real fica em titulo ou auditoria — usa o proprio atividade_id
        # quando ele já é um código no formato N.N
        if r.atividade_id and "." in r.atividade_id:
            idx_codigo[r.atividade_id] = r
        if r.auditoria.atividade_id and "." in r.auditoria.atividade_id:
            idx_codigo[r.auditoria.atividade_id] = r
    return idx_id, idx_codigo


def _get_ativ_id(atividade: dict) -> str:
    """Extrai o task_id tolerando snake_case e camelCase."""
    return (
        atividade.get("atividade_id")
        or atividade.get("atividadeId")
        or ""
    )


def _get_codigo(atividade: dict) -> str:
    """Extrai o código da atividade tolerando snake_case e camelCase."""
    return (
        atividade.get("numero_atividade_original")
        or atividade.get("numero_atividade")
        or atividade.get("numeroAtividadeOriginal")
        or atividade.get("numeroAtividade")
        or atividade.get("codigo")
        or ""
    )


def _iter_atividades_com_ref(relatorio: dict) -> list[dict]:
    """
    Retorna a lista flat de dicionários de atividade, suportando
    tanto 'metas' (Pydantic snake_case) quanto 'itens' (legado).
    """
    atividades = []
    for meta in relatorio.get("metas", []):
        atividades.extend(meta.get("atividades", []))
    for item in relatorio.get("itens", []):
        atividades.extend(item.get("atividades", []))
    return atividades


def aplicar_textos(
    relatorio: dict[str, Any],
    resultados: list[ResultadoAtividade],
) -> dict[str, Any]:
    """
    Aplica os textos gerados no dicionário do relatório.

    A função é não-destrutiva: trabalha sobre deep copy do relatório.
    Os campos preenchidos são:
        - atividade.desenvolvimento
        - atividade.resultados
        - atividade.justificativa
        - atividade._auditoria  (campo de rastreabilidade, prefixo _ = interno)

    Args:
        relatorio:  dict do relatorio_final_com_progresso.json
        resultados: lista de ResultadoAtividade produzidos pelo pipeline

    Returns:
        Novo dict com textos e auditoria aplicados.
    """
    relatorio_final = copy.deepcopy(relatorio)
    idx_id, idx_codigo = _index_resultados(resultados)

    total     = 0
    aplicados = 0
    nao_encontrados: list[str] = []

    # Itera sobre metas (snake_case) e itens (legado)
    for container in (
        relatorio_final.get("metas", []) +
        relatorio_final.get("itens", [])
    ):
        for atividade in container.get("atividades", []):
            total += 1
            ativ_id = _get_ativ_id(atividade)
            codigo  = _get_codigo(atividade)

            # Lookup: task_id primeiro, código como fallback
            resultado = (
                idx_id.get(ativ_id)
                or idx_id.get(codigo)
                or idx_codigo.get(codigo)
            )

            if resultado is None:
                nao_encontrados.append(codigo or ativ_id or "?")
                continue

            atividade["desenvolvimento"] = resultado.textos.desenvolvimento
            atividade["resultados"]      = resultado.textos.resultados
            atividade["justificativa"]   = resultado.textos.justificativa
            atividade["_auditoria"] = {
                "tentativas":       resultado.auditoria.tentativas,
                "status_validacao": resultado.auditoria.status_final,
                "erros":            resultado.auditoria.erros_encontrados,
                "fontes_contexto":  resultado.auditoria.fontes_contexto,
            }
            aplicados += 1

    if nao_encontrados:
        logger.warning(
            "Merger: %d atividade(s) sem resultado de agente: %s",
            len(nao_encontrados),
            nao_encontrados[:10],
        )

    logger.info(
        "Merger: %d/%d atividades com textos aplicados.",
        aplicados, total,
    )

    return relatorio_final
