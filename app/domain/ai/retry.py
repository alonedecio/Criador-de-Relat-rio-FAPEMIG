"""
Retry — orquestra ciclos de writer → validator até aprovação ou limite.

Estratégia:
    Tentativa 1: writer normal
    Tentativas 2+: writer com feedback do validator incluído no prompt
    Após MAX_TENTATIVAS: retorna o melhor resultado obtido (menor nº de erros)

Nunca lança exceção por estouro de tentativas — sempre retorna algo,
registrando na auditoria o status final.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.domain.ai.schemas import (
    TextosGerados,
    ResultadoValidacao,
    StatusValidacao,
    AuditoriaAtividade,
)
from app.domain.ai.writer import gerar_textos, WriterError, WriterParseError
from app.domain.ai.validator import validar_textos
from app.domain.context.builders import ContextoAtividade
from app.domain.projects.termo_outorga import ContextoProjeto

logger = logging.getLogger(__name__)

MAX_TENTATIVAS = 3


def _prompt_com_feedback(erros: list[str], sugestoes: list[str]) -> str:
    """Adiciona bloco de feedback do validator ao user prompt na reescrita."""
    erros_txt = "\n".join(f"  - {e}" for e in erros)
    sug_txt   = "\n".join(f"  - {s}" for s in sugestoes)
    return (
        "\n\n━━ FEEDBACK DO VALIDATOR (corrija estes pontos) ━━━━━━━━━━━━\n"
        f"ERROS ENCONTRADOS:\n{erros_txt}\n"
        f"SUGESTÕES:\n{sug_txt}\n"
        "Reescreva os três campos corrigindo os pontos acima.\n"
    )


def executar_com_retry(
    ctx_projeto: ContextoProjeto,
    ctx_atividade: ContextoAtividade,
    llm_client,
    model: str = "gpt-4o",
    max_tentativas: int = MAX_TENTATIVAS,
) -> tuple[TextosGerados, AuditoriaAtividade]:
    """
    Executa o ciclo writer → validator com retry automático.

    Returns:
        Tupla (textos_aprovados, auditoria).
        textos_aprovados pode ter status REPROVADO se nenhuma tentativa passou;
        nesse caso, é retornado o resultado com menos erros para revisão manual.
    """
    from app.domain.ai import prompts as _prompts
    import copy

    melhor_textos: Optional[TextosGerados] = None
    melhor_validacao: Optional[ResultadoValidacao] = None
    todos_erros: list[str] = []
    feedback_extra = ""

    for tentativa in range(1, max_tentativas + 1):
        logger.info(
            "Retry atividade %s — tentativa %d/%d",
            ctx_atividade.codigo, tentativa, max_tentativas,
        )

        # Writer: injeta feedback nas tentativas subsequentes
        try:
            if tentativa == 1 or not feedback_extra:
                textos = gerar_textos(ctx_projeto, ctx_atividade, llm_client, model)
            else:
                # Cria cópia do contexto com feedback embutido na descrição
                ctx_com_feedback = copy.copy(ctx_atividade)
                ctx_com_feedback.descricao = (
                    ctx_atividade.descricao + feedback_extra
                )
                textos = gerar_textos(ctx_projeto, ctx_com_feedback, llm_client, model)
        except (WriterError, WriterParseError) as e:
            logger.warning("Writer falhou na tentativa %d: %s", tentativa, e)
            todos_erros.append(f"Tentativa {tentativa}: {e}")
            continue

        # Validator
        validacao = validar_textos(ctx_atividade, textos, llm_client, model)

        # Guarda o melhor resultado (menor número de erros)
        if melhor_validacao is None or len(validacao.erros) < len(melhor_validacao.erros):
            melhor_textos    = textos
            melhor_validacao = validacao

        if validacao.status in (StatusValidacao.APROVADO, StatusValidacao.APROVADO_COM_RESSALVA):
            logger.info(
                "Atividade %s aprovada na tentativa %d (%s)",
                ctx_atividade.codigo, tentativa, validacao.status,
            )
            break

        # Prepara feedback para próxima tentativa
        feedback_extra = _prompt_com_feedback(
            validacao.erros,
            validacao.sugestoes_correcao,
        )
        todos_erros.extend(validacao.erros)

    # Fallback: se todas as tentativas falharam, usa o melhor obtido
    if melhor_textos is None:
        melhor_textos = TextosGerados(
            desenvolvimento="Não foi possível gerar o texto automaticamente. Revisão manual necessária.",
            resultados="Não foi possível gerar o texto automaticamente. Revisão manual necessária.",
            justificativa="Não foi possível gerar o texto automaticamente. Revisão manual necessária.",
        )
        status_final = StatusValidacao.REPROVADO
    else:
        status_final = melhor_validacao.status if melhor_validacao else StatusValidacao.APROVADO_COM_RESSALVA

    fontes = list({f.origem for f in ctx_atividade.fontes})

    auditoria = AuditoriaAtividade(
        atividade_id=ctx_atividade.task_id or ctx_atividade.codigo,
        tentativas=tentativa,
        status_final=status_final,
        erros_encontrados=todos_erros,
        fontes_contexto=fontes,
    )

    return melhor_textos, auditoria
