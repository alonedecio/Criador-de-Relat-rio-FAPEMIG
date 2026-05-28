"""
Merger — aplica os textos gerados pelos agentes no relatório canônico.

Recebe:
    relatorio: dict  — estrutura do relatorio_com_progresso_clickup_api.json
    resultados: list[ResultadoAtividade]  — saída do pipeline de agentes

Devolve:
    relatorio_com_textos: dict  — relatório com os campos de texto preenchidos
                                  + trilha de auditoria embutida

O merger não altera nenhum campo de progresso, datas ou metas;
ele apenas injeta os três campos textuais e a auditoria.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from app.domain.ai.schemas import ResultadoAtividade

logger = logging.getLogger(__name__)


def _index_resultados(
    resultados: list[ResultadoAtividade],
) -> dict[str, ResultadoAtividade]:
    """Indexa resultados por atividade_id para lookup O(1)."""
    return {r.atividade_id: r for r in resultados}


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
        relatorio:  dict carregado do relatorio_com_progresso_clickup_api.json
        resultados: lista de ResultadoAtividade produzidos pelo pipeline

    Returns:
        Novo dict com textos e auditoria aplicados.
    """
    relatorio_final = copy.deepcopy(relatorio)
    idx = _index_resultados(resultados)

    total = 0
    aplicados = 0
    nao_encontrados: list[str] = []

    for item in relatorio_final.get("itens", []):
        for atividade in item.get("atividades", []):
            total += 1
            ativ_id = atividade.get("atividadeId") or atividade.get("atividade_id", "")

            resultado = idx.get(ativ_id)
            if resultado is None:
                nao_encontrados.append(ativ_id)
                continue

            atividade["desenvolvimento"] = resultado.textos.desenvolvimento
            atividade["resultados"]      = resultado.textos.resultados
            atividade["justificativa"]   = resultado.textos.justificativa
            atividade["_auditoria"] = {
                "tentativas":        resultado.auditoria.tentativas,
                "status_validacao":  resultado.auditoria.status_final,
                "erros":             resultado.auditoria.erros_encontrados,
                "fontes_contexto":   resultado.auditoria.fontes_contexto,
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
