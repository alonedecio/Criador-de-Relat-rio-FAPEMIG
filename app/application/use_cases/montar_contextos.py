"""
Use case: MontarContextosUseCase

Responsabilidade única: dado um relatório canônico (JSON já carregado),
o enriched snapshot do ClickUp e o PDF do projeto, produzir a lista
completa de ContextoAtividade para todas as atividades.

Não acessa ClickUp, não acessa PDF diretamente, não chama IA.
Recebe os dados já carregados e orquestra os serviços de domínio.

ORDEM CORRETA DO PIPELINE POR ATIVIDADE:
  1. montar_contexto()   → resolve datas (ClickUp > PDF > ausente),
                            monta descrição, checklists, responsáveis
  2. calcular_progresso() → recebe as datas já resolvidas como override,
                            garantindo que datas do PDF sejam usadas
                            mesmo quando ClickUp não tem startdate/duedate
  3. ctx.progresso = ...  → injeta resultado de volta no contexto

Essa ordem é intencional: calcular_progresso precisa das datas definitivas,
que só estão disponíveis após montar_contexto() cruzar ClickUp + PDF.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.domain.context.builders import ContextoAtividade, montar_contexto
from app.domain.projects.pdf_extractor import ProjetoExtraido
from app.domain.reporting.canonical_schemas import (
    AtividadeCanonica,
    MetaCanonica,
    RelatorioCanonico,
)
from app.domain.reporting.progress import calcular_progresso

logger = logging.getLogger(__name__)


# ── modelos de entrada ────────────────────────────────────────────────────


@dataclass
class EnrichedIndex:
    """
    Índice de tasks enriquecidas, indexado por código de atividade.
    Construído pelo orquestrador antes de chamar este use case.

    task_por_codigo: {"1.1": ClickUpTaskEnriched, ...}
    """
    task_por_codigo: dict = field(default_factory=dict)

    def get(self, codigo: str):
        return self.task_por_codigo.get(codigo)


# ── resultado ─────────────────────────────────────────────────────────────


@dataclass
class ResultadoContextos:
    contextos:         list[ContextoAtividade]
    total:             int
    com_dados:         int
    sem_dados:         int
    sem_task_clickup:  int
    sem_datas_pdf:     int
    codigos_sem_dados: list[str] = field(default_factory=list)

    def resumo(self) -> str:
        return (
            f"{self.com_dados}/{self.total} atividades com dados suficientes "
            f"({self.sem_task_clickup} sem task ClickUp, "
            f"{self.sem_datas_pdf} sem datas no PDF)"
        )


# ── use case ──────────────────────────────────────────────────────────────


class MontarContextosUseCase:
    """
    Monta ContextoAtividade para cada atividade do relatório canônico.

    Fluxo por atividade (ver docstring do módulo para justificativa da ordem):
      1. montar_contexto()    → resolve datas e monta estrutura
      2. calcular_progresso() → usa datas já resolvidas como override
      3. injeta progresso no contexto
    """

    def executar(
        self,
        relatorio:      RelatorioCanonico,
        enriched_index: EnrichedIndex,
        projeto_pdf:    Optional[ProjetoExtraido] = None,
    ) -> ResultadoContextos:

        contextos:         list[ContextoAtividade] = []
        sem_task_clickup   = 0
        sem_datas_pdf      = 0
        codigos_sem_dados: list[str] = []

        for meta in relatorio.metas:
            for atv in meta.atividades:
                codigo = atv.numero_atividade_original or atv.numero_atividade or atv.atividade_id
                ctx = self._montar_uma(
                    codigo=codigo,
                    atv=atv,
                    enriched_index=enriched_index,
                    projeto_pdf=projeto_pdf,
                )
                contextos.append(ctx)

                if not enriched_index.get(codigo):
                    sem_task_clickup += 1
                if not (ctx.data_inicio and ctx.data_fim):
                    sem_datas_pdf += 1
                if not ctx.tem_dados_suficientes():
                    codigos_sem_dados.append(codigo)

        total     = len(contextos)
        com_dados = total - len(codigos_sem_dados)

        resultado = ResultadoContextos(
            contextos=contextos,
            total=total,
            com_dados=com_dados,
            sem_dados=len(codigos_sem_dados),
            sem_task_clickup=sem_task_clickup,
            sem_datas_pdf=sem_datas_pdf,
            codigos_sem_dados=codigos_sem_dados,
        )

        logger.info("MontarContextosUseCase: %s", resultado.resumo())
        return resultado

    # ── privado ─────────────────────────────────────────────────────────────

    def _montar_uma(
        self,
        codigo:         str,
        atv:            AtividadeCanonica,
        enriched_index: EnrichedIndex,
        projeto_pdf:    Optional[ProjetoExtraido],
    ) -> ContextoAtividade:

        task    = enriched_index.get(codigo)
        pdf_atv = projeto_pdf.por_codigo(codigo) if projeto_pdf else None

        if not task:
            logger.debug("Atividade %s: sem task no ClickUp", codigo)
        if not pdf_atv:
            logger.debug("Atividade %s: sem entrada no PDF", codigo)

        # Passo 1: monta contexto (resolve datas ClickUp > PDF > ausente)
        ctx = montar_contexto(
            codigo=codigo,
            titulo=atv.titulo,
            task=task,
            pdf_atv=pdf_atv,
            progresso=None,  # será preenchido no passo 2
        )

        # Passo 2: calcula progresso com as datas já resolvidas
        # IMPORTANTE: passa data_inicio e data_fim do ctx como override para que
        # calcular_progresso use as datas do PDF quando o ClickUp não tem datas.
        if task:
            ctx.progresso = calcular_progresso(
                task=task,
                data_inicio_override=ctx.data_inicio,
                data_fim_override=ctx.data_fim,
            )
        else:
            # Sem task no ClickUp: usa progresso já calculado anteriormente (se houver)
            ctx.progresso = atv.progresso

        return ctx
