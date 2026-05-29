"""
AIService — fachada do pipeline de agentes IA.

Uso típico:

    from app.domain.ai.service import AIService
    from app.domain.projects.pdf_reader import ler_pdf
    from app.domain.projects.termo_outorga import extrair_contexto_projeto

    pdf = ler_pdf(Path("data/input/termo_projeto.pdf"))
    ctx_projeto = extrair_contexto_projeto(pdf)

    service = AIService(llm_client=openai_client, ctx_projeto=ctx_projeto)
    relatorio_final = service.processar_relatorio(relatorio_dict, contextos_atividades)
"""
from __future__ import annotations

import logging
from typing import Any

from app.domain.ai.retry import executar_com_retry
from app.domain.ai.merger import aplicar_textos
from app.domain.ai.schemas import ResultadoAtividade
from app.domain.context.builders import ContextoAtividade
from app.domain.projects.termo_outorga import ContextoProjeto

logger = logging.getLogger(__name__)


class AIService:
    """
    Orquestra o pipeline completo:
    termo_outorga → contexto_projeto (estático)
    clickup + progresso → contexto_atividade (dinâmico)
    writer → validator → retry → merger → relatorio_final
    """

    def __init__(
        self,
        llm_client,
        ctx_projeto: ContextoProjeto,
        model: str = "gemini-2.5-flash-lite",
        max_tentativas: int = 3,
    ):
        self.llm_client      = llm_client
        self.ctx_projeto     = ctx_projeto
        self.model           = model
        self.max_tentativas  = max_tentativas

    def processar_atividade(
        self,
        ctx_atividade: ContextoAtividade,
    ) -> ResultadoAtividade:
        """Processa uma atividade individual. Retorna ResultadoAtividade."""
        textos, auditoria = executar_com_retry(
            ctx_projeto=self.ctx_projeto,
            ctx_atividade=ctx_atividade,
            llm_client=self.llm_client,
            model=self.model,
            max_tentativas=self.max_tentativas,
        )

        # Registra rastreabilidade da origem do contexto
        if not auditoria.fontes_contexto:
            fontes = []
            if ctx_atividade.task_id:
                fontes.append(f"clickup:{ctx_atividade.task_id}")
            else:
                fontes.append("sem_task_clickup")
            if ctx_atividade.progresso:
                fontes.append("progresso_calculado")
            if ctx_atividade.descricao:
                fontes.append("descricao_clickup")
            if ctx_atividade.comentarios:
                fontes.append(f"{len(ctx_atividade.comentarios)}_comentarios")
            if ctx_atividade.checklists:
                fontes.append(f"{len(ctx_atividade.checklists)}_checklists")
            if ctx_atividade.anexos:
                fontes.append(f"{len(ctx_atividade.anexos)}_anexos")
            auditoria.fontes_contexto = fontes

        return ResultadoAtividade(
            atividade_id=auditoria.atividade_id,
            meta_codigo=ctx_atividade.meta_codigo,
            titulo=ctx_atividade.titulo,
            textos=textos,
            auditoria=auditoria,
        )

    def processar_relatorio(
        self,
        relatorio: dict[str, Any],
        contextos: list[ContextoAtividade],
    ) -> dict[str, Any]:
        """
        Processa todas as atividades e aplica os textos no relatório.

        Args:
            relatorio:  dict do relatorio_com_progresso_clickup_api.json
            contextos:  lista de ContextoAtividade montados pelo builder

        Returns:
            Relatório final com textos e auditoria aplicados.
        """
        resultados: list[ResultadoAtividade] = []

        sem_clickup = [c.codigo for c in contextos if not c.task_id]
        if sem_clickup:
            logger.warning(
                "[AIService] %d atividade(s) sem task_id do ClickUp (contexto limitado): %s",
                len(sem_clickup), sem_clickup,
            )

        for i, ctx in enumerate(contextos, 1):
            logger.info(
                "[%d/%d] Processando atividade %s — %s%s",
                i, len(contextos),
                ctx.codigo,
                ctx.titulo[:60],
                " [sem task ClickUp]" if not ctx.task_id else "",
            )
            try:
                resultado = self.processar_atividade(ctx)
                resultados.append(resultado)
            except Exception as e:
                logger.error(
                    "Falha irrecuperável na atividade %s: %s",
                    ctx.codigo, e,
                )

        return aplicar_textos(relatorio, resultados)
